'use strict';



/**

 * 路由状态写入 — writeRouteState + appendRouteLog + 遥测

 * @module scripts/route-state

 *

 * 从 route-interceptor-bundle.js 提取 (Phase 0 宪法合规拆分)

 * 原始位置: bundle L486-599

 */



const fs = require('fs');

const path = require('path');

const crypto = require('crypto');

const { safeAppendJsonl } = require('./lib/safe-append.js');



const CLAUDE_ROOT = require('./lib/root.js');

const DEBUG_DIR = path.join(CLAUDE_ROOT, 'debug');

const SCRIPTS_DIR = path.join(CLAUDE_ROOT, 'scripts');



const { MUST_INVOKE_EXEMPT_INTENTS } = require('./bwr-builder.js');



// 日志脱敏

const sanitizePrompt = (() => {

  try { return require('./sanitize.js').sanitize; }

  catch { return (text) => text || ''; }

})();



// 安全加载模块

function safeRequire(modulePath) {

  try { return require(modulePath); } catch { return null; }

}



/**

 * 追加路由决策到每日路由日志

 * @param {string} prompt - 用户输入

 * @param {object} routing - 路由结果

 * @param {string} traceId - 追踪 ID

 */

function appendRouteLog(prompt, routing, traceId) {

  try {

    if (prompt && prompt.includes('<task-notification>')) return;



    const dateStr = new Date().toISOString().slice(0, 10);

    const logFile = path.join(DEBUG_DIR, 'route-' + dateStr + '.jsonl');

    const entry = {

      ts: new Date().toISOString(),

      traceId,

      query: sanitizePrompt((prompt || '').slice(0, 200)),

      topResult: routing.primary,

      topConfidence: routing.confidence,

      candidates: (routing.candidates || []).slice(0, 3).map(c => c.name),

    };

    safeAppendJsonl(logFile, entry);



    // 低置信度 developer-expert 回退日志

    if (routing.primary === 'developer-expert' && routing.confidence < 0.4) {

      const blindFile = path.join(DEBUG_DIR, 'route-blind-spots.jsonl');

      safeAppendJsonl(blindFile, {

        ts: entry.ts, traceId,

        query: entry.query,

        confidence: routing.confidence,

        candidates: (routing.candidates || []).slice(0, 5).map(c => ({ n: c.name, c: Math.round((c.confidence || 0) * 100) })),

      });

    }



    // 每日路由统计

    try {

      const dailyStatsFile = path.join(DEBUG_DIR, `route-stats-daily-${dateStr}.jsonl`);

      const complexity = routing._complexity || 'unknown';

      const isExempt = (routing._intents || []).some(i => MUST_INVOKE_EXEMPT_INTENTS.has(i));

      const mustInvoke = complexity === 'complex' ||

        (!isExempt && complexity === 'medium' && routing.confidence >= 0.5 &&

         routing.primary !== 'developer-expert' && routing.primary !== 'none');

      safeAppendJsonl(dailyStatsFile, {

        ts: entry.ts, date: dateStr,

        skill: routing.primary,

        confidence: routing.confidence,

        mustInvoke,

      });

    } catch {}

  } catch {}

}



/**

 * 写入路由状态文件 (供下游 hook 消费)

 * @param {string} traceId - 追踪 ID

 * @param {string} prompt - 用户输入

 * @param {object} intent - 意图分类结果

 * @param {object} routing - 路由结果

 * @param {string|null} sessionId - 会话 ID

 * @returns {object} 写入的状态对象

 */

function writeRouteState(traceId, prompt, intent, routing, sessionId) {

  const state = {

    traceId,

    ts: new Date().toISOString(),

    promptHash: crypto.createHash('sha256').update(prompt).digest('hex').slice(0, 12),

    promptRaw: sanitizePrompt(prompt.slice(0, 200)),

    intent: {

      intents: intent.intents,

      modifiers: intent.modifiers,

      entities: intent.entities,

      complexity: intent.complexity,

    },

    routing: {

      primary: routing.primary,

      candidates: routing.candidates,

      confidence: routing.confidence,

      chain: routing.chain,

      experiment: routing.experiment || null,

      domain: routing.domain || null,

      lastValidPrimary: routing.lastValidPrimary || null, // LVP_PERSIST_FIX_v1

    },

    recommendation: {

      action: routing.confidence >= 0.8 ? 'route' : routing.confidence >= 0.5 ? 'recommend' : 'fallback',

      skill: routing.primary,

    },

    mustInvoke: intent.complexity === 'complex' ||

      (!intent.intents.some(i => MUST_INVOKE_EXEMPT_INTENTS.has(i)) &&

       intent.complexity === 'medium' && routing.confidence >= 0.5 &&

       routing.primary !== 'developer-expert' && routing.primary !== 'none'),

    version: (() => { try { return require('./feature-flags.js').version; } catch { return 'v6.2'; } })(),

    sessionId: sessionId || null,

  };



  try {

    if (!fs.existsSync(DEBUG_DIR)) fs.mkdirSync(DEBUG_DIR, { recursive: true });

    const _tmpState = path.join(DEBUG_DIR, 'route-state-current.json.tmp.' + process.pid);

    fs.writeFileSync(_tmpState, JSON.stringify(state, null, 2) + '\n');
    try {
      fs.renameSync(_tmpState, path.join(DEBUG_DIR, 'route-state-current.json'));
    } catch {
      // Windows: rename may fail if target locked — write directly
      fs.writeFileSync(path.join(DEBUG_DIR, 'route-state-current.json'), JSON.stringify(state, null, 2) + '\n');
    }
  } catch {}



  // 注入 intent 信息供 appendRouteLog 统一计算 mustInvoke

  routing._complexity = intent.complexity;

  routing._intents = intent.intents;

  appendRouteLog(prompt, routing, traceId);



  // 路由遥测指标

  try {

    const telemetry = safeRequire(path.join(SCRIPTS_DIR, 'route-telemetry.js'));

    if (telemetry && telemetry.emitRouteMetric) {

      telemetry.emitRouteMetric({

        queryLength: (prompt || '').split(/\s+/).length,

        selectedSkill: routing.primary,

        topScore: routing.candidates?.[0]?.confidence || 0,

        gap12: (routing.candidates?.[0]?.confidence || 0) - (routing.candidates?.[1]?.confidence || 0),

        confidence: routing.confidence,

        rulesFired: routing._firedRules || [],

        coldStartApplied: routing._coldStartApplied || false,

        coldStartSkills: routing._coldStartSkills || [],

        latencyMs: Date.now() - (routing._startTs || Date.now()),

        experimentId: routing.experiment?.id || null,

      });

    }

  } catch {}



  return state;

}



module.exports = { writeRouteState, appendRouteLog };

