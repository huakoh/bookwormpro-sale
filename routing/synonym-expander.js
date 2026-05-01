#!/usr/bin/env node
/**
 * 同义词展开器 (v4.9)
 *
 * 加载 synonyms.json，将查询 token 展开为同义词组。
 * 供 route-analyzer.js 和 route-feedback.js 的 tokenize() 使用。
 *
 * 核心函数:
 *   loadSynonymMap() → Map<word, string[]> 单例缓存
 *   expandSynonyms(tokens) → 展开后的 Set<string>
 */

const fs = require('fs');
const path = require('path');

// 单例缓存
let _synonymMap = null;

/**
 * 加载同义词映射表 (单例)
 * @returns {Map<string, string[]>} 每个词 → 所属组的全部同义词
 */
function loadSynonymMap() {
  if (_synonymMap) return _synonymMap;

  _synonymMap = new Map();

  try {
    const selfDir = path.dirname(__filename);
    const synFile = path.join(selfDir, 'synonyms.json');
    if (!fs.existsSync(synFile)) return _synonymMap;

    const data = JSON.parse(fs.readFileSync(synFile, 'utf8'));
    for (const group of (data.groups || [])) {
      const words = (group.words || []).map(w => w.toLowerCase());
      for (const word of words) {
        // 每个词映射到组内其他所有词
        const others = words.filter(w => w !== word);
        if (_synonymMap.has(word)) {
          // 合并多组同义词
          const existing = _synonymMap.get(word);
          for (const o of others) {
            if (!existing.includes(o)) existing.push(o);
          }
        } else {
          _synonymMap.set(word, [...others]);
        }
      }
    }
  } catch {}

  return _synonymMap;
}

/**
 * 展开 token 集合为包含同义词的更大集合
 * @param {Set<string>|Array<string>} tokens - 原始 token 集合
 * @returns {Set<string>} 展开后的 token 集合 (包含原始 + 同义词)
 */
function expandSynonyms(tokens) {
  const synMap = loadSynonymMap();
  const expanded = new Set(tokens);

  for (const token of tokens) {
    const synonyms = synMap.get(token.toLowerCase());
    if (synonyms) {
      for (const syn of synonyms) {
        expanded.add(syn);
      }
    }
  }

  return expanded;
}

/**
 * 重置单例缓存 (测试用)
 */
/**
 * P1-FIX: 加权同义词展开
 * 原词权重 1.0, 主同义词 0.7, 次同义词 0.4
 * @param {Set<string>} tokens
 * @returns {{ expanded: Set<string>, weights: Map<string, number> }}
 */
function expandSynonymsWeighted(tokens) {
  const synMap = loadSynonymMap();
  const expanded = new Set(tokens);
  const weights = new Map();

  // 原词权重 1.0
  for (const t of tokens) weights.set(t, 1.0);

  for (const token of tokens) {
    const synonyms = synMap.get(token.toLowerCase());
    if (synonyms) {
      for (let i = 0; i < synonyms.length; i++) {
        const syn = synonyms[i];
        expanded.add(syn);
        // 前 3 个同义词为主同义词(0.7)，其余为次(0.4)
        const w = i < 3 ? 0.7 : 0.4;
        if (!weights.has(syn) || weights.get(syn) < w) {
          weights.set(syn, w);
        }
      }
    }
  }
  return { expanded, weights };
}

function resetCache() {
  _synonymMap = null;
}

// 模块导出
if (typeof module !== 'undefined') {
  module.exports = { loadSynonymMap, expandSynonyms, expandSynonymsWeighted, resetCache };
}

// CLI 入口
if (require.main === module) {
  const query = process.argv.slice(2).join(' ');
  if (!query) {
    console.log('Usage: node synonym-expander.js <tokens...>');
    console.log('Example: node synonym-expander.js 前端 部署');
    process.exit(0);
  }

  const tokens = new Set(query.toLowerCase().split(/\s+/));
  const expanded = expandSynonyms(tokens);

  console.log('原始 tokens:', Array.from(tokens).join(', '));
  console.log('展开后:', Array.from(expanded).join(', '));
  console.log(`展开: ${tokens.size} → ${expanded.size} (+${expanded.size - tokens.size})`);
}
