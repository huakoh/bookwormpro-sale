#!/usr/bin/env node
/**
 * TF-IDF 关键词加权引擎 (v4.9)
 *
 * 为 skills-index.json 中的关键词计算 TF-IDF 权重，
 * 区分高区分度关键词 (如 "pytorch") 和低区分度关键词 (如 "部署")。
 *
 * 核心函数:
 *   buildCorpus(skills) → 倒排索引 {keyword → Set<skillName>}
 *   computeIDF(df, N) → 平滑 IDF 值
 *   applyTFIDFWeights(index) → 为每个关键词附加 tfidfWeight 字段
 */

const fs = require('fs');
const path = require('path');

/**
 * 构建倒排索引: 每个关键词出现在哪些技能中
 * @param {Array} skills - skills-index.json 中的 skills 数组
 * @returns {Map<string, Set<string>>} 关键词 → 技能名集合
 */
function buildCorpus(skills) {
  const corpus = new Map();
  for (const skill of skills) {
    for (const { keyword } of (skill.keywords || [])) {
      const kw = (keyword || "").toLowerCase();
      if (!corpus.has(kw)) corpus.set(kw, new Set());
      corpus.get(kw).add(skill.name);
    }
  }
  return corpus;
}

/**
 * 计算平滑 IDF 值
 * 公式: log((N-df+0.5)/(df+0.5) + 1) — BM25 Robertson-Walker IDF
 * @param {number} df - 文档频率 (出现在多少个技能中)
 * @param {number} N - 技能总数
 * @returns {number} IDF 值
 */
function computeIDF(df, N) {
  // P1-FIX: 统一为 BM25 Robertson-Walker IDF (与 route-analyzer.js 一致)
  return Math.log((N - df + 0.5) / (df + 0.5) + 1);
}

/**
 * 为索引中的每个关键词附加 tfidfWeight 字段
 * tfidfWeight = 原始 weight * IDF
 * @param {Object} index - skills-index.json 完整对象
 */
function applyTFIDFWeights(index) {
  const skills = index.skills || [];
  const N = skills.length;
  const corpus = buildCorpus(skills);

  for (const skill of skills) {
    for (const kwEntry of (skill.keywords || [])) {
      const kw = (kwEntry.keyword || "").toLowerCase();
      const df = corpus.has(kw) ? corpus.get(kw).size : 0;
      const idf = computeIDF(df, N);
      // TF 简化为 1 (布尔频率: 关键词在技能中出现即为 1)
      kwEntry.tfidfWeight = Math.round(kwEntry.weight * idf * 100) / 100;
    }
  }
}

// 模块导出
if (typeof module !== 'undefined') {
  module.exports = { buildCorpus, computeIDF, applyTFIDFWeights };
}

// CLI 入口: 可独立运行查看统计
if (require.main === module) {
  const detectClaudeRoot = () => require('./paths.config.js').PATHS.root;

  const ROOT = detectClaudeRoot();
  const indexFile = path.join(ROOT, 'skills-index.json');

  if (!fs.existsSync(indexFile)) {
    console.error('skills-index.json 不存在，请先运行 generate-skill-index.js');
    process.exit(1);
  }

  const index = JSON.parse(fs.readFileSync(indexFile, 'utf8'));
  const corpus = buildCorpus(index.skills);
  const N = index.skills.length;

  console.log(`=== TF-IDF 统计 ===`);
  console.log(`技能总数: ${N}`);
  console.log(`唯一关键词: ${corpus.size}`);
  console.log('');

  // 高区分度关键词 (仅出现在 1-2 个技能中)
  const highIDF = [];
  for (const [kw, skills] of corpus) {
    if (skills.size <= 2) {
      highIDF.push({ keyword: kw, df: skills.size, idf: computeIDF(skills.size, N) });
    }
  }
  highIDF.sort((a, b) => b.idf - a.idf);

  console.log('高区分度关键词 (df<=2, Top 20):');
  for (const item of highIDF.slice(0, 20)) {
    console.log(`  ${item.keyword.padEnd(25)} df=${item.df}  idf=${item.idf.toFixed(2)}`);
  }

  // 低区分度关键词 (出现在 >10 个技能中)
  const lowIDF = [];
  for (const [kw, skills] of corpus) {
    if (skills.size > 10) {
      lowIDF.push({ keyword: kw, df: skills.size, idf: computeIDF(skills.size, N) });
    }
  }
  lowIDF.sort((a, b) => a.idf - b.idf);

  console.log('\n低区分度关键词 (df>10):');
  for (const item of lowIDF) {
    console.log(`  ${item.keyword.padEnd(25)} df=${item.df}  idf=${item.idf.toFixed(2)}`);
  }
}
