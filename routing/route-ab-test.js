#!/usr/bin/env node
/**
 * 路由 A/B 实验框架 (v5.3)
 *
 * 当路由引擎 top-2 候选分数接近时 (差距 < 15%)，
 * 使用 Thompson Sampling 随机选择，收集隐式反馈，
 * 自动收敛到最优路由。
 *
 * 模块导出:
 *   shouldExperiment(top2) → boolean
 *   selectVariant(skillA, skillB) → { selected, experiment }
 *   recordOutcome(experimentId, skill, outcome) → void
 *   getExperimentStats() → { experiments, convergence }
 *   resolveConverged(minTrials=20) → string[]  (自动定论的技能对)
 */

const fs = require('fs');
const path = require('path');

const detectClaudeRoot = () => require('./paths.config.js').PATHS.root;

const ROOT = detectClaudeRoot();
const DEBUG_DIR = path.join(ROOT, 'debug');
const AB_FILE = path.join(DEBUG_DIR, 'ab-experiments.json');
const AB_LOG = path.join(DEBUG_DIR, 'ab-experiments.jsonl');

// 实验触发阈值: top-2 置信度差距 < 此值时启动实验
const EXPERIMENT_THRESHOLD = 0.15;
// 最小试验次数 (每个变体) 才能判定收敛
const MIN_TRIALS = 20;
// 收敛阈值: 胜率差 > 此值视为收敛
const CONVERGENCE_THRESHOLD = 0.2;

/**
 * 加载 A/B 实验数据
 * @returns {{ pairs: Object }}
 */
function loadExperiments() {
  try {
    if (fs.existsSync(AB_FILE)) {
      return JSON.parse(fs.readFileSync(AB_FILE, 'utf8'));
    }
  } catch {}
  return { pairs: {}, createdAt: new Date().toISOString() };
}

/**
 * 保存 A/B 实验数据
 */
function saveExperiments(data) {
  if (!fs.existsSync(DEBUG_DIR)) fs.mkdirSync(DEBUG_DIR, { recursive: true });
  fs.writeFileSync(AB_FILE, JSON.stringify(data, null, 2) + '\n');
}

/**
 * 生成实验对键 (排序确保 A-B 和 B-A 是同一个实验)
 */
function pairKey(skillA, skillB) {
  return [skillA, skillB].sort().join(':');
}

/**
 * 判断是否应启动 A/B 实验
 * @param {{ name: string, confidence: number }[]} top2 - top-2 路由结果
 * @returns {boolean}
 */
function shouldExperiment(top2) {
  if (!top2 || top2.length < 2) return false;
  const [a, b] = top2;
  if (a.confidence === 0) return false;
  const gap = (a.confidence - b.confidence) / a.confidence;
  return gap < EXPERIMENT_THRESHOLD && b.confidence >= 0.3;
}

/**
 * Thompson Sampling 选择变体
 * 使用 Beta 分布近似: Beta(successes+1, failures+1)
 *
 * @param {string} skillA
 * @param {string} skillB
 * @returns {{ selected: string, experiment: { id: string, pair: string } }}
 */
function selectVariant(skillA, skillB) {
  const data = loadExperiments();
  const key = pairKey(skillA, skillB);

  if (!data.pairs[key]) {
    data.pairs[key] = {
      skills: [skillA, skillB],
      createdAt: new Date().toISOString(),
      stats: {
        [skillA]: { trials: 0, successes: 0 },
        [skillB]: { trials: 0, successes: 0 },
      },
      resolved: null, // 收敛后填入获胜技能名
    };
    saveExperiments(data);
  }

  const pair = data.pairs[key];

  // 已收敛直接返回获胜者
  if (pair.resolved) {
    return {
      selected: pair.resolved,
      experiment: { id: key, pair: key, resolved: true },
    };
  }

  // v5.9: 真 Beta 分布采样 (Gamma 分布法)
  // Beta(alpha, beta) = Gamma(alpha,1) / (Gamma(alpha,1) + Gamma(beta,1))
  const sampleGamma = (shape) => {
    // Marsaglia-Tsang 方法 (shape >= 1)
    // 对 shape < 1 使用 Gamma(shape+1) * U^(1/shape) 变换
    if (shape < 1) {
      return sampleGamma(shape + 1) * Math.pow(Math.random(), 1.0 / shape);
    }
    const d = shape - 1.0 / 3.0;
    const c = 1.0 / Math.sqrt(9.0 * d);
    while (true) {
      let x, v;
      do {
        // Box-Muller 正态分布采样
        const u1 = Math.random();
        const u2 = Math.random();
        x = Math.sqrt(-2.0 * Math.log(u1)) * Math.cos(2.0 * Math.PI * u2);
        v = 1.0 + c * x;
      } while (v <= 0);
      v = v * v * v;
      const u = Math.random();
      if (u < 1.0 - 0.0331 * (x * x) * (x * x)) return d * v;
      if (Math.log(u) < 0.5 * x * x + d * (1.0 - v + Math.log(v))) return d * v;
    }
  };
  const sampleBeta = (s, f) => {
    const alpha = s + 1;
    const beta = f + 1;
    const gA = sampleGamma(alpha);
    const gB = sampleGamma(beta);
    // v5.9: NaN 防护 — 极端情况下 gA+gB=0 返回无信息先验 0.5
    if (gA + gB === 0) return 0.5;
    return gA / (gA + gB);
  };

  const statsA = pair.stats[skillA] || { trials: 0, successes: 0 };
  const statsB = pair.stats[skillB] || { trials: 0, successes: 0 };

  const sampleA = sampleBeta(statsA.successes, statsA.trials - statsA.successes);
  const sampleB = sampleBeta(statsB.successes, statsB.trials - statsB.successes);

  const selected = sampleA >= sampleB ? skillA : skillB;

  return {
    selected,
    experiment: { id: key, pair: key },
  };
}

/**
 * 记录实验结果
 * @param {string} experimentId - 实验对键
 * @param {string} skill - 实际使用的技能
 * @param {'success'|'failure'} outcome - 结果 (success=用户继续使用, failure=用户切换)
 */
function recordOutcome(experimentId, skill, outcome) {
  const data = loadExperiments();
  const pair = data.pairs[experimentId];
  if (!pair) return;

  if (!pair.stats[skill]) {
    pair.stats[skill] = { trials: 0, successes: 0 };
  }
  pair.stats[skill].trials++;
  if (outcome === 'success') pair.stats[skill].successes++;

  saveExperiments(data);

  // 追加日志
  try {
    const entry = {
      ts: new Date().toISOString(),
      experimentId,
      skill,
      outcome,
      stats: pair.stats,
    };
    fs.appendFileSync(AB_LOG, JSON.stringify(entry) + '\n');
  } catch {}
}

/**
 * 获取实验统计
 * @returns {{ totalPairs: number, active: number, resolved: number, pairs: Object }}
 */
function getExperimentStats() {
  const data = loadExperiments();
  const entries = Object.entries(data.pairs);
  return {
    totalPairs: entries.length,
    active: entries.filter(([, v]) => !v.resolved).length,
    resolved: entries.filter(([, v]) => v.resolved).length,
    pairs: data.pairs,
  };
}

/**
 * 自动收敛判定: 试验次数足够且胜率差明显
 * @param {number} minTrials - 每个变体最小试验次数
 * @returns {string[]} 新收敛的实验对键列表
 */
function resolveConverged(minTrials = MIN_TRIALS) {
  const data = loadExperiments();
  const newlyResolved = [];

  for (const [key, pair] of Object.entries(data.pairs)) {
    if (pair.resolved) continue;

    const skills = pair.skills;
    const statsA = pair.stats[skills[0]] || { trials: 0, successes: 0 };
    const statsB = pair.stats[skills[1]] || { trials: 0, successes: 0 };

    // 两个变体都需要足够的试验次数
    if (statsA.trials < minTrials || statsB.trials < minTrials) continue;

    const rateA = statsA.successes / statsA.trials;
    const rateB = statsB.successes / statsB.trials;
    const gap = Math.abs(rateA - rateB);

    if (gap >= CONVERGENCE_THRESHOLD) {
      pair.resolved = rateA > rateB ? skills[0] : skills[1];
      pair.resolvedAt = new Date().toISOString();
      pair.resolvedReason = `胜率差 ${(gap * 100).toFixed(1)}% (${skills[0]}: ${(rateA * 100).toFixed(0)}%, ${skills[1]}: ${(rateB * 100).toFixed(0)}%)`;
      newlyResolved.push(key);
    }
  }

  if (newlyResolved.length > 0) saveExperiments(data);
  return newlyResolved;
}

// 模块导出
if (typeof module !== 'undefined') {
  module.exports = {
    shouldExperiment,
    selectVariant,
    recordOutcome,
    getExperimentStats,
    resolveConverged,
    loadExperiments,
    saveExperiments,
    pairKey,
    EXPERIMENT_THRESHOLD,
    MIN_TRIALS,
    CONVERGENCE_THRESHOLD,
  };
}

// CLI 入口
if (require.main === module) {
  const stats = getExperimentStats();
  console.log('=== A/B 路由实验 ===');
  console.log(`总实验对: ${stats.totalPairs}`);
  console.log(`活跃: ${stats.active}, 已收敛: ${stats.resolved}`);

  for (const [key, pair] of Object.entries(stats.pairs)) {
    const skills = pair.skills;
    const statsA = pair.stats[skills[0]] || { trials: 0, successes: 0 };
    const statsB = pair.stats[skills[1]] || { trials: 0, successes: 0 };
    const rateA = statsA.trials > 0 ? (statsA.successes / statsA.trials * 100).toFixed(0) : '?';
    const rateB = statsB.trials > 0 ? (statsB.successes / statsB.trials * 100).toFixed(0) : '?';
    const status = pair.resolved ? `RESOLVED → ${pair.resolved}` : 'ACTIVE';
    console.log(`\n  ${key} [${status}]`);
    console.log(`    ${skills[0]}: ${statsA.trials} trials, ${rateA}% success`);
    console.log(`    ${skills[1]}: ${statsB.trials} trials, ${rateB}% success`);
  }

  // 尝试收敛
  const resolved = resolveConverged();
  if (resolved.length > 0) {
    console.log(`\n新收敛: ${resolved.join(', ')}`);
  }
}
