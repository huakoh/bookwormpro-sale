#!/usr/bin/env node
/**
 * BM25 参数调优器
 * 对 golden-set.json 进行网格搜索，找到最优 (k1, b) 参数对
 */
const fs = require('fs');
const path = require('path');

const ROOT = require('./paths.config.js').PATHS.root;
const goldenSetFile = path.join(ROOT, 'scripts', 'golden-set.json');
const indexFile = path.join(ROOT, 'skills-index-lite.json');

if (!fs.existsSync(goldenSetFile)) {
  console.error('golden-set.json not found');
  process.exit(1);
}
if (!fs.existsSync(indexFile)) {
  console.error('skills-index-lite.json not found');
  process.exit(1);
}

const goldenSet = JSON.parse(fs.readFileSync(goldenSetFile, 'utf8'));
const index = JSON.parse(fs.readFileSync(indexFile, 'utf8'));
const routeAnalyzer = require('./route-analyzer.js');

// 网格搜索参数
const K1_VALUES = [0.5, 0.8, 1.0, 1.2, 1.5, 2.0];
const B_VALUES = [0.0, 0.25, 0.5, 0.75];

/**
 * 使用自定义 k1, b 计算单项 BM25 分值
 */
function computeBM25(tf, idf, dl, avgdl, k1, b) {
  const numerator = tf * (k1 + 1);
  const denominator = tf + k1 * (1 - b + b * dl / avgdl);
  return idf * numerator / denominator;
}

/**
 * 对单个技能评分 (简化版，只用全局 IDF，不含 domain blending)
 */
function scoreSkillCustom(skill, queryTokens, N, dfMap, avgdl, k1, b) {
  let totalScore = 0;
  const dl = (skill.keywords || []).length;
  const IDF_FLOOR = Math.log(2);

  for (const kwEntry of (skill.keywords || [])) {
    const kwLower = (kwEntry.keyword || "").toLowerCase();
    const baseWeight = kwEntry.tfidfWeight || kwEntry.weight || 1;

    // 全局 IDF
    const df = dfMap.get(kwLower) || 0;
    const rawIdf = Math.log((N - df + 0.5) / (df + 0.5) + 1);
    const kwIDF = Math.max(rawIdf, IDF_FLOOR);

    // 精确匹配
    if (queryTokens.has(kwLower)) {
      totalScore += computeBM25(baseWeight, kwIDF, dl, avgdl, k1, b);
      continue;
    }

    // 部分匹配 (折扣 0.6)
    for (const token of queryTokens) {
      if (token.length >= 3 && kwLower.includes(token)) {
        totalScore += computeBM25(baseWeight * 0.6, kwIDF, dl, avgdl, k1, b);
        break;
      }
      if (kwLower.length >= 3 && token.includes(kwLower)) {
        totalScore += computeBM25(baseWeight * 0.6, kwIDF, dl, avgdl, k1, b);
        break;
      }
    }
  }

  // 休眠降权
  if (skill.coldPenalty && totalScore > 0) {
    totalScore *= skill.coldPenalty;
  }

  return totalScore;
}

/**
 * 构建全局 DF 表
 */
function buildDFMap(skills) {
  const dfMap = new Map();
  for (const skill of skills) {
    const seen = new Set();
    for (const kw of (skill.keywords || [])) {
      const k = (kw.keyword || "").toLowerCase();
      if (!seen.has(k)) {
        seen.add(k);
        dfMap.set(k, (dfMap.get(k) || 0) + 1);
      }
    }
  }
  return dfMap;
}

// 主流程
const skills = index.skills || [];
const N = skills.length;
const dfMap = buildDFMap(skills);

// 计算 avgdl
let totalDl = 0;
for (const s of skills) totalDl += (s.keywords || []).length;
const avgdl = N > 0 ? totalDl / N : 1;

console.log('=== BM25 Parameter Tuning ===');
console.log('Skills:', N, '| Golden set:', goldenSet.entries.length, '| avgdl:', avgdl.toFixed(1));
console.log('');

const results = [];

for (const k1 of K1_VALUES) {
  for (const b of B_VALUES) {
    let rrSum = 0;
    let p1Hits = 0;
    let evaluated = 0;

    for (const entry of goldenSet.entries) {
      const queryTokens = routeAnalyzer.tokenize(entry.query);
      const correctSkill = entry.expectedSkill;

      const scores = skills.map(skill => ({
        name: skill.name,
        score: scoreSkillCustom(skill, queryTokens, N, dfMap, avgdl, k1, b),
      }));
      scores.sort((a, b_) => b_.score - a.score);

      const rank = scores.findIndex(s => s.name === correctSkill) + 1;
      if (rank > 0) {
        rrSum += 1.0 / rank;
        if (rank === 1) p1Hits++;
      }
      evaluated++;
    }

    const mrr = evaluated > 0 ? rrSum / evaluated : 0;
    const p1 = evaluated > 0 ? p1Hits / evaluated : 0;
    results.push({ k1, b, mrr: Math.round(mrr * 1000) / 1000, p1: Math.round(p1 * 1000) / 1000 });
  }
}

// 按 MRR 排序
results.sort((a, b_) => b_.mrr - a.mrr);

console.log('Top 10 parameter combinations:');
console.log('  k1    b     MRR     P@1');
console.log('  ----  ----  ------  ------');
for (const r of results.slice(0, 10)) {
  console.log('  ' + r.k1.toFixed(1).padEnd(4) + '  ' + r.b.toFixed(2).padEnd(4) + '  ' + r.mrr.toFixed(3).padEnd(6) + '  ' + r.p1.toFixed(3));
}

const best = results[0];
console.log('');
console.log('Best params: k1=' + best.k1 + ', b=' + best.b + ' (MRR=' + best.mrr + ', P@1=' + best.p1 + ')');

// 输出 JSON
if (process.argv.includes('--json')) {
  console.log(JSON.stringify({ best, allResults: results }, null, 2));
}
