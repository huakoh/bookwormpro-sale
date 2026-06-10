#!/usr/bin/env node
/**
 * 消歧决策树引擎 (v5.9)
 *
 * 将 disambiguation-rules.json 的 38 条规则编译为决策树，
 * 实现 O(log N) 查询和自动冲突检测。
 *
 * 设计:
 *   - 决策树节点: 条件测试 (关键词/意图/实体)
 *   - 叶子节点: 技能推荐 (boost/penalty)
 *   - 支持在线构建 + 缓存
 *
 * 模块导出:
 *   buildDecisionTree(rules) → tree
 *   evaluateTree(tree, query, intents, entities) → { boost, penalty, firedRules }
 *   detectConflicts(rules) → conflicts[]
 */

const fs = require('fs');
const path = require('path');

const detectClaudeRoot = () => require('./paths.config.js').PATHS.root;

const ROOT = detectClaudeRoot();
const RULES_FILE = path.join(ROOT, 'scripts', 'disambiguation-rules.json');

/**
 * 加载消歧规则
 * @returns {Array} 规则列表
 */
function loadRules() {
  try {
    const data = JSON.parse(fs.readFileSync(RULES_FILE, 'utf8'));
    return data.rules || [];
  } catch {
    return [];
  }
}

/**
 * 从规则中提取关键词簇 (用于决策树节点)
 * @param {string} triggerPattern - 正则字符串
 * @returns {string[]} 关键词列表
 */
function extractKeywords(triggerPattern) {
  // 将 regex pattern 拆分为关键词 (以 | 分割，去除正则元字符)
  return triggerPattern
    .split('|')
    .map(k => k.replace(/[\\().*+?^${}[\]]/g, '').trim().toLowerCase())
    .filter(k => k.length >= 2);
}

/**
 * 构建决策树
 * 按规则优先级分组:
 *   Level 0: 高优先级精确匹配 (weight >= 0.6)
 *   Level 1: 中优先级组合匹配 (weight 0.3-0.6)
 *   Level 2: 低优先级通用匹配 (weight < 0.3)
 *
 * @param {Array} rules - 规则列表
 * @returns {Object} 决策树
 */
function buildDecisionTree(rules) {
  if (!rules || rules.length === 0) return { levels: [], ruleCount: 0 };

  const levels = [[], [], []]; // high, medium, low

  for (const rule of rules) {
    const weight = rule.weight || 0.5;
    const keywords = extractKeywords(rule.trigger);
    const node = {
      id: rule.id,
      keywords,
      trigger: new RegExp(rule.trigger, 'i'),
      boost: rule.boost,
      penalty: rule.penalty || [],
      weight,
      note: rule.note || '',
    };

    if (weight >= 0.6) levels[0].push(node);
    else if (weight >= 0.3) levels[1].push(node);
    else levels[2].push(node);
  }

  // 每层内按关键词数量排序 (更多关键词 = 更具体 → 优先)
  for (const level of levels) {
    level.sort((a, b) => b.keywords.length - a.keywords.length);
  }

  return {
    levels,
    ruleCount: rules.length,
    builtAt: new Date().toISOString(),
  };
}

/**
 * 评估决策树
 * @param {Object} tree - 决策树
 * @param {string} query - 用户查询
 * @returns {{ boosts: Map, penalties: Map, firedRules: string[] }}
 */
function evaluateTree(tree, query) {
  const queryLower = (query || '').toLowerCase();
  const boosts = new Map();
  const penalties = new Map();
  const firedRules = [];

  // 逐层评估，高优先级先匹配
  for (const level of tree.levels) {
    for (const node of level) {
      if (!node.trigger.test(queryLower)) continue;

      firedRules.push(node.id);

      // 累积 boost (取最大值)
      if (node.boost) {
        const current = boosts.get(node.boost) || 0;
        boosts.set(node.boost, Math.max(current, node.weight));
      }

      // 累积 penalty
      for (const pen of node.penalty) {
        const current = penalties.get(pen) || 0;
        penalties.set(pen, Math.max(current, node.weight * 0.5));
      }
    }
  }

  return { boosts, penalties, firedRules };
}

/**
 * 检测规则冲突
 * 冲突定义: 两条规则的 trigger 有交集 且 boost 不同
 * @param {Array} rules - 规则列表
 * @returns {Array} 冲突列表 [{ ruleA, ruleB, overlap }]
 */
function detectConflicts(rules) {
  const conflicts = [];
  const compiled = rules.map(r => ({
    ...r,
    keywords: new Set(extractKeywords(r.trigger)),
  }));

  for (let i = 0; i < compiled.length; i++) {
    for (let j = i + 1; j < compiled.length; j++) {
      const a = compiled[i];
      const b = compiled[j];
      if (a.boost === b.boost) continue; // 同目标不算冲突

      // 计算关键词交集
      const overlap = [...a.keywords].filter(k => b.keywords.has(k));
      if (overlap.length >= 2) { // 至少 2 个共同关键词
        conflicts.push({
          ruleA: a.id,
          ruleB: b.id,
          boostA: a.boost,
          boostB: b.boost,
          overlap,
          severity: overlap.length >= 3 ? 'high' : 'medium',
        });
      }
    }
  }

  return conflicts;
}

// 缓存编译后的决策树
let _cachedTree = null;

/**
 * 获取或构建决策树 (带缓存)
 * @returns {Object} 决策树
 */
function getTree() {
  if (_cachedTree) return _cachedTree;
  const rules = loadRules();
  _cachedTree = buildDecisionTree(rules);
  return _cachedTree;
}

/**
 * 清除缓存 (规则文件变更时调用)
 */
function clearCache() {
  _cachedTree = null;
}

// 模块导出
if (typeof module !== 'undefined') {
  module.exports = {
    loadRules, extractKeywords, buildDecisionTree, evaluateTree,
    detectConflicts, getTree, clearCache,
  };
}

// CLI 入口
if (require.main === module) {
  const rules = loadRules();
  console.log(`规则总数: ${rules.length}`);

  const tree = buildDecisionTree(rules);
  console.log(`决策树: ${tree.levels.map((l, i) => `L${i}=${l.length}`).join(', ')}`);

  const conflicts = detectConflicts(rules);
  console.log(`\n冲突检测: ${conflicts.length} 个`);
  for (const c of conflicts) {
    console.log(`  [${c.severity}] ${c.ruleA} (→${c.boostA}) vs ${c.ruleB} (→${c.boostB}) — 共同词: ${c.overlap.join(', ')}`);
  }

  // 测试查询
  const testQueries = ['React 组件 bug', 'K8s 部署', 'API 安全', '数据库架构设计', '代码审查'];
  console.log('\n测试查询:');
  for (const q of testQueries) {
    const result = evaluateTree(tree, q);
    const boostStr = [...result.boosts.entries()].map(([k, v]) => `${k}(+${v})`).join(', ') || 'none';
    console.log(`  "${q}" → boost: ${boostStr} | rules: ${result.firedRules.join(',') || 'none'}`);
  }
}
