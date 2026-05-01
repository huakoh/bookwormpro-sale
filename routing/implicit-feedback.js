#!/usr/bin/env node
/**
 * 隐式反馈推断引擎 (v4.9)
 *
 * 从 activity 日志推断路由是否正确:
 * - 路由到 skill-A 后 5 分钟内若实际使用 skill-B → 隐式纠正
 * - 路由到 skill-A 后实际使用 skill-A → 隐式确认
 *
 * 用法:
 *   node implicit-feedback.js            # 推断并写入反馈
 *   node implicit-feedback.js --dry-run  # 仅预览
 *   node implicit-feedback.js --json     # JSON 输出
 */

const fs = require('fs');
const { safeAppendJsonl } = require('./lib/safe-append.js');
const path = require('path');

const detectClaudeRoot = () => require('./paths.config.js').PATHS.root;

const ROOT = detectClaudeRoot();
const DEBUG_DIR = path.join(ROOT, 'debug');
const FEEDBACK_FILE = path.join(DEBUG_DIR, 'route-feedback.jsonl');

// 隐式反馈时间窗口 (毫秒)
const IMPLICIT_WINDOW_MS = 5 * 60 * 1000; // 5 分钟
const MAX_FEEDBACK_LINES = 5000; // v5.9: 反馈文件最大行数 (约 30 天 @100条/天)

/**
 * v5.9: 日志轮转 — 当 FEEDBACK_FILE 超过 MAX_FEEDBACK_LINES 时截断旧条目
 */
function rotateFeedbackIfNeeded() {
  try {
    if (!fs.existsSync(FEEDBACK_FILE)) return;
    const content = fs.readFileSync(FEEDBACK_FILE, 'utf8');
    const lines = content.split('\n').filter(Boolean);
    if (lines.length <= MAX_FEEDBACK_LINES) return;
    // 保留最新的 MAX_FEEDBACK_LINES 行
    const kept = lines.slice(-MAX_FEEDBACK_LINES);
    // V18 修复: 原子轮转 (temp+rename)
    const tmpFile = FEEDBACK_FILE + '.tmp';
    fs.writeFileSync(tmpFile, kept.join('\n') + '\n');
    fs.renameSync(tmpFile, FEEDBACK_FILE);
  } catch {}
}

/**
 * 加载路由日志 (所有日期)
 * @param {number} maxDays - 最多回溯天数
 * @returns {Array} 路由日志条目
 */
function loadRouteLogs(maxDays = 7) {
  const logs = [];
  try {
    const files = fs.readdirSync(DEBUG_DIR)
      .filter(f => f.startsWith('route-') && f.endsWith('.jsonl'))
      .sort();

    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - maxDays);
    const cutoffStr = cutoff.toISOString().slice(0, 10);

    for (const file of files) {
      const dateMatch = file.match(/route-(\d{4}-\d{2}-\d{2})/);
      if (dateMatch && dateMatch[1] < cutoffStr) continue;

      const lines = fs.readFileSync(path.join(DEBUG_DIR, file), 'utf8').trim().split('\n');
      for (const line of lines) {
        try { logs.push(JSON.parse(line)); } catch {}
      }
    }
  } catch {}
  return logs;
}

/**
 * 加载 activity 日志
 * @param {number} maxDays - 最多回溯天数
 * @returns {Array} activity 事件条目
 */
function loadActivityLogs(maxDays = 7) {
  const events = [];
  try {
    const files = fs.readdirSync(DEBUG_DIR)
      .filter(f => f.startsWith('activity-') && f.endsWith('.jsonl'))
      .sort();

    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - maxDays);
    const cutoffStr = cutoff.toISOString().slice(0, 10);

    for (const file of files) {
      const dateMatch = file.match(/activity-(\d{4}-\d{2}-\d{2})/);
      if (dateMatch && dateMatch[1] < cutoffStr) continue;

      const lines = fs.readFileSync(path.join(DEBUG_DIR, file), 'utf8').trim().split('\n');
      for (const line of lines) {
        try { events.push(JSON.parse(line)); } catch {}
      }
    }
  } catch {}
  return events;
}

/**
 * 从路由日志和活动日志推断隐式反馈
 * @param {Array} routeLogs - 路由日志条目
 * @param {Array} activityLogs - activity 事件条目
 * @returns {Array} 隐式反馈条目
 */
function inferFeedback(routeLogs, activityLogs) {
  const feedback = [];

  // 将 activity 日志中的 skill 事件按时间排序
  const skillEvents = activityLogs
    .filter(e => e.event === 'skill' && e.detail && e.ts)
    .sort((a, b) => new Date(a.ts) - new Date(b.ts));

  for (const routeEntry of routeLogs) {
    if (!routeEntry.ts || !routeEntry.topResult) continue;
    const routeTime = new Date(routeEntry.ts).getTime();
    if (isNaN(routeTime)) continue;

    // P1-1 修复: 取窗口内第一个技能调用 (代表用户对路由的即时反应)
    // 原逻辑取最后一个会把不相关的后续技能误判为"纠正"
    const windowEvents = skillEvents.filter(e => {
      const eventTime = new Date(e.ts).getTime();
      return eventTime >= routeTime && (eventTime - routeTime) <= IMPLICIT_WINDOW_MS;
    });
    const nextSkill = windowEvents.length > 0
      ? windowEvents[0]
      : null;

    if (!nextSkill) continue;

    const routedTo = routeEntry.topResult;
    const actualUsed = nextSkill.detail;

    if (routedTo === actualUsed) {
      // 隐式确认: 路由正确
      feedback.push({
        ts: routeEntry.ts,
        type: 'implicit',
        query: routeEntry.query || '',
        routedTo,
        correctedTo: routedTo,
        confidence: routeEntry.topConfidence || 0,
        implicit: 'confirm',
      });
    } else {
      // 隐式纠正: 用户实际用了不同技能
      feedback.push({
        ts: routeEntry.ts,
        type: 'implicit',
        query: routeEntry.query || '',
        routedTo,
        correctedTo: actualUsed,
        confidence: routeEntry.topConfidence || 0,
        implicit: 'correct',
      });
    }
  }



  // 弱信号: 超时确认 — 路由后 5 分钟内无 Skill 调用也无纠正 → 隐式确认 (低权重)
  // V11 修复: 排除 simple 复杂度查询 (BWR:skip)，避免虚假确认膨胀
  const feedbackTs = new Set(feedback.map(f => f.ts));
  const correctionFile = require("path").join(DEBUG_DIR, "route-feedback.jsonl");
  let explicitCorrections = new Set();
  try {
    if (fs.existsSync(correctionFile)) {
      const corrLines = fs.readFileSync(correctionFile, "utf8").split("\n").filter(Boolean);
      for (const cl of corrLines) {
        try {
          const ce = JSON.parse(cl);
          if (ce.type === "explicit" || ce.type === "manual") {
            explicitCorrections.add(ce.ts);
          }
        } catch {}
      }
    }
  } catch {}

  const now = Date.now();
  for (const re of routeLogs) {
    if (!re.ts || !re.topResult) continue;
    if (feedbackTs.has(re.ts)) continue;
    if (explicitCorrections.has(re.ts)) continue;
    const rt = new Date(re.ts).getTime();
    if (isNaN(rt)) continue;
    if (now - rt < IMPLICIT_WINDOW_MS) continue;
    // V11 修复: simple/skip 查询不产生 timeout-confirm (这些查询本身不需要 Skill)
    const complexity = re.complexity || '';
    if (complexity === 'simple' || re.action === 'skip') continue;
    feedback.push({
      ts: re.ts,
      type: "implicit",
      query: re.query || "",
      routedTo: re.topResult,
      correctedTo: re.topResult,
      confidence: re.topConfidence || 0,
      implicit: "timeout-confirm",
      weight: 0.1, // v5.9: 降低超时确认权重 (0.3→0.1)，减少观测偏差
    });
  }

  return feedback;
}

/**
 * 生成隐式反馈并写入 route-feedback.jsonl
 * @param {Object} options - { dryRun, maxDays }
 * @returns {Object} 统计结果
 */
function generateImplicitFeedback(options = {}) {
  const dryRun = options.dryRun || false;
  const maxDays = options.maxDays || options.days || 7;

  const routeLogs = loadRouteLogs(maxDays);
  const activityLogs = loadActivityLogs(maxDays);
  const implicitFB = inferFeedback(routeLogs, activityLogs);

  // v5.9: 消费 skill-outcome.jsonl 直接观测信号 (比时间窗口推断更准确)
  try {
    const outcomeFile = path.join(DEBUG_DIR, 'skill-outcome.jsonl');
    if (fs.existsSync(outcomeFile)) {
      const outcomes = fs.readFileSync(outcomeFile, 'utf8')
        .split('\n').filter(Boolean)
        .map(l => { try { return JSON.parse(l); } catch { return null; } })
        .filter(Boolean);
      // 按 traceId 关联路由日志，生成高置信度反馈
      const routeByTrace = {};
      for (const rl of routeLogs) {
        if (rl.traceId) routeByTrace[rl.traceId] = rl;
      }
      for (const oc of outcomes) {
        if (!oc.traceId || !oc.skill) continue;
        const rl = routeByTrace[oc.traceId];
        if (!rl || !rl.topResult) continue;
        implicitFB.push({
          ts: oc.ts,
          type: 'observed',
          query: rl.query || '',
          routedTo: rl.topResult,
          correctedTo: oc.skill,
          confidence: rl.topConfidence || 0,
          implicit: rl.topResult === oc.skill ? 'observed-confirm' : 'observed-correct',
          weight: 0.8, // 直接观测权重远高于时间窗口推断
        });
      }
    }
  } catch {}

  // 去重: 不重复写入已有的隐式反馈
  let existingFB = [];
  if (fs.existsSync(FEEDBACK_FILE)) {
    existingFB = fs.readFileSync(FEEDBACK_FILE, 'utf8')
      .split('\n').filter(Boolean)
      .map(l => { try { return JSON.parse(l); } catch { return null; } })
      .filter(Boolean);
  }

  // XC9 修复: 去重同时覆盖 'implicit' 和 'observed' 类型
  // 轮转后旧 implicit 条目被删除，若只过滤 'implicit' 则 observed 重复写入
  const existingKeys = new Set(
    existingFB.filter(f => f.type === 'implicit' || f.type === 'observed')
      .map(f => `${f.traceId || f.ts}:${f.routedTo}:${f.correctedTo}`)
  );

  const newFB = implicitFB.filter(f =>
    !existingKeys.has(`${f.traceId || f.ts}:${f.routedTo}:${f.correctedTo}`)
  );

  if (!dryRun && newFB.length > 0) {
    if (!fs.existsSync(DEBUG_DIR)) fs.mkdirSync(DEBUG_DIR, { recursive: true });
    const lines = newFB.map(f => JSON.stringify(f)).join('\n') + '\n';
    fs.appendFileSync(FEEDBACK_FILE, lines);

    // v5.9: 写入后检查是否需要轮转
    rotateFeedbackIfNeeded();

    // P3: 写入新反馈后触发权重学习
    try {
      const routeFeedback = require('./route-feedback.js');
      if (routeFeedback.autoLearn) routeFeedback.autoLearn();
    } catch {}
  }

  const confirms = newFB.filter(f => f.implicit === 'confirm' || f.implicit === 'timeout-confirm').length;
  const corrections = newFB.filter(f => f.implicit === 'correct').length;
  const timeoutConfirms = newFB.filter(f => f.implicit === 'timeout-confirm').length;

  return {
    routeLogCount: routeLogs.length,
    activityLogCount: activityLogs.length,
    totalInferred: implicitFB.length,
    newFeedback: newFB.length,
    confirms,
    timeoutConfirms,
    corrections,
    dryRun,
  };
}

// 模块导出
if (typeof module !== 'undefined') {
  module.exports = {
    inferFeedback,
    generateImplicitFeedback,
    inferAndWrite: generateImplicitFeedback,
    loadRouteLogs,
    loadActivityLogs,
    IMPLICIT_WINDOW_MS,
  };
}

// CLI 入口
if (require.main === module) {
  const dryRun = process.argv.includes('--dry-run');
  const jsonMode = process.argv.includes('--json');

  const result = generateImplicitFeedback({ dryRun });

  if (jsonMode) {
    console.log(JSON.stringify(result, null, 2));
  } else {
    console.log('=== 隐式反馈推断 ===');
    console.log(`路由日志: ${result.routeLogCount} 条`);
    console.log(`活动日志: ${result.activityLogCount} 条`);
    console.log(`推断反馈: ${result.totalInferred} 条 (${result.confirms} 确认, ${result.corrections} 纠正)`);
    console.log(`新增写入: ${result.newFeedback} 条${result.dryRun ? ' (dry-run)' : ''}`);
  }
}
