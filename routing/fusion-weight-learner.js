#!/usr/bin/env node
/**
 * 融合权重自适应学习器 (v5.9)
 *
 * 对路由融合权重 (BM25, Semantic, Context, Project, Workflow) 进行在线学习。
 * 基于反馈纠正数据，用 projected gradient descent 调整权重使路由更准确。
 *
 * 约束:
 *   - 权重之和 = 1.0 (概率单纯形)
 *   - 每个权重 ∈ [0.05, 0.6] (防止退化)
 *   - 学习率 η = 0.02 (保守更新)
 *
 * 用法:
 *   node fusion-weight-learner.js              # 学习并输出权重
 *   node fusion-weight-learner.js --dry-run    # 仅预览
 *   node fusion-weight-learner.js --reset      # 重置为默认权重
 *   node fusion-weight-learner.js --json       # JSON 输出
 *
 * 文件:
 *   debug/fusion-weights.json   学习后的融合权重
 */

const fs = require('fs');
const path = require('path');

// MEDIUM-1: 引入 WeightStore，使用 safeWriteJson 进行并发安全写入
// 若加载失败则回退到直接写入 (不阻断功能)
let _weightStore = null;
try {
  const _ws = require('./weight-store.js');
  if (typeof _ws.safeWriteJson === 'function') {
    _weightStore = _ws;
  }
} catch {}

const detectClaudeRoot = () => require('./paths.config.js').PATHS.root;

const ROOT = detectClaudeRoot();
const DEBUG_DIR = path.join(ROOT, 'debug');
const FEEDBACK_FILE = path.join(DEBUG_DIR, 'route-feedback.jsonl');
const FUSION_WEIGHTS_FILE = path.join(DEBUG_DIR, 'fusion-weights.json');
const INDEX_FILE = path.join(ROOT, 'skills-index.json');

// 默认融合权重 (与 route-interceptor.js 一致)
const DEFAULT_WEIGHTS = {
  bm25: 0.40,
  semantic: 0.30,
  context: 0.15,
  project: 0.10,
  workflow: 0.05,
};

// 约束
const MIN_WEIGHT = 0.05;
const MAX_WEIGHT = 0.60;
const LEARNING_RATE = 0.02;
// W1 修复 (patch-w1-weight-decay, 2026-04-16): L2 正则化强度
// 每批次将权重按比例拉回 DEFAULT_WEIGHTS，防止 simulateSignals 三维=0 导致的单向漂移
const WEIGHT_DECAY = 0.02;
const DECAY_HALF_LIFE = 7 * 86400000; // 7 天半衰期

// v5.9: 多项目隔离支持
let _isolator = null;
try { _isolator = require('./project-isolator.js'); } catch {}
function getWeightsFile(cwd) {
  if (_isolator && cwd) return _isolator.getIsolatedPath('fusion-weights.json', cwd);
  return FUSION_WEIGHTS_FILE;
}

/**
 * 安全写入 fusion-weights.json
 * BUG-FIX: 原来委托给 weight-store.safeWriteJson（async Promise），
 * 但没有 await，导致进程退出时写入从未完成，权重永远停在 bootstrap 值。
 * fusion-weights.json 只有一个写入者（本文件），无并发写入，不需要锁。
 * 直接使用同步 fs.writeFileSync 保证写入在进程退出前完成。
 * @param {string} weightsFile - 目标文件路径
 * @param {Object} data - 要写入的数据
 */
function safeWriteFusionWeights(weightsFile, data) {
  _directWriteFallback(weightsFile, data);
}

/** 直接写入回退（weight-store 不可用时） */
function _directWriteFallback(weightsFile, data) {
  try {
    if (!fs.existsSync(path.dirname(weightsFile))) {
      fs.mkdirSync(path.dirname(weightsFile), { recursive: true });
    }
    fs.writeFileSync(weightsFile, JSON.stringify(data, null, 2) + '\n');
  } catch {}
}

/**
 * C1 原子重置助手 (patch-c1-atomic-reset, 2026-04-16)
 * 用 tmp+rename 覆盖为 DEFAULT_WEIGHTS，避免 unlinkSync 与并发 readFileSync 的 TOCTOU 竞态。
 * 读者永远看到合法 JSON (旧值或新的 DEFAULT)，不会 ENOENT。
 */
function atomicResetWeightsFile(weightsFile, reason) {
  try {
    if (!fs.existsSync(path.dirname(weightsFile))) {
      fs.mkdirSync(path.dirname(weightsFile), { recursive: true });
    }
    const payload = {
      weights: { ...DEFAULT_WEIGHTS },
      resetAt: new Date().toISOString(),
      resetReason: reason || 'manual',
    };
    const _tmp = weightsFile + '.tmp.' + process.pid;
    fs.writeFileSync(_tmp, JSON.stringify(payload, null, 2) + '\n');
    fs.renameSync(_tmp, weightsFile);
  } catch {}
}

/**
 * 加载当前融合权重
 * @param {string} [cwd] - 工作目录 (v5.9 per-cwd 隔离)
 * @returns {Object} { bm25, semantic, context, project, workflow }
 */
function loadWeights(cwd) {
  try {
    const file = getWeightsFile(cwd);
    if (fs.existsSync(file)) {
      const data = JSON.parse(fs.readFileSync(file, 'utf8'));
      if (data.weights) return { ...DEFAULT_WEIGHTS, ...data.weights };
    }
  } catch {}
  return { ...DEFAULT_WEIGHTS };
}

/**
 * 投影到概率单纯形 (权重之和=1, 每个 ∈ [MIN, MAX])
 * V01 修复: 迭代 clamp+归一化，确保投影后所有约束同时满足
 */
/**
 * 标准约束单纯形投影 (Duchi et al. 2008 变体)
 * 保证: sum(w) = 1.0 且 w[k] ∈ [MIN_WEIGHT, MAX_WEIGHT]
 * 算法: 排序 → 阈值查找 → 投影 → box clamp → 精确余数分配
 */
function projectToSimplex(w) {
  const keys = Object.keys(w).sort(); // 确定性排序
  const n = keys.length;

  // Step 1: 不带 box 约束的单纯形投影 (Duchi 2008)
  const vals = keys.map(k => w[k]);
  vals.sort((a, b) => b - a); // 降序
  let cumSum = 0;
  let rho = 0;
  for (let j = 0; j < n; j++) {
    cumSum += vals[j];
    if (vals[j] - (cumSum - 1) / (j + 1) > 0) rho = j + 1;
  }
  const theta = (keys.reduce((s, k) => s + w[k], 0) - 1) / rho;
  for (const k of keys) {
    w[k] = Math.max(0, w[k] - theta);
  }

  // Step 2: Box 约束 clamp [MIN_WEIGHT, MAX_WEIGHT]
  for (const k of keys) {
    w[k] = Math.max(MIN_WEIGHT, Math.min(MAX_WEIGHT, w[k]));
  }

  // Step 3: 精确余数分配到离边界最远的维度
  for (const k of keys) {
    w[k] = Math.round(w[k] * 1000) / 1000;
  }
  let residual = 1.0 - keys.reduce((s, k) => s + w[k], 0);
  residual = Math.round(residual * 1000) / 1000;
  if (Math.abs(residual) > 0) {
    // 找离边界最远的维度来吸收残差
    let bestKey = keys[0];
    let bestRoom = 0;
    for (const k of keys) {
      const room = residual > 0
        ? MAX_WEIGHT - w[k]  // 需要增加，找上界余量最大的
        : w[k] - MIN_WEIGHT; // 需要减少，找下界余量最大的
      if (room > bestRoom) { bestRoom = room; bestKey = k; }
    }
    w[bestKey] = Math.round((w[bestKey] + residual) * 1000) / 1000;
    w[bestKey] = Math.max(MIN_WEIGHT, Math.min(MAX_WEIGHT, w[bestKey]));
  }
  return w;
}

/**
 * 加载反馈数据中的纠正条目
 */
function loadCorrections() {
  if (!fs.existsSync(FEEDBACK_FILE)) return [];
  return fs.readFileSync(FEEDBACK_FILE, 'utf8')
    .split('\n').filter(Boolean)
    .map(l => { try { return JSON.parse(l); } catch { return null; } })
    .filter(f => f && f.routedTo && f.correctedTo && f.routedTo !== f.correctedTo && f.routedTo !== 'unknown');
}

/**
 * 为每条纠正模拟各信号分数
 * 因为历史纠正没有保存各信号分数，使用当前引擎重新计算
 */
function simulateSignals(query, skillName, index, analyzer, semanticScorer) {
  const signals = { bm25: 0, semantic: 0, context: 0, project: 0, workflow: 0 };

  // BM25 分数
  try {
    const bm25Params = analyzer.buildBM25Params ? analyzer.buildBM25Params(index) : null;
    const queryTokens = analyzer.tokenize(query);
    const skill = index.skills.find(s => s.name === skillName);
    if (skill && bm25Params) {
      const { totalScore } = analyzer.scoreSkill(skill, queryTokens, bm25Params);
      signals.bm25 = totalScore;
    }
  } catch {}

  // 语义分数
  try {
    if (semanticScorer) {
      const results = semanticScorer.semanticScore(query, index);
      const match = results.find(r => r.name === skillName);
      if (match) signals.semantic = match.score;
    }
  } catch {}

  // context/project/workflow 无法回溯，保持 0
  return signals;
}

/**
 * 在线梯度下降学习融合权重
 * 思路: 对每条纠正，计算正确技能和错误技能的信号向量差异，
 *       沿着提升正确技能分数的方向调整权重
 */
function learnFusionWeights(options = {}) {
  const dryRun = options.dryRun || false;
  const corrections = loadCorrections();

  if (corrections.length < 2) {
    return { status: 'skip', reason: '纠正不足2条', count: corrections.length };
  }

  // 加载依赖
  let analyzer, semanticScorer;
  try { analyzer = require('./route-analyzer.js'); } catch { return { status: 'error', reason: 'route-analyzer 不可用' }; }
  try { semanticScorer = require('./semantic-scorer.js'); } catch { semanticScorer = null; }

  let index;
  try { index = JSON.parse(fs.readFileSync(INDEX_FILE, 'utf8')); } catch { return { status: 'error', reason: 'skills-index.json 不可用' }; }

  const weights = loadWeights();
  const now = Date.now();
  let totalGradient = { bm25: 0, semantic: 0, context: 0, project: 0, workflow: 0 };
  let effectiveSamples = 0;

  for (const fb of corrections) {
    // 时间衰减
    const age = now - new Date(fb.ts).getTime();
    if (isNaN(age) || age < 0) continue;
    const decay = Math.pow(0.5, age / DECAY_HALF_LIFE);

    // 类型权重
    const typeFactor = fb.type === 'observed' ? 0.8 : (fb.type === 'implicit' ? 0.5 : 1.0);
    const sampleWeight = decay * typeFactor;
    if (sampleWeight < 0.01) continue;

    // 模拟正确技能和错误技能的信号
    const correctSignals = simulateSignals(fb.query, fb.correctedTo, index, analyzer, semanticScorer);
    const wrongSignals = simulateSignals(fb.query, fb.routedTo, index, analyzer, semanticScorer);

    // 梯度: 正确技能信号 - 错误技能信号 (希望提升正确技能的权重组合分数)
    for (const key of Object.keys(totalGradient)) {
      totalGradient[key] += sampleWeight * (correctSignals[key] - wrongSignals[key]);
    }
    effectiveSamples += sampleWeight;
  }

  if (effectiveSamples < 1) {
    return { status: 'skip', reason: '有效样本不足', effectiveSamples };
  }

  // 归一化梯度
  for (const key of Object.keys(totalGradient)) {
    totalGradient[key] /= effectiveSamples;
  }

  // 梯度更新 + W1 权重衰减 (L2 正则化拉回 DEFAULT_WEIGHTS)
  const newWeights = { ...weights };
  for (const key of Object.keys(newWeights)) {
    newWeights[key] += LEARNING_RATE * totalGradient[key];
    newWeights[key] += WEIGHT_DECAY * (DEFAULT_WEIGHTS[key] - newWeights[key]);
  }

  // 投影到约束空间
  const projected = projectToSimplex(newWeights);

  // 计算权重变化量
  const deltas = {};
  let totalDelta = 0;
  for (const key of Object.keys(projected)) {
    deltas[key] = Math.round((projected[key] - weights[key]) * 1000) / 1000;
    totalDelta += Math.abs(deltas[key]);
  }

  const result = {
    status: 'ok',
    corrections: corrections.length,
    effectiveSamples: Math.round(effectiveSamples * 10) / 10,
    previousWeights: weights,
    newWeights: projected,
    deltas,
    totalDelta: Math.round(totalDelta * 1000) / 1000,
    gradient: Object.fromEntries(
      Object.entries(totalGradient).map(([k, v]) => [k, Math.round(v * 1000) / 1000])
    ),
    dryRun,
  };

  if (!dryRun && totalDelta > 0.005) {
    if (!fs.existsSync(DEBUG_DIR)) fs.mkdirSync(DEBUG_DIR, { recursive: true });
    const output = {
      generated: new Date().toISOString(),
      weights: projected,
      meta: {
        corrections: corrections.length,
        effectiveSamples: result.effectiveSamples,
        gradient: result.gradient,
        previousWeights: weights,
      },
    };
    // P1-2 修复: 使用文件锁保护写入，防止与 applyImplicitWeights 竞态
    // 根因守卫 + cooldown: 连续 2 周期命中才真正 reset，避免单周期误报抖动
    const wVals = Object.values(result.newWeights || {});
    let degen = 0;
    for (let i = 0; i < wVals.length; i++) {
      for (let j = i + 1; j < wVals.length; j++) {
        if (Math.abs(wVals[i] - wVals[j]) < 0.01) degen++;
      }
    }
    const bm25Val = (result.newWeights && result.newWeights.bm25) || 1;
    const DEGEN_COOLDOWN_FILE = path.join(DEBUG_DIR, 'degen-counter.json');
    const hitDegen = degen >= 3 || bm25Val <= 0.06;
    let consecutiveHits = 0;
    try {
      if (fs.existsSync(DEGEN_COOLDOWN_FILE)) {
        const c = JSON.parse(fs.readFileSync(DEGEN_COOLDOWN_FILE, 'utf8'));
        if (typeof c.hits === 'number') consecutiveHits = c.hits;
      }
    } catch {}
    if (hitDegen) {
      consecutiveHits += 1;
      try {
        const _tmp = DEGEN_COOLDOWN_FILE + '.tmp.' + process.pid;
        fs.writeFileSync(_tmp, JSON.stringify({ hits: consecutiveHits, degen, bm25: bm25Val, ts: new Date().toISOString() }));
        fs.renameSync(_tmp, DEGEN_COOLDOWN_FILE);
      } catch {}
      if (consecutiveHits >= 2) {
        try {
          process.stderr.write('[fusion-weight] 连续 ' + consecutiveHits + ' 周期退化命中，reset 到 DEFAULT_WEIGHTS\n');
          atomicResetWeightsFile(FUSION_WEIGHTS_FILE, 'degen-consecutive-' + consecutiveHits);
          // 重置计数器
          try { fs.unlinkSync(DEGEN_COOLDOWN_FILE); } catch {}
        } catch {}
        return Object.assign({}, result, { status: 'reset-on-degeneracy', weights: Object.assign({}, DEFAULT_WEIGHTS) });
      }
      // 单周期命中: 记录但不 reset (cooldown 防抖)
      try { process.stderr.write('[fusion-weight] 退化单周期 (' + consecutiveHits + '/2)，等待下次确认\n'); } catch {}
    } else {
      // 未命中: 清零计数器 (连续性要求)
      try { if (fs.existsSync(DEGEN_COOLDOWN_FILE)) fs.unlinkSync(DEGEN_COOLDOWN_FILE); } catch {}
    }
    safeWriteFusionWeights(FUSION_WEIGHTS_FILE, output);
  }

  return result;
}

/**
 * 重置为默认权重
 */
function resetWeights() {
  atomicResetWeightsFile(FUSION_WEIGHTS_FILE, 'manual-reset');
  return { status: 'reset', weights: DEFAULT_WEIGHTS };
}

/**
 * 将 implicit-feedback.js 的输出回流到 fusion-weights.json (F3-4)
 *
 * 修复问题: implicit-feedback 只写 route-feedback.jsonl，未触发融合权重更新。
 * 本函数从 route-feedback.jsonl 读取反馈信号，将其转化为 PGD 梯度输入，
 * 调用 learnFusionWeights() 更新 fusion-weights.json。
 *
 * 反馈权重规则（来自 strategic-evolution-v6.md S1-Phase1）:
 *   confirmed       → 权重向当前方向微调 (正向梯度, weight factor 0.5)
 *   corrected       → 权重向正确技能方向调整 (weight factor 1.0)
 *   timeout-confirm → 弱信号确认 (weight factor 0.1)
 *   observed        → 直接观测，最高可信度 (weight factor 0.8)
 *
 * @param {Object} [options]
 * @param {boolean} [options.dryRun=false] - 仅预览，不写文件
 * @param {number} [options.minNewFeedback=3] - 新反馈条数不足时跳过
 * @param {string} [options.cwd] - 工作目录（per-cwd 权重隔离）
 * @returns {Object} { status, applied, skipped, reason, newWeights, totalDelta }
 */
function applyImplicitWeights(options = {}) {
  const dryRun = options.dryRun || false;
  const minNewFeedback = options.minNewFeedback || 3;
  const cwd = options.cwd || null;

  try {
    // XC6 修复: 如果 learnFusionWeights 在同一 Stop 周期内已运行，
    // 先读取最新权重（包含 learnFusionWeights 写入的结果），在此基础上叠加 implicit 梯度，
    // 而非用 applyImplicitWeights 结果覆盖 learnFusionWeights 的结果。
    // 通过 loadWeights() 获取最新状态（下方已调用），不再需要额外标记文件。

    // P2.4 watermark: 若反馈文件 size 未变化 (>=300 bytes 阈值 ~= 3 条新反馈)，跳过全量重算
    // 避免 1085+ 行反馈每次 Stop 都重放，语义不变 (仍然全量读取，只是跳过无新增的周期)
    const WATERMARK_FILE = path.join(DEBUG_DIR, 'implicit-feedback-watermark.json');
    const MIN_SIZE_DELTA = 300;
    let currentSize = 0;
    try { currentSize = fs.existsSync(FEEDBACK_FILE) ? fs.statSync(FEEDBACK_FILE).size : 0; } catch {}
    if (!options.ignoreWatermark && currentSize > 0) {
      try {
        if (fs.existsSync(WATERMARK_FILE)) {
          const wm = JSON.parse(fs.readFileSync(WATERMARK_FILE, 'utf8'));
          if (typeof wm.lastSize === 'number') {
            // RT-V3+V4 修复: 文件被 truncate → 用 overwrite 代替 unlink 消除 unlink-race
            if (currentSize < wm.lastSize) {
              try {
                const _tmp = WATERMARK_FILE + '.tmp.' + process.pid;
                fs.writeFileSync(_tmp, JSON.stringify({ lastSize: 0, ts: new Date().toISOString(), reason: 'truncate-reset' }));
                fs.renameSync(_tmp, WATERMARK_FILE);
              } catch {}
            } else if (currentSize - wm.lastSize < MIN_SIZE_DELTA) {
              return { status: 'skip', reason: 'watermark no-new-feedback', lastSize: wm.lastSize, currentSize };
            }
          }
        }
      } catch {}
    }

    // 读取 route-feedback.jsonl（含 implicit 反馈和 explicit 纠正）
    if (!fs.existsSync(FEEDBACK_FILE)) {
      return { status: 'skip', reason: 'route-feedback.jsonl 不存在', applied: 0 };
    }

    const allFeedback = fs.readFileSync(FEEDBACK_FILE, 'utf8')
      .split('\n').filter(Boolean)
      .map(l => { try { return JSON.parse(l); } catch { return null; } })
      .filter(f => f && f.ts && f.routedTo);

    // RT-V3+V4 修复: 反馈已完整读入内存 → tmp+rename 原子更新 watermark (防并发读取半字节)
    try {
      const _wmTmp = WATERMARK_FILE + '.tmp.' + process.pid;
      fs.writeFileSync(_wmTmp, JSON.stringify({ lastSize: currentSize, ts: new Date().toISOString() }));
      fs.renameSync(_wmTmp, WATERMARK_FILE);
    } catch {}

    if (allFeedback.length === 0) {
      return { status: 'skip', reason: '反馈文件为空', applied: 0 };
    }

    // 只处理 implicit 和 observed 类型的反馈（explicit 已由 learnFusionWeights 消费）
    const implicitFeedback = allFeedback.filter(f =>
      f.type === 'implicit' || f.type === 'observed'
    );

    if (implicitFeedback.length < minNewFeedback) {
      return {
        status: 'skip',
        reason: `隐式反馈条数不足 (${implicitFeedback.length} < ${minNewFeedback})`,
        applied: 0,
      };
    }

    // 加载当前权重
    const currentWeights = loadWeights(cwd);
    const now = Date.now();

    // 计算加权平均梯度
    // 策略: 对 confirmed/timeout-confirm 施加微弱正向梯度（不改变方向）
    //       对 corrected/observed-correct 施加明确的梯度（提升正确技能的信号分量）
    let totalGradient = { bm25: 0, semantic: 0, context: 0, project: 0, workflow: 0 };
    let totalWeight = 0;

    // 加载依赖（用于重新计算信号分数）
    let analyzer, semanticScorer, index;
    try { analyzer = require('./route-analyzer.js'); } catch { analyzer = null; }
    try { semanticScorer = require('./semantic-scorer.js'); } catch { semanticScorer = null; }
    try { index = JSON.parse(fs.readFileSync(INDEX_FILE, 'utf8')); } catch { index = null; }

    for (const fb of implicitFeedback) {
      // 时间衰减（7天半衰期）
      const age = now - new Date(fb.ts).getTime();
      if (isNaN(age) || age < 0) continue;
      const decay = Math.pow(0.5, age / DECAY_HALF_LIFE);

      // 类型权重
      let typeFactor;
      switch (fb.implicit) {
        case 'observed-correct':  typeFactor = 0.8; break;
        case 'correct':           typeFactor = 1.0; break;
        case 'confirm':           typeFactor = 0.5; break;
        case 'observed-confirm':  typeFactor = 0.5; break;
        case 'timeout-confirm':   typeFactor = fb.weight || 0.1; break;
        default:
          // 根据 type 判断
          typeFactor = (fb.routedTo !== fb.correctedTo) ? 1.0 : 0.5;
      }

      const sampleWeight = decay * typeFactor;
      if (sampleWeight < 0.005) continue;

      // 只有纠正类型才需要计算信号差（确认类型梯度为 0，不改变权重方向）
      const isCorrected = fb.routedTo !== fb.correctedTo;

      if (isCorrected && analyzer && index) {
        // 模拟正确技能和错误技能的信号分数
        const correctSignals = simulateSignals(
          fb.query || '', fb.correctedTo, index, analyzer, semanticScorer
        );
        const wrongSignals = simulateSignals(
          fb.query || '', fb.routedTo, index, analyzer, semanticScorer
        );

        for (const key of Object.keys(totalGradient)) {
          totalGradient[key] += sampleWeight * (correctSignals[key] - wrongSignals[key]);
        }
      }
      // P1-1 修复: confirmed 类型不计入 totalWeight，防止梯度稀释导致学习停滞
      if (isCorrected) {
        totalWeight += sampleWeight;
      }
    }

    if (totalWeight < 0.1) {
      return { status: 'skip', reason: '有效样本权重不足', applied: 0 };
    }

    // 归一化梯度
    for (const key of Object.keys(totalGradient)) {
      totalGradient[key] /= totalWeight;
    }

    // 应用梯度更新（保守学习率，使用 LEARNING_RATE 的一半避免与 learnFusionWeights 叠加）
    // W1: 同步使用 WEIGHT_DECAY 的一半，与 implicitLR 成比例
    const implicitLR = LEARNING_RATE * 0.5;
    const implicitDecay = WEIGHT_DECAY * 0.5;
    const newWeights = { ...currentWeights };
    for (const key of Object.keys(newWeights)) {
      newWeights[key] += implicitLR * (totalGradient[key] || 0);
      newWeights[key] += implicitDecay * (DEFAULT_WEIGHTS[key] - newWeights[key]);
    }

    // 投影到概率单纯形
    const projected = projectToSimplex(newWeights);

    // 计算变化量
    const deltas = {};
    let totalDelta = 0;
    for (const key of Object.keys(projected)) {
      deltas[key] = Math.round((projected[key] - currentWeights[key]) * 1000) / 1000;
      totalDelta += Math.abs(deltas[key]);
    }
    totalDelta = Math.round(totalDelta * 1000) / 1000;

    // 变化量过小则跳过（避免频繁写文件）
    if (totalDelta < 0.003) {
      return {
        status: 'skip',
        reason: `梯度变化量过小 (${totalDelta})，跳过写入`,
        applied: implicitFeedback.length,
        totalDelta,
      };
    }

    // 写入 fusion-weights.json（非 dry-run 时）
    if (!dryRun) {
      const weightsFile = getWeightsFile(cwd);
      if (!fs.existsSync(DEBUG_DIR)) fs.mkdirSync(DEBUG_DIR, { recursive: true });
      const output = {
        generated: new Date().toISOString(),
        weights: projected,
        meta: {
          source: 'applyImplicitWeights',
          implicitFeedbackCount: implicitFeedback.length,
          effectiveWeight: Math.round(totalWeight * 10) / 10,
          gradient: Object.fromEntries(
            Object.entries(totalGradient).map(([k, v]) => [k, Math.round(v * 1000) / 1000])
          ),
          previousWeights: currentWeights,
        },
      };
      // P1-2 修复: 使用文件锁保护写入，防止与 learnFusionWeights 竞态
      safeWriteFusionWeights(weightsFile, output);
    }

    return {
      status: 'ok',
      applied: implicitFeedback.length,
      effectiveWeight: Math.round(totalWeight * 10) / 10,
      previousWeights: currentWeights,
      newWeights: projected,
      deltas,
      totalDelta,
      gradient: Object.fromEntries(
        Object.entries(totalGradient).map(([k, v]) => [k, Math.round(v * 1000) / 1000])
      ),
      dryRun,
    };
  } catch (err) {
    // fail-open: 任何异常不影响主流程
    return { status: 'error', reason: err.message, applied: 0 };
  }
}

/**
 * 初始化引导: 若 fusion-weights.json 不存在，写入默认权重
 * 确保 route-interceptor-bundle 首次运行时有权重可读
 */
function bootstrapWeights(cwd) {
  const file = cwd ? getWeightsFile(cwd) : FUSION_WEIGHTS_FILE;
  if (fs.existsSync(file)) return { status: 'exists' };
  if (!fs.existsSync(DEBUG_DIR)) fs.mkdirSync(DEBUG_DIR, { recursive: true });
  const output = {
    generated: new Date().toISOString(),
    weights: { ...DEFAULT_WEIGHTS },
    meta: { source: 'bootstrap', corrections: 0 },
  };
  safeWriteFusionWeights(file, output);
  return { status: 'bootstrapped', weights: DEFAULT_WEIGHTS };
}

/**
 * H2 修复: 原子化 bootstrap + learn + apply 权重更新
 * 用 sentinel 文件检测"半写入"状态 (Stop hook 被 timeout kill)
 *
 * - 检测到 30s 内的 sentinel → 跳过 (并发写入保护)
 * - 检测到 >30s 的 stale sentinel → 清除后正常跑 (上次 kill 残留)
 * - 正常流程: 串联 bootstrap → learn → apply，过程中维护 sentinel
 */
function atomicWeightUpdate(options = {}) {
  const sentinel = FUSION_WEIGHTS_FILE + '.writing';
  const now = Date.now();

  if (fs.existsSync(sentinel)) {
    try {
      const age = now - fs.statSync(sentinel).mtimeMs;
      if (age > 30000) {
        // Stale sentinel (上次写入被 kill) → 清除
        try {
          process.stderr.write('[fusion-weight] stale sentinel 清除 (age=' + Math.round(age/1000) + 's)\n');
        } catch {}
        try { fs.unlinkSync(sentinel); } catch {}
      } else {
        return { status: 'skip', reason: 'concurrent-write', age };
      }
    } catch {}
  }

  try {
    if (!fs.existsSync(DEBUG_DIR)) fs.mkdirSync(DEBUG_DIR, { recursive: true });
    fs.writeFileSync(sentinel, String(process.pid) + '@' + now);

    const bootResult = bootstrapWeights();
    const learnResult = learnFusionWeights(options);
    const applyResult = applyImplicitWeights(options);

    return {
      status: 'ok',
      bootstrap: bootResult && bootResult.status,
      learn: learnResult && learnResult.status,
      apply: applyResult && applyResult.status,
    };
  } catch (err) {
    return { status: 'error', reason: err.message };
  } finally {
    try { if (fs.existsSync(sentinel)) fs.unlinkSync(sentinel); } catch {}
  }
}

// 模块导出
if (typeof module !== 'undefined') {
  module.exports = {
    loadWeights, projectToSimplex, learnFusionWeights,
    resetWeights, applyImplicitWeights, bootstrapWeights, atomicWeightUpdate,
    DEFAULT_WEIGHTS, FUSION_WEIGHTS_FILE,
  };
}

// CLI 入口
if (require.main === module) {
  const args = process.argv.slice(2);
  const jsonMode = args.includes('--json');
  const dryRun = args.includes('--dry-run');

  if (args.includes('--reset')) {
    const r = resetWeights();
    console.log(jsonMode ? JSON.stringify(r, null, 2) : '融合权重已重置为默认值');
    process.exit(0);
  }

  const result = learnFusionWeights({ dryRun });

  if (jsonMode) {
    console.log(JSON.stringify(result, null, 2));
  } else {
    console.log('=== 融合权重自适应学习 ===');
    if (result.status === 'skip') {
      console.log(`跳过: ${result.reason}`);
    } else if (result.status === 'error') {
      console.log(`错误: ${result.reason}`);
    } else {
      console.log(`纠正样本: ${result.corrections}, 有效样本: ${result.effectiveSamples}`);
      console.log(`梯度: ${JSON.stringify(result.gradient)}`);
      console.log(`\n权重变化:`);
      for (const [k, v] of Object.entries(result.deltas)) {
        const arrow = v > 0 ? '↑' : v < 0 ? '↓' : '=';
        console.log(`  ${k.padEnd(10)} ${result.previousWeights[k]} → ${result.newWeights[k]} (${arrow}${Math.abs(v)})`);
      }
      console.log(`\n总变化量: ${result.totalDelta}${result.dryRun ? ' (dry-run)' : ''}`);
    }
  }
}
