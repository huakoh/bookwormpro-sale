#!/usr/bin/env node
/**
 * SLI/SLO 定义 (P95 targets):
 * - 路由延迟 P95 < 50ms (当前实测 6-9ms)
 * - 路由准确率 > 80% (MRR on corrections holdout)
 * - Hook 成功率 > 99% (非 ask/deny 退出)
 */
/**
 * 路由遥测模块 (v5.8 P0-C)
 *
 * 记录每次路由决策的结构化指标，用于量化路由效果和回归检测。
 * 追加到 debug/route-metrics.jsonl
 *
 * 模块导出:
 *   emitRouteMetric(decision) → void
 *   loadRecentMetrics(days) → Array
 *   getSkillRouteStats() → Map<skillName, routeCount>
 */

const fs = require('fs');
const { safeAppendJsonl } = require('./lib/safe-append.js');
const path = require('path');

const detectClaudeRoot = () => require('./paths.config.js').PATHS.root;

const ROOT = detectClaudeRoot();
const DEBUG_DIR = path.join(ROOT, 'debug');
const METRICS_FILE = path.join(DEBUG_DIR, 'route-metrics.jsonl');
const STATS_FILE = path.join(DEBUG_DIR, 'route-stats.json');

/**
 * 记录路由决策指标
 * @param {Object} decision
 * @param {string} decision.query - 用户查询 (截断到200字)
 * @param {number} decision.queryLength - 查询词数
 * @param {string} decision.selectedSkill - 最终选中技能
 * @param {number} decision.topScore - top-1 分值
 * @param {number} decision.gap12 - top-1 与 top-2 的分值差
 * @param {number} decision.confidence - 置信度
 * @param {string[]} decision.rulesFired - 触发的消歧规则 ID
 * @param {boolean} decision.coldStartApplied - 是否施加了冷启动 boost
 * @param {string[]} decision.coldStartSkills - 获得 boost 的技能列表
 * @param {number} decision.latencyMs - 路由总延迟
 * @param {string} decision.experimentId - A/B 实验 ID (如有)
 */
function emitRouteMetric(decision) {
  try {
    if (!fs.existsSync(DEBUG_DIR)) fs.mkdirSync(DEBUG_DIR, { recursive: true });
    const metric = {
      ts: new Date().toISOString(),
      query_length: decision.queryLength || 0,
      selected_skill: decision.selectedSkill || 'unknown',
      top_score: decision.topScore || 0,
      gap_1_2: decision.gap12 || 0,
      confidence: decision.confidence || 0,
      rules_fired: decision.rulesFired || [],
      cold_start_applied: decision.coldStartApplied || false,
      cold_start_skills: decision.coldStartSkills || [],
      latency_ms: decision.latencyMs || 0,
      experiment_id: decision.experimentId || null,
    };
    safeAppendJsonl(METRICS_FILE, metric);
  } catch {}
}

/**
 * 从 route-*.jsonl 日志统计每个技能的历史路由次数
 * 用于冷启动检测: routeCount < COLD_START_THRESHOLD 的技能需要 boost
 * @param {number} days - 统计最近 N 天 (默认 30)
 * @returns {Map<string, number>} skillName → routeCount
 */
function getSkillRouteStats(days = 30) {
  const stats = new Map();

  // 优先从缓存读取 (1 小时内有效)
  try {
    if (fs.existsSync(STATS_FILE)) {
      const cached = JSON.parse(fs.readFileSync(STATS_FILE, 'utf8'));
      const age = Date.now() - new Date(cached.ts).getTime();
      if (age < 3600000) { // 1 小时缓存
        return new Map(Object.entries(cached.stats));
      }
    }
  } catch {}

  // 扫描 route-YYYY-MM-DD.jsonl 文件
  try {
    const now = new Date();
    for (let i = 0; i < days; i++) {
      const d = new Date(now);
      d.setDate(d.getDate() - i);
      const dateStr = d.toISOString().slice(0, 10);
      const logFile = path.join(DEBUG_DIR, `route-${dateStr}.jsonl`);
      if (!fs.existsSync(logFile)) continue;

      const lines = fs.readFileSync(logFile, 'utf8').trim().split('\n');
      for (const line of lines) {
        if (!line) continue;
        try {
          const entry = JSON.parse(line);
          // 过滤系统噪声: task-notification 不是真实用户查询
          if (entry.query && entry.query.includes('<task-notification>')) continue;
          const skill = entry.topResult || entry.selected_skill;
          if (skill && skill !== 'none') {
            stats.set(skill, (stats.get(skill) || 0) + 1);
          }
        } catch {}
      }
    }
  } catch {}

  // 写入缓存
  try {
    if (!fs.existsSync(DEBUG_DIR)) fs.mkdirSync(DEBUG_DIR, { recursive: true });
    const cacheData = { ts: new Date().toISOString(), stats: Object.fromEntries(stats) };
    fs.writeFileSync(STATS_FILE, JSON.stringify(cacheData, null, 2) + '\n');
  } catch {}

  return stats;
}

/**
 * 加载最近 N 天的遥测指标 (用于离线分析)
 * @param {number} maxLines - 最大行数
 * @returns {Array}
 */
function loadRecentMetrics(maxLines = 500) {
  try {
    if (!fs.existsSync(METRICS_FILE)) return [];
    const lines = fs.readFileSync(METRICS_FILE, 'utf8').trim().split('\n');
    const recent = lines.slice(-maxLines);
    return recent.map(l => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);
  } catch { return []; }
}

// 模块导出
if (typeof module !== 'undefined') {
  module.exports = {
    emitRouteMetric,
    getSkillRouteStats,
    loadRecentMetrics,
    METRICS_FILE,
    STATS_FILE,
  };
}

// CLI: 显示路由统计概览
if (require.main === module) {
  const stats = getSkillRouteStats(30);
  const sorted = [...stats.entries()].sort((a, b) => b[1] - a[1]);

  console.log('=== 路由统计 (最近 30 天) ===\n');
  console.log(`总技能: ${sorted.length}`);
  const totalRoutes = sorted.reduce((sum, [, c]) => sum + c, 0);
  console.log(`总路由: ${totalRoutes}\n`);

  const COLD_THRESHOLD = 30;
  const cold = sorted.filter(([, c]) => c < COLD_THRESHOLD);
  if (cold.length > 0) {
    console.log(`冷启动技能 (< ${COLD_THRESHOLD} 次):`);
    for (const [name, count] of cold) {
      console.log(`  ${name.padEnd(35)} ${count} 次`);
    }
    console.log();
  }

  console.log('Top 20 热门技能:');
  for (const [name, count] of sorted.slice(0, 20)) {
    const bar = '█'.repeat(Math.round(count / (sorted[0]?.[1] || 1) * 20));
    console.log(`  ${name.padEnd(35)} ${String(count).padStart(5)} ${bar}`);
  }
}
