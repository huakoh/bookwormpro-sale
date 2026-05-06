#!/usr/bin/env node
/**
 * 路由置信度引擎
 *
 * 基于 skills-index.json 对输入文本做语义匹配，
 * 返回 top-K 技能及置信度分数。
 *
 * 用法:
 *   node scripts/route-analyzer.js "React 组件性能优化"
 *   node scripts/route-analyzer.js --top 10 "部署到 k8s"
 *   node scripts/route-analyzer.js --json "写一个 REST API"
 *   node scripts/route-analyzer.js --log "调试内存泄漏"
 *
 * 置信度阈值:
 *   >= 0.8  高置信度 - 直接路由
 *   0.5-0.8 中置信度 - 推荐候选
 *   < 0.5   低置信度 - fallback developer-expert
 */

const fs = require('fs');
const path = require('path');

const detectClaudeRoot = () => require('./paths.config.js').PATHS.root;

const CLAUDE_ROOT = detectClaudeRoot();
const INDEX_FILE = path.join(CLAUDE_ROOT, 'skills-index.json');
const DEBUG_DIR = path.join(CLAUDE_ROOT, 'debug');
const WEIGHTS_FILE = path.join(DEBUG_DIR, 'route-weights.json');

// === 参数解析 (延迟到 main 内使用，仅在直接执行时校验) ===
let args, jsonMode, logMode, topK, query;
function parseArgs() {
  args = process.argv.slice(2);
  jsonMode = args.includes('--json');
  logMode = args.includes('--log');
  const topIdx = args.indexOf('--top');
  topK = (topIdx >= 0 && parseInt(args[topIdx + 1])) || 5;
  query = args.filter(a => !a.startsWith('--') && !(topIdx >= 0 && args[topIdx + 1] === a)).join(' ');
}

// === 加载索引 ===
function loadIndex() {
  if (!fs.existsSync(INDEX_FILE)) {
    console.error('skills-index.json not found. Run: node scripts/generate-skill-index.js');
    process.exit(1);
  }
  return JSON.parse(fs.readFileSync(INDEX_FILE, 'utf8'));
}

// === 文本标准化 ===
// P0-FIX: 从 skills-index 构建已知中文关键词集合
let _knownCnKwCache = null;
function _getKnownCnKeywords() {
  if (_knownCnKwCache) return _knownCnKwCache;
  _knownCnKwCache = new Set();
  try {
    const idxFile = path.join(CLAUDE_ROOT, 'skills-index-lite.json');
    const idx = JSON.parse(fs.readFileSync(idxFile, 'utf8'));
    for (const skill of (idx.skills || [])) {
      for (const kw of (skill.keywords || [])) {
        const k = (kw.keyword || kw).toLowerCase();
        if (/[\u4e00-\u9fff]/.test(k)) _knownCnKwCache.add(k);
      }
    }
  } catch {}
  return _knownCnKwCache;
}

// P1-FIX: 否定检测 — 否定词后 1-3 token 降权
const NEGATION_WORDS = new Set([
  '不用', '不要', '不是', '别用', '除了', '排除', '去掉', '不需要', '不使用',
  'without', 'except', 'exclude', 'no', 'not', 'dont', "don\'t", 'remove'
]);

function tokenize(text) {
  // P2: 截断超长输入，防止性能退化
  text = (text || '').slice(0, 2000);
  const tokens = new Set();

  // 高频复合词优先匹配 (减少滑动窗口噪声)
  const COMPOUND_WORDS = new Set([
    "数据库", "服务器", "微服务", "框架设计", "项目管理",
    "接口设计", "单元测试", "集成测试", "性能优化", "代码审查",
    "架构设计", "版本控制", "持续集成", "持续部署", "负载均衡",
    "消息队列", "缓存策略", "安全审计", "权限管理", "日志分析",
    "容器化", "虚拟化", "自动化", "可视化", "模块化",
    "数据分析", "机器学习", "深度学习", "自然语言", "搜索引擎",
    "前端开发", "后端开发", "全栈开发", "移动开发", "跨平台",
    "状态管理", "路由设计", "组件开发", "响应式", "渐进式",
    "大语言模型", "向量数据库", "知识图谱", "推荐系统",
  ]);
  const textLower = text.toLowerCase();
  for (const w of COMPOUND_WORDS) {
    if (textLower.includes(w)) tokens.add(w);
  }

  // 中文: 2-4 字符片段 (滑动窗口)
  const cnChars = text.match(/[\u4e00-\u9fff]+/g) || [];
  for (const chunk of cnChars) {
    for (let len = 2; len <= Math.min(4, chunk.length); len++) {
      for (let i = 0; i <= chunk.length - len; i++) {
        tokens.add(chunk.slice(i, i + len).toLowerCase());
      }
    }
  }

  // 英文: 完整单词 + 连字符词组
  const enWords = text.match(/[A-Za-z][\w.-]*(?:\s+[A-Za-z][\w.-]*){0,2}/g) || [];
  for (const w of enWords) {
    tokens.add(w.toLowerCase().trim());
    // 也添加单个单词
    for (const single of w.split(/[\s.-]+/)) {
      if (single.length >= 2) tokens.add(single.toLowerCase());
    }
  }

  // v4.9→v6.4: 加权同义词展开 + 否定检测
  let expanded;
  let synonymWeights = null; // 同义词权重映射 (原词 1.0, 主同义词 0.7, 次 0.4)
  try {
    const { expandSynonymsWeighted } = require('./synonym-expander.js');
    const result = expandSynonymsWeighted(tokens);
    expanded = result.expanded;
    synonymWeights = result.weights;
  } catch {
    expanded = tokens;
  }
  const negatedTokens = new Set();
  const _w = text.toLowerCase().split(/[\s,]+/);
  for (let _i = 0; _i < _w.length; _i++) {
    if (NEGATION_WORDS.has(_w[_i])) {
      for (let _j = 1; _j <= 3 && _i + _j < _w.length; _j++) {
        if (_w[_i + _j].length >= 2) negatedTokens.add(_w[_i + _j]);
      }
    }
  }
  Object.defineProperty(expanded, '_negatedTokens', {
    value: negatedTokens, enumerable: false, configurable: true
  });
  // v6.4: 挂载同义词权重映射，供 scoreSkill 使用
  Object.defineProperty(expanded, '_synonymWeights', {
    value: synonymWeights, enumerable: false, configurable: true
  });
  return expanded;
}

// === BM25 参数构建 (v5.8 P1-A: 分段 IDF 归一化) ===
const IDF_FLOOR = Math.log(2); // ≈0.693，防止 IDF 趋零

// 加载 domain 映射 (技能→domain 的反向索引)
let _domainMap = null;
function loadDomainMap() {
  if (_domainMap) return _domainMap;
  try {
    const mapFile = path.join(CLAUDE_ROOT, 'scripts', 'skill-domain-map.json');
    if (fs.existsSync(mapFile)) {
      const raw = JSON.parse(fs.readFileSync(mapFile, 'utf8'));
      // 构建 skillName → domainName 反向索引
      _domainMap = new Map();
      for (const [domain, skills] of Object.entries(raw.domains || {})) {
        for (const skill of skills) {
          _domainMap.set(skill, domain);
        }
      }
      return _domainMap;
    }
  } catch {}
  _domainMap = new Map();
  return _domainMap;
}

function buildBM25Params(index) {
  const skills = index.skills || [];
  const N = skills.length;

  // 计算平均文档长度 (关键词数)
  let totalDl = 0;
  for (const skill of skills) {
    totalDl += (skill.keywords || []).length;
  }
  const avgdl = N > 0 ? totalDl / N : 1;

  // 加载 domain 映射
  const domainMap = loadDomainMap();

  // 按 domain 分组技能
  const domainGroups = new Map(); // domain → [skill]
  for (const skill of skills) {
    const domain = domainMap.get(skill.name) || '_global';
    if (!domainGroups.has(domain)) domainGroups.set(domain, []);
    domainGroups.get(domain).push(skill);
  }

  // 全局 DF
  const df = new Map(); // keyword → 全局出现计数
  for (const skill of skills) {
    const seen = new Set();
    for (const { keyword } of (skill.keywords || [])) {
      const kw = (keyword || "").toLowerCase();
      if (!seen.has(kw)) {
        seen.add(kw);
        df.set(kw, (df.get(kw) || 0) + 1);
      }
    }
  }

  // domain-local DF
  const domainDf = new Map(); // domain → Map<keyword, localDf>
  for (const [domain, groupSkills] of domainGroups) {
    const localDf = new Map();
    for (const skill of groupSkills) {
      const seen = new Set();
      for (const { keyword } of (skill.keywords || [])) {
        const kw = (keyword || "").toLowerCase();
        if (!seen.has(kw)) {
          seen.add(kw);
          localDf.set(kw, (localDf.get(kw) || 0) + 1);
        }
      }
    }
    domainDf.set(domain, localDf);
  }

  // 全局 IDF (带 floor)
  const idf = new Map();
  for (const [kw, docFreq] of df) {
    const rawIdf = Math.log((N - docFreq + 0.5) / (docFreq + 0.5) + 1);
    idf.set(kw, Math.max(rawIdf, IDF_FLOOR));
  }

  // domain-local IDF (per-domain 分段计算)
  // domainIdf: Map<domain, Map<keyword, localIdf>>
  const domainIdf = new Map();
  for (const [domain, localDfMap] of domainDf) {
    const localN = domainGroups.get(domain).length;
    const localIdfMap = new Map();
    for (const [kw, localDocFreq] of localDfMap) {
      const rawIdf = Math.log((localN - localDocFreq + 0.5) / (localDocFreq + 0.5) + 1);
      localIdfMap.set(kw, Math.max(rawIdf, IDF_FLOOR));
    }
    domainIdf.set(domain, localIdfMap);
  }

  return { N, avgdl, idf, df, domainIdf, domainMap, domainGroups };
}

/**
 * BM25 单项评分
 * @param {number} tf - 词频 (匹配权重)
 * @param {number} idf - 逆文档频率
 * @param {number} dl - 文档长度 (技能关键词数)
 * @param {number} avgdl - 平均文档长度
 * @param {number} k1 - 词频饱和参数 (默认 1.2)
 * @param {number} b - 长度归一化参数 (默认 0.75)
 * @returns {number} BM25 分值
 */
function computeBM25Score(tf, idf, dl, avgdl, k1 = 1.5, b = 0.75) {
  const numerator = tf * (k1 + 1);
  const denominator = tf + k1 * (1 - b + b * dl / avgdl);
  return idf * numerator / denominator;
}

// === 冷启动防护 (v5.8 P0-A) ===
const COLD_START_THRESHOLD = 30; // 路由次数低于此值视为冷启动
const COLD_START_MAX_BOOST = 0.08; // 冷启动最大 boost 值 (67 skills 场景，降低避免翻转)
const EPSILON_EXPLORE = 0.10; // epsilon-greedy 探索概率

/**
 * 对冷启动技能施加线性衰减 boost
 * boost = MAX_BOOST * (1 - routeCount / THRESHOLD)
 * 当 routeCount >= THRESHOLD 时 boost = 0
 *
 * @param {Array} results - 排序后的评分结果 [{name, score, ...}]
 * @param {Map<string, number>} routeStats - 技能路由次数统计
 * @returns {{ results: Array, boostedSkills: string[] }}
 */
function applyColdStartBoost(results, routeStats) {
  const boostedSkills = [];

  // 保护基准: 消歧 top 优先，否则用 BM25 原始 top-1
  const disambTop = results.find(r => r.disambiguated);
  const originalTop = results[0]; // BM25 排序后的 top-1

  for (const r of results) {
    if (r.score <= 0) continue; // 只 boost 有基础分的技能
    const count = routeStats.get(r.name) || 0;
    if (count < COLD_START_THRESHOLD) {
      const boost = COLD_START_MAX_BOOST * (1 - count / COLD_START_THRESHOLD);
      const topScore = results[0]?.score || 1;
      const newScore = r.score + boost * topScore;

      // 保护 1: 冷启动 boost 不得超过消歧确认的 top 技能
      if (disambTop && !r.disambiguated && newScore > disambTop.score) {
        r.score = disambTop.score * 0.98;
        r.coldStartCapped = true;
      // 保护 2: 冷启动 boost 不得让非 top-1 技能跃居 top-1 之上
      } else if (originalTop && r !== originalTop && newScore > originalTop.score) {
        r.score = originalTop.score * 0.99;
        r.coldStartCapped = true;
      } else {
        r.score = newScore;
      }
      r.coldStartBoost = boost;
      boostedSkills.push(r.name);
    }
  }

  // 重新排序
  results.sort((a, b) => b.score - a.score);
  return { results, boostedSkills };
}

/**
 * Epsilon-greedy 探索: 以 EPSILON 概率从 top-K 中随机选择
 * 与已有 route-ab-test.js (Thompson Sampling) 互补:
 *   - AB test: 仅在 top-2 置信差 <15% 时触发
 *   - Epsilon-greedy: 无条件以 10% 概率探索 top-5
 *
 * @param {Array} candidates - top-K 候选
 * @param {number} epsilon - 探索概率
 * @returns {{ selected: Object, explored: boolean }}
 */
function epsilonGreedySelect(candidates, epsilon = EPSILON_EXPLORE) {
  if (!candidates || candidates.length < 2) {
    return { selected: candidates?.[0] || null, explored: false };
  }

  if (Math.random() < epsilon) {
    // 从 top-5 中随机选一个 (非 top-1)
    const pool = candidates.slice(1, Math.min(5, candidates.length));
    if (pool.length > 0) {
      const idx = Math.floor(Math.random() * pool.length);
      return { selected: pool[idx], explored: true };
    }
  }

  return { selected: candidates[0], explored: false };
}

// === 学习权重加载 ===
let _learnedWeights = null;
function loadLearnedWeights() {
  if (_learnedWeights !== null) return _learnedWeights;
  try {
    if (fs.existsSync(WEIGHTS_FILE)) {
      _learnedWeights = JSON.parse(fs.readFileSync(WEIGHTS_FILE, 'utf8'));
      return _learnedWeights;
    }
  } catch {}
  _learnedWeights = {};
  return _learnedWeights;
}

// === 旧版评分 (向后兼容) ===
function legacyScoreSkill(skill, queryTokens) {
  let totalScore = 0;
  let matchedKeywords = [];

  const weights = loadLearnedWeights();
  const skillDeltas = (weights.deltas || {})[skill.name] || {};

  for (const { keyword, weight } of skill.keywords) {
    const kwLower = (keyword || "").toLowerCase();
    const delta = skillDeltas[kwLower] || 0;
    const adjustedWeight = Math.max(0.1, weight + delta);

    if (queryTokens.has(kwLower)) {
      totalScore += adjustedWeight;
      matchedKeywords.push({ keyword, weight: adjustedWeight, matchType: 'exact' });
      continue;
    }

    for (const token of queryTokens) {
      if (token.length >= 3 && kwLower.includes(token)) {
        totalScore += adjustedWeight * 0.6;
        matchedKeywords.push({ keyword, weight: adjustedWeight * 0.6, matchType: 'partial' });
        break;
      }
      if (kwLower.length >= 3 && token.includes(kwLower)) {
        totalScore += adjustedWeight * 0.6;
        matchedKeywords.push({ keyword, weight: adjustedWeight * 0.6, matchType: 'partial' });
        break;
      }
    }
  }

  return { totalScore, matchedKeywords };
}

// === BM25 匹配评分 (v5.8 P1-A: blended IDF) ===
const IDF_BLEND_GLOBAL = 0.4;  // 全局 IDF 权重
const IDF_BLEND_DOMAIN = 0.6;  // domain-local IDF 权重

function scoreSkill(skill, queryTokens, bm25Params, invertedIndex) {
  // 向后兼容: 无 BM25 参数时回退旧逻辑
  if (!bm25Params) return legacyScoreSkill(skill, queryTokens);

  let totalScore = 0;
  let matchedKeywords = [];

  // v6.4 MEDIUM-3: 读取否定 token 集合，命中否定的关键词施加反向惩罚
  const negatedTokens = queryTokens._negatedTokens || new Set();
  // v6.4 MEDIUM-4: 读取同义词权重映射，对同义词匹配施加衰减
  const synonymWeights = queryTokens._synonymWeights || null;

  const weights = loadLearnedWeights();
  const skillDeltas = (weights.deltas || {})[skill.name] || {};
  const dl = (skill.keywords || []).length;
  const { avgdl, idf: idfMap, domainIdf, domainMap } = bm25Params;

  // 获取当前技能所属 domain 的 local IDF
  const skillDomain = domainMap ? (domainMap.get(skill.name) || '_global') : '_global';
  const localIdfMap = (domainIdf && domainIdf.get(skillDomain)) || null;

  // v6.3: 倒排索引优化 — 预计算精确匹配集合
  let exactMatchSet = null;
  if (invertedIndex) {
    exactMatchSet = new Set();
    for (const token of queryTokens) {
      const postings = invertedIndex.get(token);
      if (postings) {
        // postings 是 Set<skillIndex>，需要反查技能名
        // 但 invertedIndex 存的是 keyword→Set<skillIndex>
        // 我们直接检查当前 token 是否在此技能的关键词中
        exactMatchSet.add(token);
      }
    }
  }

  for (const kwEntry of skill.keywords) {
    const kwLower = (kwEntry.keyword || "").toLowerCase();
    const delta = skillDeltas[kwLower] || 0;
    // 使用 tfidfWeight 如果可用，否则 fallback 到 weight
    const baseWeight = kwEntry.tfidfWeight || kwEntry.weight;
    const adjustedWeight = Math.max(0.1, baseWeight + delta);

    // v5.8: blended IDF — 全局×0.4 + domain-local×0.6
    // tfidfWeight 已含编译期 IDF，施加校正因子而非直接替代
    let kwIDF;
    if (kwEntry.tfidfWeight) {
      // 编译期 tfidfWeight 有效时: 计算校正因子
      // 全局 IDF 退化时，domain-local IDF 补偿
      const globalIdf = idfMap.get(kwLower) || IDF_FLOOR;
      const localIdf = (localIdfMap && localIdfMap.get(kwLower)) || globalIdf;
      const blendedIdf = globalIdf * IDF_BLEND_GLOBAL + localIdf * IDF_BLEND_DOMAIN;
      // 校正因子 = blended / globalIdf (当 globalIdf 退化时 > 1，补偿)
      const correction = globalIdf > 0 ? blendedIdf / globalIdf : 1;
      kwIDF = Math.max(correction, 0.5); // V10 修复: 允许校正因子 <1 (下限 0.5)，消除小域系统性加分偏差
    } else {
      // 无预计算: 直接用 blended IDF
      const globalIdf = idfMap.get(kwLower) || 0;
      const localIdf = (localIdfMap && localIdfMap.get(kwLower)) || globalIdf;
      kwIDF = globalIdf * IDF_BLEND_GLOBAL + localIdf * IDF_BLEND_DOMAIN;
      kwIDF = Math.max(kwIDF, IDF_FLOOR);
    }

    // 精确匹配
    if (queryTokens.has(kwLower)) {
      let bm25 = computeBM25Score(adjustedWeight, kwIDF, dl, avgdl);
      // v6.4 MEDIUM-4: 同义词权重衰减 — 非原词的同义词匹配按权重缩放
      if (synonymWeights && synonymWeights.has(kwLower)) {
        bm25 *= synonymWeights.get(kwLower);
      }
      // v6.4 MEDIUM-3: 否定惩罚 — 被否定的 token 反向计分
      if (negatedTokens.has(kwLower)) {
        bm25 *= -0.3;
      }
      totalScore += bm25;
      matchedKeywords.push({ keyword: kwEntry.keyword, weight: bm25, matchType: negatedTokens.has(kwLower) ? 'negated' : 'exact' });
      continue;
    }

    // 包含匹配 (折扣 0.6)
    for (const token of queryTokens) {
      if (token.length >= 3 && kwLower.includes(token)) {
        let bm25 = computeBM25Score(adjustedWeight * 0.6, kwIDF, dl, avgdl);
        // v6.4: 同义词权重衰减
        if (synonymWeights && synonymWeights.has(token)) {
          bm25 *= synonymWeights.get(token);
        }
        // v6.4: 否定惩罚
        if (negatedTokens.has(token)) {
          bm25 *= -0.3;
        }
        totalScore += bm25;
        matchedKeywords.push({ keyword: kwEntry.keyword, weight: bm25, matchType: negatedTokens.has(token) ? 'negated' : 'partial' });
        break;
      }
      if (kwLower.length >= 3 && token.includes(kwLower)) {
        let bm25 = computeBM25Score(adjustedWeight * 0.6, kwIDF, dl, avgdl);
        if (synonymWeights && synonymWeights.has(token)) {
          bm25 *= synonymWeights.get(token);
        }
        if (negatedTokens.has(token)) {
          bm25 *= -0.3;
        }
        totalScore += bm25;
        matchedKeywords.push({ keyword: kwEntry.keyword, weight: bm25, matchType: negatedTokens.has(token) ? 'negated' : 'partial' });
        break;
      }
    }
  }

  // v5.9.1: 长期休眠技能降权 (coldPenalty 由 generate-skill-index 标记)
  if (skill.coldPenalty && totalScore > 0) {
    totalScore *= skill.coldPenalty;
  }

  // v6.3: 超大关键词列表技能降权 — 防止 gstack 导入技能的大量泛化关键词淹没真正专家技能
  // 技能关键词数 > 80 且 maturity=unknown 视为低信噪比技能，施加对数衰减降权
  if (skill.maturity === 'unknown' && dl > 80 && totalScore > 0) {
    // 对数衰减: 80 kw → 1.0, 120 kw → 0.37, 200 kw → 0.17
    const penalty = Math.max(0.1, 80 / dl);
    totalScore *= penalty;
  }

  return { totalScore, matchedKeywords };
}

// === 上下文感知融合评分 (v5.0) ===
/**
 * 融合 BM25 + 上下文 + 项目类型 + 工作流模式
 * 权重: BM25 0.6 + context 0.2 + project 0.1 + workflow 0.1
 * @param {number} bm25Score - BM25 原始分数
 * @param {number} contextScore - 上下文分数 (0~1)
 * @param {number} projectBoost - 项目类型加成 (0~...)
 * @param {number} workflowScore - 工作流预测分数 (0~1)
 * @returns {number} 融合后的分数
 */
/** @deprecated CLI fallback only. Use route-interceptor-bundle fusion weights. */
function contextAwareScore(bm25Score, contextScore, projectBoost, workflowScore) {
  // 修复: 线性加权融合，上下文信号独立于 BM25 分数
  // 上下文信号使用固定基准值缩放，确保对排名有实质影响
  const CTX_BASE = 5.0;
  return bm25Score * 0.6
    + contextScore * CTX_BASE * 0.2
    + projectBoost * CTX_BASE * 0.1
    + workflowScore * CTX_BASE * 0.1;
}

// === Top-k Reranking (v5.8 P1-B) ===
/**
 * BM25 初筛后对 top-k 结果精排
 *
 * 三个精排信号:
 *   1. Jaccard overlap — 查询 tokens 与技能 core 关键词的重叠率
 *   2. Tier bonus     — core 关键词匹配 ×1.5, extended ×1.0
 *   3. Gap penalty    — top-1 与 top-2 差距过小时收紧排名
 *
 * @param {Array} results - BM25 排序后的结果 (已含 matchedKeywords)
 * @param {Set} queryTokens - 用户查询 tokens
 * @param {Object} index - 技能索引
 * @param {number} k - rerank 窗口大小 (默认 10)
 * @returns {Array} 精排后的结果
 */
function rerankTopK(results, queryTokens, index, k = 10) {
  if (!results || results.length < 2 || !queryTokens) return results;

  const topK = results.slice(0, k);
  const rest = results.slice(k);

  // 构建技能 core keywords 快速查找
  const skillCoreKws = new Map();
  for (const skill of (index.skills || [])) {
    const coreSet = new Set();
    const allSet = new Set();
    for (const kw of (skill.keywords || [])) {
      const kwLower = (kw.keyword || "").toLowerCase();
      allSet.add(kwLower);
      if (kw.tier === 'core') coreSet.add(kwLower);
    }
    skillCoreKws.set(skill.name, { core: coreSet, all: allSet });
  }

  for (const r of topK) {
    const kwData = skillCoreKws.get(r.name);
    if (!kwData) continue;

    // 信号 1: Jaccard overlap (查询 vs 技能 core 关键词)
    let intersect = 0, unionSize = kwData.core.size;
    for (const token of queryTokens) {
      if (kwData.core.has(token)) intersect++;
      if (!kwData.all.has(token)) unionSize++;
    }
    const jaccard = unionSize > 0 ? intersect / unionSize : 0;

    // 信号 2: Tier bonus — 统计 matchedKeywords 中 core 占比
    let coreMatches = 0, totalMatches = (r.matchedKeywords || []).length;
    for (const mk of (r.matchedKeywords || [])) {
      if (kwData.core.has((mk.keyword || "").toLowerCase())) coreMatches++;
    }
    const tierRatio = totalMatches > 0 ? coreMatches / totalMatches : 0;

    // rerank score = 原始 BM25 × (1 + jaccard×0.3 + tierRatio×0.2)
    // 消歧 boosted 技能受保护: rerank 不降低其排名
    /* L1c-RERANK-ARBITRATION-AWARE-2026-04-25 */
    const rerankMultiplier = 1 + jaccard * 0.3 + tierRatio * 0.2;
    // L1c: L1b 仲裁 loser (_arbitratedBy 标记) 不享受保护, 且 multiplier 硬 cap 到 1.0
    // 防止被 rerank boost 反超已被 cap 到 winner*0.95 的位置
    const _isArbLoser = !!r._arbitratedBy;
    if (r.disambiguated && !_isArbLoser) {
      // 消歧 winner: 只允许 rerank 增强，不允许被其他技能超越
      r.score = r.score * Math.max(rerankMultiplier, 1.0);
      r._rerankProtected = true;
    } else if (_isArbLoser) {
      // 仲裁 loser: 严格不放大, 仅允许收紧 (jaccard/tier 真低分自然降级 OK)
      const _capped = Math.min(rerankMultiplier, 1.0);
      r.score = r.score * _capped;
      r._rerankBoost = _capped;
      continue;
    } else {
      r.score = r.score * rerankMultiplier;
    }
    r._rerankBoost = rerankMultiplier;
  }

  // 消歧保护 cap: 非消歧技能不得超越消歧 winner
  // L1c: cap 基线必须是真 winner (disambiguated && !_arbitratedBy);
  // 跨域仲裁 loser 虽然 disambiguated=true, 但被 L1b cap 到 winner*0.95,
  // 不可作为 cap 基线 (否则真 winner 会被反向 cap)
  const disambTop = topK.find(r => r.disambiguated && !r._arbitratedBy);
  if (disambTop) {
    for (const r of topK) {
      if (r === disambTop) continue;
      // 仲裁 loser 也参与 cap: 它的 disambiguated 是历史标记, 不豁免
      if (r.score > disambTop.score) {
        r.score = disambTop.score * 0.98;
        r._rerankCapped = true;
      }
    }
  }

  // 信号 3: Gap penalty — top-1 与 top-2 差距 < 5% 时不改变排名
  topK.sort((a, b) => b.score - a.score);

  return topK.concat(rest);
}

function normalizeScores(results) {
  if (!results || results.length === 0) return results || [];
  const maxScore = results[0]?.score;
  if (maxScore === 0) return results;

  return results.map(r => ({
    ...r,
    confidence: Math.min(Math.round(r.score / maxScore * 100) / 100, 1.0),
  }));
}

// === 路由审计日志 ===
function logRoute(query, results) {
  try {
    if (!fs.existsSync(DEBUG_DIR)) fs.mkdirSync(DEBUG_DIR, { recursive: true });
    const dateStr = new Date().toISOString().slice(0, 10);
    const logFile = path.join(DEBUG_DIR, `route-${dateStr}.jsonl`);
    const entry = {
      ts: new Date().toISOString(),
      query: query.slice(0, 200),
      topResult: results[0]?.name || 'none',
      topConfidence: results[0]?.confidence || 0,
      candidates: results.slice(0, 5).map(r => ({ name: r.name, confidence: r.confidence })),
    };
    fs.appendFileSync(logFile, JSON.stringify(entry) + '\n');
  } catch {}
}

// === composable 协作推荐 ===
function getComposable(index, skillName) {
  const skill = index.skills.find(s => s.name === skillName);
  return skill?.composable || {};
}

function buildComposableHints(index, topResults) {
  if (topResults.length === 0) return [];
  const top = topResults[0];
  const comp = getComposable(index, top.name);
  const hints = [];

  // enhances: 本技能可增强的其他技能
  if (comp.enhances?.length > 0) {
    for (const name of comp.enhances) {
      // 只推荐存在于索引中的技能
      if (index.skills.some(s => s.name === name)) {
        hints.push({ skill: name, relation: 'enhances', from: top.name });
      }
    }
  }

  // requires: 前置依赖技能
  if (comp.requires?.length > 0) {
    for (const name of comp.requires) {
      if (index.skills.some(s => s.name === name)) {
        hints.push({ skill: name, relation: 'requires', from: top.name });
      }
    }
  }

  // conflicts: 不宜同时使用
  if (comp.conflicts?.length > 0) {
    for (const name of comp.conflicts) {
      if (index.skills.some(s => s.name === name)) {
        hints.push({ skill: name, relation: 'conflicts', from: top.name });
      }
    }
  }

  return hints;
}

// === 冲突消歧规则引擎 (v5.3 三层防线, v5.5 P4 外部化) ===
// 规则数据从 disambiguation-rules.json 加载，trigger 字符串编译为 RegExp
function loadDisambiguationRules() {
  try {
    const rulesPath = path.join(__dirname, 'disambiguation-rules.json');
    const raw = JSON.parse(fs.readFileSync(rulesPath, 'utf8'));
    return raw.rules.map(r => ({
      id: r.id,
      trigger: new RegExp(r.trigger, 'i'),
      boost: r.boost,
      penalty: r.penalty,
      weight: r.weight,
      mutual_exclusion: r.mutual_exclusion,
    }));
  } catch (e) {
    // 加载失败时返回空数组，优雅降级
    if (typeof process !== 'undefined' && process.stderr) {
      process.stderr.write(`[route-analyzer] 消歧规则加载失败: ${e.message}\n`);
    }
    return [];
  }
}
const DISAMBIGUATION_RULES = loadDisambiguationRules();

/**
 * 计算规则 specificity: regex 中固定字符占比越高越具体
 * @param {string} triggerSource - regex 源字符串
 * @returns {number} 0~1 之间的 specificity 值
 */
function computeRuleSpecificity(triggerSource) {
  if (!triggerSource) return 0.5;
  // 固定字符 = 非元字符 (非 . * + ? | [ ] ( ) { } ^ $ \)
  const fixed = (triggerSource.match(/[a-zA-Z0-9\u4e00-\u9fff_-]/g) || []).length;
  const total = triggerSource.length;
  return total > 0 ? Math.min(1, fixed / total) : 0.5;
}

/**
 * 对评分结果应用消歧规则 (v5.8 重构: 全量匹配 + 加权投票 + specificity)
 *
 * 改进点 (vs v5.7):
 *   1. 所有规则全量匹配，收集投票后统一应用
 *   2. 每条规则的有效权重 = weight × specificity (越具体的规则影响越大)
 *   3. boost/penalty 分别累积，最终一次性合并到分值
 *   4. 记录触发的规则 ID 供遥测消费
 *
 * @param {Array} results - 排序后的评分结果
 * @param {string} queryText - 原始查询文本
 * @param {Object} index - skills-index
 * @returns {{ results: Array, firedRules: string[] }} 消歧后的结果 + 触发的规则
 */
// // L1-AGENT-VIRTUAL-INJECTION-HELPER 加载 ~/.claude/agents/*.md 构建 agent 白名单 (惰性 + 缓存)
let _agentNamesCache = null;
function _loadAgentNamesCached() {
  if (_agentNamesCache !== null) return _agentNamesCache;
  try {
    const _agentDir = path.join(CLAUDE_ROOT, 'agents');
    if (!fs.existsSync(_agentDir)) {
      _agentNamesCache = new Set();
      return _agentNamesCache;
    }
    const _files = fs.readdirSync(_agentDir);
    const _names = new Set();
    for (const _f of _files) {
      if (_f.endsWith('.md') && !_f.startsWith('_')) {
        _names.add(_f.slice(0, -3));
      }
    }
    _agentNamesCache = _names;
  } catch (_e) {
    _agentNamesCache = new Set(); // fail-close: 空集等价于关闭虚拟注入
  }
  return _agentNamesCache;
}

function applyDisambiguation(results, queryText, index) {
  if (results.length < 2) return { results, firedRules: [] };

  const queryLower = queryText.toLowerCase();
  const firedRules = [];

  // L1-AGENT-VIRTUAL-INJECTION (2026-04-25 D1 缺陷根治)
  // 在投票阶段开始前, 为 agent-only boost 规则注入虚拟 results 条目,
  // 使后续 boost/penalty/排名强制能正常作用于 agent (skills-index 不含 agent)。
  // Fail-close: 加载失败仅打印警告, 不阻断主流程。
  try {
    const _agentNames = _loadAgentNamesCached();
    if (_agentNames && _agentNames.size > 0 && results.length > 0) {
      const _maxScore = Math.max.apply(null, results.map(function(r){return r.score||0;}).concat([0.001]));
      const _existingNames = new Set(results.map(function(r){return r.name;}));
      const _candidateAgents = new Set();
      for (const _rule of DISAMBIGUATION_RULES) {
        if (!_rule.trigger.test(queryText.toLowerCase())) continue;
        if (_rule.boost && _agentNames.has(_rule.boost) && !_existingNames.has(_rule.boost)) {
          _candidateAgents.add(_rule.boost);
        }
      }
      for (const _agentName of _candidateAgents) {
        results.push({
          name: _agentName,
          score: _maxScore * 0.6,
          _virtual: true,
          _isAgent: true,
          matched: [],
          weights: {}
        });
      }
    }
  } catch (_e) {
    try { process.stderr.write('[route-analyzer] L1 virtual-agent injection skipped: ' + (_e && _e.message ? _e.message : String(_e)) + '\n'); } catch (_) {}
  }

  // Phase 1: 收集所有匹配规则的投票
  const boostVotes = new Map();   // skillName → 累积 boost 增量
  const penaltyVotes = new Map(); // skillName → 累积 penalty 增量

  for (const rule of DISAMBIGUATION_RULES) {
    if (!rule.trigger.test(queryLower)) continue;

    firedRules.push(rule.id);

    // specificity 加权: regex 越具体，权重越高
    const specificity = computeRuleSpecificity(rule.trigger.source);
    const effectiveWeight = rule.weight * (0.5 + specificity * 0.5); // 基础 50% + specificity 50%

    // 累积 boost 投票
    const boosted = results.find(r => r.name === rule.boost && r.score > 0);
    if (boosted) {
      const current = boostVotes.get(rule.boost) || 0;
      boostVotes.set(rule.boost, Math.max(current, effectiveWeight)); // 取最大值防止叠加虚高
    } else if (rule.boost) {
      // v1.8 submit: 规则匹配但目标 skill 不在 BM25 结果中 → 注入虚拟条目
      const maxScore = results.length > 0 ? Math.max(...results.map(r => r.score || 0)) : 0.001;
      results.push({
        name: rule.boost,
        score: maxScore * 0.5,  // 基准分 = 最高分 * 50%
        _submitted: true,
        _ruleId: rule.id,
        matched: [],
        weights: {}
      });
      boostVotes.set(rule.boost, effectiveWeight);
    }

    // 累积 penalty 投票
    for (const penName of rule.penalty) {
      const current = penaltyVotes.get(penName) || 0;
      penaltyVotes.set(penName, Math.max(current, effectiveWeight * 0.5)); // penalty 折半
    }
  }

  // Phase 1.5: mutual_exclusion 互斥消解 (RL-V14)
  for (const rule of DISAMBIGUATION_RULES) {
    if (!rule.mutual_exclusion || !firedRules.includes(rule.id)) continue;
    const conflictWith = rule.mutual_exclusion.with;
    if (firedRules.includes(conflictWith)) {
      if (rule.mutual_exclusion.on_keyword) {
        const keywordRe = new RegExp(rule.mutual_exclusion.on_keyword, 'i');
        if (keywordRe.test(queryLower) && rule.boost) {
          boostVotes.delete(rule.boost);
        }
      }
    }
  }

  // Phase 2: 统一应用投票结果
  for (const r of results) {
    if (r.score <= 0) continue;

    // 记录原始分数 (用于审计)
    if (!r._baseScore) r._baseScore = r.score;

    const boost = boostVotes.get(r.name) || 0;
    const penalty = penaltyVotes.get(r.name) || 0;

    if (boost > 0) {
      r.score = r._baseScore * (1 + boost);
      r.disambiguated = true;
    }
    if (penalty > 0 && !r.disambiguated) {
      // 仅在技能未被 boost 时施加 penalty
      r.score = r._baseScore * (1 - penalty * 0.3);
      r.penalized = true;
    }
  }

  // L1b-CROSS-BOOST-ARBITRATION (2026-04-25)
  // Phase 2.5: 跨域 boost 仲裁 — 防止两条 fired rule 各自 boost 不同 skill
  // 但相互不在对方 penalty 列表中 (Phase 3 不介入), 导致基线分数高的胜出.
  // 顺序无关: 仅依赖 boostVotes + 规则静态属性, 不依赖遍历次序.
  try {
    if (boostVotes.size >= 2) {
      const _boostMeta = new Map();
      for (const _rule of DISAMBIGUATION_RULES) {
        if (!firedRules.includes(_rule.id)) continue;
        if (!_rule.boost || !boostVotes.has(_rule.boost)) continue;
        const _spec = computeRuleSpecificity(_rule.trigger.source);
        const _w = (_rule.weight || 0) * (0.5 + _spec * 0.5);
        const _prev = _boostMeta.get(_rule.boost);
        if (!_prev || _w > _prev.weight) {
          _boostMeta.set(_rule.boost, {
            weight: _w,
            ruleId: _rule.id,
            penaltySet: new Set(_rule.penalty || [])
          });
        }
      }
      if (_boostMeta.size >= 2) {
        const _ranked = Array.from(_boostMeta.entries())
          .sort((a, b) => b[1].weight - a[1].weight);
        const [_winnerName, _winnerMeta] = _ranked[0];
        const _winner = results.find(r => r.name === _winnerName && r.score > 0);
        if (_winner) {
          for (let _i = 1; _i < _ranked.length; _i++) {
            const [_loserName, _loserMeta] = _ranked[_i];
            const _crossPenalty = _winnerMeta.penaltySet.has(_loserName)
                              || _loserMeta.penaltySet.has(_winnerName);
            if (_crossPenalty) continue;
            const _loser = results.find(r => r.name === _loserName && r.score > 0);
            if (!_loser) continue;
            const _ratio = Math.max(0.6, _loserMeta.weight / Math.max(_winnerMeta.weight, 1e-6));
            const _newScore = _loser.score * _ratio;
            _loser.score = Math.min(_newScore, _winner.score * 0.95);
            _loser._arbitratedBy = _winnerMeta.ruleId;
            _loser._arbitrationRatio = Math.round(_ratio * 1000) / 1000;
          }
        }
      }
    }
  } catch (_e) {
    try { process.stderr.write('[route-analyzer] L1b cross-boost arbitration skipped: ' + (_e && _e.message ? _e.message : String(_e)) + '\n'); } catch (_) {}
  }

  // Phase 3: 排名强制 — boosted 技能必须排在其 penalized 对手前面
  for (const rule of DISAMBIGUATION_RULES) {
    if (!firedRules.includes(rule.id)) continue;
    const boosted = results.find(r => r.name === rule.boost && r.disambiguated);
    if (!boosted) continue;
    for (const r of results) {
      if (rule.penalty.includes(r.name) && r.score > boosted.score) {
        r.score = boosted.score * 0.95;
        r.penalizedBy = rule.boost;
      }
    }
  }

  // 重新排序
  results.sort((a, b) => b.score - a.score);
  return { results, firedRules };
}

// === 主流程 ===
function main() {
  parseArgs();
  if (!query) {
    console.error('Usage: node route-analyzer.js [--json] [--log] [--top N] "<query>"');
    process.exit(1);
  }
  const index = loadIndex();
  const queryTokens = tokenize(query);

  // v4.9: 构建 BM25 参数
  const bm25Params = buildBM25Params(index);

  // v5.0: 加载上下文信号 (优雅降级)
  let composableIdx = {}, contextScores = {}, projectBoosts = {}, workflowPrediction = null;
  try {
    const ct = require('./context-tracker.js');
    composableIdx = ct.buildComposableIndex(index);
    const ctxState = ct.loadState(); // 一次性加载，避免 68 次 I/O
    for (const skill of index.skills) {
      contextScores[skill.name] = ct.computeContextScore(skill.name, composableIdx, ctxState);
    }
  } catch {}
  try {
    const pd = require('./project-detector.js');
    projectBoosts = pd.getProjectBoost(process.cwd());
  } catch {}
  try {
    const wp = require('./workflow-patterns.js');
    const events = wp.loadActivityLogs(30);
    const sessions = wp.extractSkillSequences(events, 30);
    const patterns = wp.minePatterns(sessions, 2);
    workflowPrediction = patterns;
  } catch {}

  // 评分所有技能
  // v6.3: 构建倒排索引加速精确匹配
  const invertedIndex = buildInvertedIndex(index);
  const results = index.skills.map(skill => {
    const { totalScore, matchedKeywords } = scoreSkill(skill, queryTokens, bm25Params, invertedIndex);

    // v5.0: 上下文融合
    const ctxScore = contextScores[skill.name] || 0;
    const projBoost = projectBoosts[skill.name] || 0;
    let wfScore = 0;
    if (workflowPrediction) {
      // 从 bigrams 检查当前技能是否为预测后继
      for (const [key, count] of Object.entries(workflowPrediction.bigrams || {})) {
        const [, to] = key.split('→');
        if (to === skill.name) { wfScore = Math.min(1, count * 0.1); break; }
      }
    }

    // 修复: 上下文信号可独立贡献，不再要求 BM25 > 0
    const finalScore = (totalScore > 0 || ctxScore > 0 || projBoost > 0 || wfScore > 0)
      ? contextAwareScore(totalScore, ctxScore, projBoost, wfScore)
      : 0;

    return {
      name: skill.name,
      maturity: skill.maturity,
      score: Math.round(finalScore * 100) / 100,
      matchedKeywords: matchedKeywords
        .sort((a, b) => b.weight - a.weight)
        .slice(0, 8),
    };
  }).sort((a, b) => b.score - a.score);

  // v5.3: 冲突消歧 (三层防线第 3 层)
  const { results: disambiguated, firedRules } = applyDisambiguation(results, query, index);

  // v5.8 P1-B: top-k reranking 精排
  const reranked = rerankTopK(disambiguated, queryTokens, index, 10);

  // 归一化置信度
  const normalized = normalizeScores(reranked).slice(0, topK);

  // composable 协作推荐
  const composableHints = buildComposableHints(index, normalized);

  // 路由审计日志
  if (logMode) {
    logRoute(query, normalized);
  }

  // 输出
  if (jsonMode) {
    const output = {
      query,
      tokens: Array.from(queryTokens),
      results: normalized,
      recommendation: getRecommendation(normalized),
    };
    if (composableHints.length > 0) {
      output.composable = composableHints;
    }
    console.log(JSON.stringify(output, null, 2));
  } else {
    renderCli(normalized, composableHints);
  }
}

function getRecommendation(results) {
  if (results.length === 0) return { action: 'fallback', skill: 'developer-expert' };

  const top = results[0];
  if (top.confidence >= 0.8 && results.length > 1 && results[1].confidence < 0.6) {
    return { action: 'route', skill: top.name, confidence: top.confidence };
  }
  if (top.confidence >= 0.5) {
    return {
      action: 'recommend',
      primary: top.name,
      candidates: results.filter(r => r.confidence >= 0.3).map(r => r.name),
    };
  }
  return { action: 'fallback', skill: 'developer-expert' };
}

function renderCli(results, composableHints = []) {
  console.log(`\nQuery: "${query}"\n`);

  if (results.length === 0) {
    console.log('  No matches found. Fallback: developer-expert');
    return;
  }

  const maxScore = results[0].score || 1;
  for (const [i, r] of results.entries()) {
    const barLen = Math.round(r.confidence * 20);
    const bar = '\u2588'.repeat(barLen) + '\u2591'.repeat(20 - barLen);
    const level = r.confidence >= 0.8 ? 'HIGH' : r.confidence >= 0.5 ? 'MED ' : 'LOW ';
    const marker = i === 0 ? ' <--' : '';
    console.log(`  ${String(i + 1).padStart(2)}. ${r.name.padEnd(30)} ${bar} ${(r.confidence * 100).toFixed(0).padStart(3)}% [${level}]${marker}`);

    // 显示匹配关键词
    if (r.matchedKeywords.length > 0) {
      const kwStr = r.matchedKeywords.slice(0, 5).map(k => k.keyword).join(', ');
      console.log(`      matched: ${kwStr}`);
    }
  }

  // composable 协作提示
  if (composableHints.length > 0) {
    console.log();
    const enhances = composableHints.filter(h => h.relation === 'enhances');
    const requires = composableHints.filter(h => h.relation === 'requires');
    const conflicts = composableHints.filter(h => h.relation === 'conflicts');

    if (enhances.length > 0) {
      console.log(`  Enhances: ${enhances.map(h => h.skill).join(', ')}`);
    }
    if (requires.length > 0) {
      console.log(`  Requires: ${requires.map(h => h.skill).join(', ')}`);
    }
    if (conflicts.length > 0) {
      console.log(`  Conflicts: ${conflicts.map(h => h.skill).join(', ')}`);
    }
  }

  // 建议
  const rec = getRecommendation(results);
  console.log();
  if (rec.action === 'route') {
    console.log(`  Recommendation: ROUTE to ${rec.skill} (${(rec.confidence * 100).toFixed(0)}% confidence)`);
  } else if (rec.action === 'recommend') {
    console.log(`  Recommendation: ${rec.primary} (candidates: ${rec.candidates.join(', ')})`);
  } else {
    console.log(`  Recommendation: FALLBACK to developer-expert`);
  }
  console.log();
}

// 导出核心函数供测试使用
if (typeof module !== 'undefined') {

// === P3-2: 倒排索引 (keyword → skill indices) ===
function buildInvertedIndex(index) {
  const skills = index.skills || [];
  const invertedIdx = new Map(); // keyword → Set<skillIndex>
  for (let i = 0; i < skills.length; i++) {
    for (const { keyword } of (skills[i].keywords || [])) {
      const kw = (keyword || "").toLowerCase();
      if (!invertedIdx.has(kw)) invertedIdx.set(kw, new Set());
      invertedIdx.get(kw).add(i);
    }
  }
  return invertedIdx;
}
  module.exports = {
    tokenize, scoreSkill, legacyScoreSkill, normalizeScores,
    getRecommendation, buildComposableHints, loadLearnedWeights,
    buildBM25Params, computeBM25Score, contextAwareScore,
    applyDisambiguation, DISAMBIGUATION_RULES,
    applyColdStartBoost, epsilonGreedySelect, computeRuleSpecificity, buildInvertedIndex,
    loadDomainMap, IDF_FLOOR, IDF_BLEND_GLOBAL, IDF_BLEND_DOMAIN, rerankTopK,
  };
}

// 仅在直接执行时运行
if (require.main === module) {
  main();
}
