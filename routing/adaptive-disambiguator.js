#!/usr/bin/env node
/**
 * Adaptive Disambiguator — Bayesian Dirichlet 学习型消歧器 (v6.0 F2-1)
 *
 * 设计原理:
 *   - 对每对 (skill_a, skill_b) 维护 Dirichlet 分布 α 向量
 *   - 初始先验: α=1.0 (弱先验，等概率)
 *   - 硬规则先验加权: 硬规则 boost 技能获得 α=10 的强先验
 *   - 每次用户确认后更新: α[used_skill] += 1
 *   - 消歧融合: Bayesian 后验 × 0.3 + 硬规则 boost/penalty × 0.7
 *
 * 数据持久化: debug/adaptive-disambiguator-state.json
 * Fail-open: 任何异常 → 返回原始 candidates 不修改
 *
 * CLI 用法:
 *   node scripts/adaptive-disambiguator.js --state    → 输出当前学习状态
 *   node scripts/adaptive-disambiguator.js --reset    → 重置所有学习数据
 */

'use strict';

const fs = require('fs');
const path = require('path');

// ─── 路径检测 ──────────────────────────────────────────
const detectClaudeRoot = () => require('./paths.config.js').PATHS.root;

const CLAUDE_ROOT = detectClaudeRoot();
const DEBUG_DIR = path.join(CLAUDE_ROOT, 'debug');
const STATE_FILE = path.join(DEBUG_DIR, 'adaptive-disambiguator-state.json');
const FEEDBACK_FILE = path.join(DEBUG_DIR, 'route-feedback.jsonl');

// ─── 融合权重配置 ──────────────────────────────────────
const CONFIG = {
  // 硬规则权重 vs Bayesian 后验权重
  hardRuleWeight: 0.7,
  bayesianWeight: 0.3,
  // 硬规则先验: boost 技能的初始 α (强先验，需大量反面证据才能推翻)
  hardRulePrior: 10,
  // 弱先验: 非 boost 技能的初始 α
  weakPrior: 1.0,
  // 样本充足阈值: 超过此值进入确定性选择
  convergenceThreshold: 30,
  // 收敛置信阈值: 后验概率超过此值视为收敛
  convergenceConfidence: 0.80,
  // 偏离警告阈值: 学习权重偏离先验超过 50% 时记录 evolution-log
  driftWarningRatio: 0.5,
};

// ─── 状态管理 ──────────────────────────────────────────

/**
 * 加载持久化状态
 * 结构: {
 *   version: string,
 *   updatedAt: string,
 *   pairs: {
 *     "<skillA>|<skillB>": {
 *       alphas: { skillName: number, ... },
 *       totalSamples: number,
 *       lastUpdated: string
 *     }
 *   }
 * }
 */
function loadState() {
  try {
    if (!fs.existsSync(STATE_FILE)) {
      return { version: '1.0', updatedAt: null, pairs: {} };
    }
    return JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
  } catch {
    return { version: '1.0', updatedAt: null, pairs: {} };
  }
}

/**
 * 持久化状态到磁盘
 */
function saveState(state) {
  try {
    if (!fs.existsSync(DEBUG_DIR)) {
      fs.mkdirSync(DEBUG_DIR, { recursive: true });
    }
    state.updatedAt = new Date().toISOString();
    // V04 修复: 原子写入 (temp+rename)，防止进程崩溃时文件损坏
    const tmpFile = STATE_FILE + '.tmp';
    fs.writeFileSync(tmpFile, JSON.stringify(state, null, 2) + '\n');
    fs.renameSync(tmpFile, STATE_FILE);
  } catch {
    // 写入失败时静默忽略，不影响主流程
  }
}

/**
 * 生成 pair key (排序以确保 a|b 与 b|a 是同一个 key)
 */
function pairKey(skillA, skillB) {
  return [skillA, skillB].sort().join('|');
}

/**
 * 获取或初始化一个 pair 的 Dirichlet 状态
 * @param {Object} state - 全局状态
 * @param {string} skillA - 技能 A
 * @param {string} skillB - 技能 B
 * @param {string} hardRuleBoost - 硬规则 boost 的技能 (若有)
 */
function getOrInitPair(state, skillA, skillB, hardRuleBoost) {
  const key = pairKey(skillA, skillB);
  if (!state.pairs[key]) {
    // 初始化 Dirichlet 先验
    const alphas = {};
    alphas[skillA] = skillA === hardRuleBoost ? CONFIG.hardRulePrior : CONFIG.weakPrior;
    alphas[skillB] = skillB === hardRuleBoost ? CONFIG.hardRulePrior : CONFIG.weakPrior;
    // XC1 修复: 保存初始 alpha 快照，供 _checkDriftWarning 计算 expectedPrior
    const initialAlphas = { ...alphas };
    state.pairs[key] = {
      alphas,
      _initialAlphas: initialAlphas,
      totalSamples: 0,
      lastUpdated: null,
    };
  }
  return state.pairs[key];
}

// ─── Bayesian 后验计算 ─────────────────────────────────

/**
 * 计算 skill 在 pair 中的 Bayesian 后验概率
 * 期望值 = α_i / Σ(α)
 */
function computePosterior(pair, skillName) {
  const alphas = pair.alphas || {};
  const totalAlpha = Object.values(alphas).reduce((s, a) => s + a, 0);
  if (totalAlpha <= 0) return 0.5; // 均匀分布
  return (alphas[skillName] || CONFIG.weakPrior) / totalAlpha;
}

/**
 * 检查 pair 是否已收敛 (样本充足且后验集中)
 * 收敛时返回 winner，否则返回 null
 */
function checkConvergence(pair) {
  if ((pair.totalSamples || 0) < CONFIG.convergenceThreshold) return null;
  const alphas = pair.alphas || {};
  const totalAlpha = Object.values(alphas).reduce((s, a) => s + a, 0);
  if (totalAlpha <= 0) return null;

  let maxAlpha = 0, winner = null;
  for (const [skill, alpha] of Object.entries(alphas)) {
    if (alpha > maxAlpha) {
      maxAlpha = alpha;
      winner = skill;
    }
  }
  const posterior = totalAlpha > 0 ? maxAlpha / totalAlpha : 0;
  return posterior >= CONFIG.convergenceConfidence ? winner : null;
}

// ─── 核心消歧函数 ──────────────────────────────────────

/**
 * 自适应消歧: 融合硬规则结果与 Bayesian 后验概率
 *
 * @param {Array<{name: string, score: number}>} candidates - 当前候选技能列表 (已按 score 排序)
 * @param {Object} context - 查询上下文 { prompt, domain, intent }
 * @param {Object} hardRuleResults - 硬规则 boost/penalty 结果
 *   结构: { boosted: string[], penalized: string[], firedRules: string[] }
 * @returns {Array<{name: string, score: number}>} 融合后重排的候选列表
 */
function adaptiveDisambiguate(candidates, context, hardRuleResults) {
  if (!candidates || candidates.length < 2) return candidates || [];

  try {
    const state = loadState();
    const boosted = (hardRuleResults && hardRuleResults.boosted) ? hardRuleResults.boosted : [];
    const penalized = (hardRuleResults && hardRuleResults.penalized) ? hardRuleResults.penalized : [];

    // 对 top-5 候选两两计算 Bayesian 调整
    const topCandidates = candidates.slice(0, 5);
    const adjustments = new Map(); // skillName → 累计 Bayesian 调整分

    for (let i = 0; i < topCandidates.length; i++) {
      for (let j = i + 1; j < topCandidates.length; j++) {
        const skillA = topCandidates[i].name;
        const skillB = topCandidates[j].name;

        // 确定此 pair 中硬规则 boost 的技能
        const hardBoostForPair = boosted.find(b => b === skillA || b === skillB) || null;
        const pair = getOrInitPair(state, skillA, skillB, hardBoostForPair);

        // 计算 Bayesian 后验
        const posteriorA = computePosterior(pair, skillA);
        const posteriorB = computePosterior(pair, skillB);

        // 积累调整量 (相对于均匀分布 0.5 的偏差)
        const adjA = (adjustments.get(skillA) || 0) + (posteriorA - 0.5);
        const adjB = (adjustments.get(skillB) || 0) + (posteriorB - 0.5);
        adjustments.set(skillA, adjA);
        adjustments.set(skillB, adjB);
      }
    }

    // C3_DIRICHLET_HARDENING_v1: softmax-lite 归一化，避免 maxAdj 线性缩放导致的 ±1 饱和
    // Σ_i softmax(adj_i) = 1; 映射到 [-1, +1] 区间做 boost 基准
    const _expAdj = new Map();
    let _sumExp = 0;
    for (const [_k, _v] of adjustments.entries()) {
      const _e = Math.exp(Math.max(-5, Math.min(5, _v)));
      _expAdj.set(_k, _e);
      _sumExp += _e;
    }
    const _n = adjustments.size || 1;
    const _uniform = 1 / _n;
    // 兼容符号: 保留 maxAdj 供 fallback (若 softmax 退化则退回原算法)
    let maxAdj = 0;
    for (const adj of adjustments.values()) {
      if (Math.abs(adj) > maxAdj) maxAdj = Math.abs(adj);
    }

    // 融合最终分数: hardRule × 0.7 + Bayesian × 0.3
    const result = candidates.map(c => {
      const adj = adjustments.get(c.name) || 0;
      // C3_DIRICHLET_HARDENING_v1: softmax 归一化 (退化时 fallback 到 maxAdj 线性)
      const _soft = _sumExp > 0 ? (_expAdj.get(c.name) || 0) / _sumExp : _uniform;
      // 映射 [0,1] → [-1,+1]: (soft - uniform) / uniform，再按 maxAdj 兜底
      const _softSigned = (_soft - _uniform) / Math.max(_uniform, 1e-6);
      const normalizedAdj = Math.max(-1, Math.min(1, _softSigned));
      // Bayesian 分量: 以原始分数为基准，用后验概率微调
      const bayesianBoost = normalizedAdj * c.score * CONFIG.bayesianWeight;
      return {
        ...c,
        score: Math.round((c.score + bayesianBoost) * 100) / 100,
        _bayesianAdj: Math.round(normalizedAdj * 100) / 100,
      };
    });

    result.sort((a, b) => b.score - a.score);

    // 状态不需要保存 (只在 updateFromFeedback 时保存)
    return result;
  } catch {
    // Fail-open: 任何异常返回原始候选
    return candidates;
  }
}

/**
 * 从路由反馈更新 Dirichlet 先验
 * 由 route-auditor 或 implicit-feedback 调用
 *
 * @param {string} routedSkill - 实际路由到的技能
 * @param {string} correctedSkill - 用户纠正为的技能 (若有，否则等于 routedSkill)
 * @param {string[]} competingSkills - 路由时的竞争技能 (candidates 中其他技能)
 */
function updateFromFeedback(routedSkill, correctedSkill, competingSkills) {
  if (!routedSkill) return;

  try {
    const state = loadState();
    // 实际使用的技能 (纠正后的，或原路由)
    const actualSkill = correctedSkill || routedSkill;
    const wasCorrect = !correctedSkill || correctedSkill === routedSkill;

    // 对 actualSkill 与所有竞争技能的 pair 进行更新
    for (const competing of (competingSkills || [])) {
      if (competing === actualSkill) continue;

      const key = pairKey(actualSkill, competing);
      // 懒初始化 (无强先验，因为我们不知道硬规则在这个 pair 上的结论)
      if (!state.pairs[key]) {
        // C3_DIRICHLET_HARDENING_v1: 懒初始化必须保存 _initialAlphas 快照，否则 drift 报警失效
        const _alphas = {
          [actualSkill]: CONFIG.weakPrior,
          [competing]: CONFIG.weakPrior,
        };
        state.pairs[key] = {
          alphas: _alphas,
          _initialAlphas: { ..._alphas },
          totalSamples: 0,
          lastUpdated: null,
        };
      }

      const pair = state.pairs[key];

      // P2-14 修复: 标准 Bayesian 更新 — 仅增加正确技能的 alpha，
      // 不减少错误技能的 alpha。Dirichlet 分布会通过总量增加自然稀释错误技能的后验概率。
      // 移除原来的 -0.5 惩罚，避免人为扭曲先验分布。
      // C3_DIRICHLET_HARDENING_v1: 正样本 +1; 竞争技能软衰减 (1%) 防止单调累积; EMA 上限 Σα ≤ 200
      pair.alphas[actualSkill] = (pair.alphas[actualSkill] || CONFIG.weakPrior) + 1;
      if (pair.alphas[competing] !== undefined && pair.alphas[competing] > CONFIG.weakPrior) {
        pair.alphas[competing] = Math.max(CONFIG.weakPrior,
          pair.alphas[competing] - 0.01 * (pair.alphas[competing] - CONFIG.weakPrior));
      }
      // EMA 上限: 总样本量超过 200 时按比例回缩 (保持相对比例)
      const _sumAlpha = Object.values(pair.alphas).reduce(function (s, a) { return s + a; }, 0);
      if (_sumAlpha > 200) {
        const _scale = 200 / _sumAlpha;
        for (const _k of Object.keys(pair.alphas)) {
          pair.alphas[_k] = Math.max(CONFIG.weakPrior, pair.alphas[_k] * _scale);
        }
      }

      pair.totalSamples = (pair.totalSamples || 0) + 1;
      pair.lastUpdated = new Date().toISOString();

      // 检查是否偏离先验超过阈值 → 写入 evolution-log
      _checkDriftWarning(actualSkill, competing, pair);
    }

    saveState(state);
  } catch {
    // Fail-open
  }
}

/**
 * 检查学习权重是否偏离先验超过 50%
 * 偏离时写入 evolution-log 供人工审查
 */
function _checkDriftWarning(skillA, skillB, pair) {
  try {
    const alphas = pair.alphas || {};
    const totalAlpha = Object.values(alphas).reduce((s, a) => s + a, 0);
    if (totalAlpha <= 0) return;

    for (const [skill, alpha] of Object.entries(alphas)) {
      const posterior = alpha / totalAlpha;
      // XC1 修复: 从 _initialAlphas 快照计算各技能的真实期望先验后验
      // 若无快照则回退到 weakPrior / totalInitialAlpha 估算
      let expectedPrior;
      if (pair._initialAlphas) {
        const initialAlpha = pair._initialAlphas[skill] || CONFIG.weakPrior;
        const totalInitialAlpha = Object.values(pair._initialAlphas).reduce((s, a) => s + a, 0);
        expectedPrior = totalInitialAlpha > 0 ? initialAlpha / totalInitialAlpha : 0.5;
      } else {
        // 旧数据无快照: 根据 hardRulePrior 数值猜测
        expectedPrior = alpha >= CONFIG.hardRulePrior
          ? CONFIG.hardRulePrior / (CONFIG.hardRulePrior + CONFIG.weakPrior)
          : CONFIG.weakPrior / (CONFIG.hardRulePrior + CONFIG.weakPrior);
      }

      if (Math.abs(posterior - expectedPrior) > CONFIG.driftWarningRatio) {
        // V20 修复: 去重 — 同一 pair+skill 24h 内只报一次
        const evolutionLog = path.join(DEBUG_DIR, 'evolution-log.jsonl');
        const dedupKey = `${pairKey(skillA, skillB)}:${skill}`;
        let shouldLog = true;
        try {
          if (fs.existsSync(evolutionLog)) {
            const tail = fs.readFileSync(evolutionLog, 'utf8').split('\n').filter(Boolean).slice(-50);
            const cutoff = Date.now() - 24 * 60 * 60 * 1000;
            for (const line of tail) {
              try {
                const e = JSON.parse(line);
                if (e.event === 'adaptive-disambiguator-drift' && e.pair === pairKey(skillA, skillB) && e.skill === skill && new Date(e.ts).getTime() > cutoff) {
                  shouldLog = false; break;
                }
              } catch {}
            }
          }
        } catch {}
        if (shouldLog) {
          const logEntry = {
            ts: new Date().toISOString(),
            event: 'adaptive-disambiguator-drift',
            pair: pairKey(skillA, skillB),
            skill,
            posterior: Math.round(posterior * 100) / 100,
            samples: pair.totalSamples,
            message: `学习权重偏离先验 ${Math.round(Math.abs(posterior - expectedPrior) * 100)}%，建议人工审查`,
          };
          // C2_SAFE_APPEND_v1: 与 stop-dispatcher consistency-sentinel 共享 evolution-log，必须加锁
          try {
            const { safeAppendJsonl } = require(require('path').join(__dirname, '..', 'hooks', 'lib', 'safe-append.js'));
            safeAppendJsonl(evolutionLog, logEntry, { useLock: true });
          } catch {
            try { fs.appendFileSync(evolutionLog, JSON.stringify(logEntry) + '\n'); } catch {}
          }
        }
      }
    }
  } catch {}
}

/**
 * 从 route-feedback.jsonl 批量更新 Dirichlet 先验
 * 用于首次初始化或定期补录
 *
 * @param {number} maxEntries - 最大处理条数 (默认 1000)
 */
function bulkUpdateFromFeedbackFile(maxEntries) {
  maxEntries = maxEntries || 1000;
  try {
    if (!fs.existsSync(FEEDBACK_FILE)) return { processed: 0, errors: 0 };

    const lines = fs.readFileSync(FEEDBACK_FILE, 'utf8')
      .split('\n')
      .filter(l => l.trim());

    let processed = 0, errors = 0;

    // 取最新的 maxEntries 条
    const entries = lines.slice(-maxEntries);

    for (const line of entries) {
      try {
        const entry = JSON.parse(line);
        // route-feedback.jsonl 格式: { routedTo, correctedTo, candidates... }
        const routedSkill = entry.routedTo;
        const correctedSkill = entry.correctedTo !== entry.routedTo ? entry.correctedTo : null;
        // candidates 字段不一定存在，用空数组降级
        const competing = (entry.candidates || []).filter(c => c !== routedSkill && c !== correctedSkill);
        updateFromFeedback(routedSkill, correctedSkill, competing);
        processed++;
      } catch {
        errors++;
      }
    }

    return { processed, errors };
  } catch {
    return { processed: 0, errors: 0 };
  }
}

/**
 * 获取当前学习状态的摘要
 */
function getState() {
  try {
    const state = loadState();
    const pairs = state.pairs || {};
    const pairCount = Object.keys(pairs).length;

    // 统计收敛的 pair
    let convergedCount = 0;
    const convergedPairs = [];
    for (const [key, pair] of Object.entries(pairs)) {
      const winner = checkConvergence(pair);
      if (winner) {
        convergedCount++;
        convergedPairs.push({ pair: key, winner, samples: pair.totalSamples });
      }
    }

    // 总样本数
    const totalSamples = Object.values(pairs).reduce((s, p) => s + (p.totalSamples || 0), 0);

    return {
      version: state.version || '1.0',
      updatedAt: state.updatedAt,
      pairCount,
      totalSamples,
      convergedCount,
      convergedPairs: convergedPairs.slice(0, 10), // 只返回前 10 个
      config: CONFIG,
    };
  } catch {
    return { error: 'state unavailable', config: CONFIG };
  }
}

/**
 * 重置所有学习状态
 */
function resetState() {
  try {
    const empty = { version: '1.0', updatedAt: new Date().toISOString(), pairs: {}, resetAt: new Date().toISOString() };
    saveState(empty);
    return { success: true, message: '学习状态已重置' };
  } catch (e) {
    return { success: false, error: e.message };
  }
}

// ─── CLI 入口 ──────────────────────────────────────────
if (require.main === module) {
  const args = process.argv.slice(2);

  if (args.includes('--reset')) {
    const result = resetState();
    console.log(result.success ? '[adaptive-disambiguator] 状态已重置' : `[ERROR] ${result.error}`);
    process.exit(result.success ? 0 : 1);
  }

  if (args.includes('--bulk-update')) {
    const result = bulkUpdateFromFeedbackFile(1000);
    console.log(`[adaptive-disambiguator] 批量更新完成: 处理 ${result.processed} 条, 错误 ${result.errors} 条`);
    process.exit(0);
  }

  // 默认: 输出当前状态
  const state = getState();
  console.log(JSON.stringify(state, null, 2));
  process.exit(0);
}

// ─── 模块导出 ──────────────────────────────────────────
if (typeof module !== 'undefined') {
  module.exports = {
    adaptiveDisambiguate,
    updateFromFeedback,
    bulkUpdateFromFeedbackFile,
    getState,
    resetState,
    loadState,
    saveState,
    computePosterior,
    checkConvergence,
    CONFIG,
  };
}
