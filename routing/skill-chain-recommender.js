#!/usr/bin/env node
/**
 * 技能链推荐引擎 (v5.1)
 *
 * 基于 composable 关系图 + 工作流模式，
 * 推荐技能调用链 (最多 4 步)。
 *
 * 核心函数:
 *   buildComposableGraph(index) → 邻接表
 *   recommendChain(primarySkill, graph, workflowPatterns, maxLen) → 推荐链
 */

const fs = require('fs');
const path = require('path');

/**
 * 从 skills-index.json 构建 composable 关系邻接表
 * @param {Object} index - skills-index.json
 * @returns {Object} { skillName → { enhances, requires, enhancedBy } }
 */
function buildComposableGraph(index) {
  const graph = {};

  // 初始化所有技能
  for (const skill of (index.skills || [])) {
    graph[skill.name] = { enhances: [], requires: [], enhancedBy: [] };
  }

  // 填充关系
  for (const skill of (index.skills || [])) {
    const comp = skill.composable || {};

    if (comp.enhances) {
      for (const target of comp.enhances) {
        if (graph[skill.name]) {
          graph[skill.name].enhances.push(target);
        }
        // 反向关系
        if (graph[target]) {
          graph[target].enhancedBy.push(skill.name);
        }
      }
    }

    if (comp.requires) {
      for (const target of comp.requires) {
        if (graph[skill.name]) {
          graph[skill.name].requires.push(target);
        }
      }
    }
  }

  return graph;
}

/**
 * 推荐技能调用链
 * @param {string} primarySkill - 主技能
 * @param {Object} graph - buildComposableGraph 的结果
 * @param {Object} workflowPatterns - minePatterns 的结果 (可选)
 * @param {number} maxLen - 最大链长 (默认 4)
 * @returns {Array<{ chain: string[], score: number, reason: string }>} 推荐链列表
 */
function recommendChain(primarySkill, graph, workflowPatterns, maxLen = 4) {
  const chains = [];
  const node = graph[primarySkill];
  if (!node) return chains;

  // 策略 1: enhances 链 (A enhances B enhances C)
  const enhanceChain = [primarySkill];
  const visited = new Set([primarySkill]);
  let current = primarySkill;

  for (let i = 1; i < maxLen; i++) {
    const currentNode = graph[current];
    if (!currentNode || currentNode.enhances.length === 0) break;

    // 选择未访问过的 enhances 目标
    const next = currentNode.enhances.find(s => !visited.has(s) && graph[s]);
    if (!next) break;

    enhanceChain.push(next);
    visited.add(next);
    current = next;
  }

  if (enhanceChain.length >= 2) {
    chains.push({
      chain: enhanceChain,
      score: enhanceChain.length * 0.3,
      reason: 'composable-enhances',
    });
  }

  // 策略 2: requires 链 (先执行依赖, 再执行主技能)
  if (node.requires.length > 0) {
    const reqChain = [...node.requires.slice(0, maxLen - 1), primarySkill];
    chains.push({
      chain: reqChain,
      score: reqChain.length * 0.25,
      reason: 'composable-requires',
    });
  }

  // 策略 3: 工作流模式驱动的链
  if (workflowPatterns && workflowPatterns.bigrams) {
    const wfChain = [primarySkill];
    let wfCurrent = primarySkill;
    const wfVisited = new Set([primarySkill]);

    for (let i = 1; i < maxLen; i++) {
      // 找 bigram 中 wfCurrent 的最高频后继
      let bestNext = null;
      let bestCount = 0;

      for (const [key, count] of Object.entries(workflowPatterns.bigrams)) {
        const [from, to] = key.split('→');
        if (from === wfCurrent && !wfVisited.has(to) && count > bestCount) {
          bestNext = to;
          bestCount = count;
        }
      }

      if (!bestNext) break;
      wfChain.push(bestNext);
      wfVisited.add(bestNext);
      wfCurrent = bestNext;
    }

    if (wfChain.length >= 2) {
      chains.push({
        chain: wfChain,
        score: wfChain.length * 0.2 + 0.1,
        reason: 'workflow-pattern',
      });
    }
  }

  // 策略 4: enhancedBy → primarySkill → enhances (上下文丰富链)
  if (node.enhancedBy.length > 0 && node.enhances.length > 0) {
    const contextChain = [
      node.enhancedBy[0],
      primarySkill,
      ...node.enhances.slice(0, maxLen - 2),
    ].slice(0, maxLen);

    chains.push({
      chain: contextChain,
      score: contextChain.length * 0.2,
      reason: 'context-bridge',
    });
  }

  // 按分数排序并去重
  chains.sort((a, b) => b.score - a.score);
  return chains;
}

// 模块导出
if (typeof module !== 'undefined') {
  module.exports = { buildComposableGraph, recommendChain };
}

// CLI 入口
if (require.main === module) {
  const detectClaudeRoot = () => require('./paths.config.js').PATHS.root;

  const ROOT = detectClaudeRoot();
  const indexFile = path.join(ROOT, 'skills-index.json');

  if (!fs.existsSync(indexFile)) {
    console.error('skills-index.json 不存在');
    process.exit(1);
  }

  const skill = process.argv[2];
  if (!skill) {
    console.log('Usage: node skill-chain-recommender.js <skillName>');
    process.exit(0);
  }

  const index = JSON.parse(fs.readFileSync(indexFile, 'utf8'));
  const graph = buildComposableGraph(index);
  const chains = recommendChain(skill, graph, null, 4);

  console.log(`=== 技能链推荐: ${skill} ===`);
  if (chains.length === 0) {
    console.log('无推荐链');
  } else {
    for (const c of chains) {
      console.log(`  [${c.reason}] ${c.chain.join(' → ')} (score: ${c.score.toFixed(2)})`);
    }
  }
}
