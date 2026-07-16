'use strict';

/**
 * BWR 指令构建器 — 生成 [BWR:xxx] 路由注入文本
 * @module scripts/bwr-builder
 *
 * 从 route-interceptor-bundle.js 提取 (Phase 0 宪法合规拆分)
 * 原始位置: bundle L440-477
 */

// MUST_INVOKE 豁免白名单
// L5-MUST-INVOKE-EVERY (2026-04-25 L5 修复 — meta 移出豁免, some→every)
// 真豁免清单: 仅纯翻译/解释/问候/记忆/对话连续意图豁免 MUST_INVOKE_SKILL
// 'meta' 移除原因: 审计/路由分析常被分类为 meta+x 复合意图, 历史用 some 判定导致豁免逃逸
const MUST_INVOKE_EXEMPT_INTENTS = new Set(['translate', 'explain', 'greeting', 'remember', 'continue', 'select', 'confirm']);

/**
 * 构建 [BWR] 注入文本
 * @param {string} traceId - 路由追踪 ID
 * @param {object} intent - 意图分类结果 { intents, complexity }
 * @param {object} routing - 路由结果 { primary, candidates, confidence, chain }
 * @param {boolean} inherited - 是否继承自上一轮
 * @returns {string} BWR 指令文本
 */
function buildBWRDirective(traceId, intent, routing, inherited) {
  const { intents, complexity } = intent;
  const { primary, candidates, confidence, chain } = routing;

  // simple 分流: 无可继承上下文时才 skip
  if (complexity === 'simple' && !inherited) {
    return `[BWR:skip] 简单查询，直接回复`;
  }

  const candidateStr = candidates
    .slice(0, 4)
    .map(c => `${c.name}(${(c.confidence * 100).toFixed(0)}%)`)
    .join(', ');

  const chainStr = chain.length > 0 ? chain.join(' → ') : '无';
  const confPct = (confidence * 100).toFixed(0);
  const inheritTag = inherited ? ' (inherited)' : '';

  let directive = `[BWR:${traceId}] 置信度 ${confPct}%${inheritTag} | 意图: ${intents.join(',')} | 复杂度: ${complexity}\n`;
  directive += `├─ 主路由: ${primary}\n`;
  directive += `├─ 候选: [${candidateStr}]\n`;
  directive += `├─ 技能链: ${chainStr}\n`;

  // complex 优先级高于豁免
  if (complexity === 'complex') {
    directive += `└─ [MUST_INVOKE_SKILL: ${primary}] 复杂任务，必须通过 Skill 工具调用 /${primary} 加载完整专家 prompt。如跨 3+ 领域则改用 orchestrator Agent。`;
  } else if (intents.length > 0 && intents.every(i => MUST_INVOKE_EXEMPT_INTENTS.has(i))) {
    directive += `└─ 执行: 使用 /${primary} 处理此请求 (豁免强制调用: ${intents.join(',')})`;
  } else if (complexity === 'medium' && confidence >= 0.5 && primary !== 'none' && primary !== 'developer-expert') {
    directive += `└─ [MUST_INVOKE_SKILL: ${primary}] 中等复杂度，必须通过 Skill 工具调用 /${primary} 以获取完整专业指导，不可仅参考技能名称回答。`;
  } else {
    directive += `└─ 执行: 使用 /${primary} 处理此请求`;
  }

  return directive;
}

module.exports = { buildBWRDirective, MUST_INVOKE_EXEMPT_INTENTS };
