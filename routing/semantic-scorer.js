#!/usr/bin/env node
/**
 * 语义评分引擎 (v5.9)
 *
 * 基于 TF-IDF 向量余弦相似度的轻量级语义匹配。
 * 无需外部 embedding 模型，纯 JS 实现。
 *
 * 原理:
 *   1. 为每个技能构建 TF-IDF 向量 (基于 keywords + description)
 *   2. 用户查询也生成 TF-IDF 向量
 *   3. 余弦相似度作为语义分数
 *
 * 模块导出:
 *   buildVectors(index) → { skillVectors, idfMap, vocabulary }
 *   queryVector(tokens, idfMap, vocabulary) → Float64Array
 *   cosineSimilarity(vecA, vecB) → number (0~1)
 *   semanticScore(query, index, cache) → { name, score }[]
 */

const path = require('path');
const fs = require('fs');

const detectClaudeRoot = () => require('./paths.config.js').PATHS.root;

/**
 * 简易分词 (与 route-analyzer.js tokenize 保持一致)
 */
function tokenize(text) {
  const tokens = [];
  const cnChars = (text || '').match(/[\u4e00-\u9fff]+/g) || [];
  for (const chunk of cnChars) {
    for (let len = 2; len <= Math.min(4, chunk.length); len++) {
      for (let i = 0; i <= chunk.length - len; i++) {
        tokens.push(chunk.slice(i, i + len).toLowerCase());
      }
    }
  }
  const enWords = (text || '').match(/[A-Za-z][\w.-]*/g) || [];
  for (const w of enWords) {
    tokens.push(w.toLowerCase());
  }
  return tokens;
}

/**
 * P1-3: 安全求 Map/迭代器最大值 (避免 Math.max(...) 在大集合时栈溢出)
 * @param {Iterable<number>} iterable - 可迭代数值集合
 * @param {number} defaultVal - 无元素时返回的默认值
 * @returns {number}
 */
function iterableMax(iterable, defaultVal) {
  let max = defaultVal;
  for (const v of iterable) {
    if (v > max) max = v;
  }
  return max;
}

/**
 * 构建 TF-IDF 向量空间
 * @param {Object} index - skills-index.json
 * @returns {{ skillVectors: Map, idfMap: Map, vocabulary: string[], vocabIndex: Map }}
 */
function buildVectors(index) {
  const skills = index.skills || [];
  const N = skills.length;

  // Phase 1: 收集所有文档的词频
  const docTokens = []; // Array<Map<token, count>>
  const df = new Map(); // document frequency

  for (const skill of skills) {
    const text = [
      skill.name,
      skill.description || '',
      ...(skill.keywords || []).map(k => k.keyword),
    ].join(' ');

    const tokens = tokenize(text);
    const tf = new Map();
    for (const t of tokens) {
      tf.set(t, (tf.get(t) || 0) + 1);
    }
    docTokens.push(tf);

    // 统计 document frequency
    for (const t of tf.keys()) {
      df.set(t, (df.get(t) || 0) + 1);
    }
  }

  // Phase 2: 构建词汇表 (只保留出现在 2+ 文档中但不超过 80% 文档的词)
  const vocabulary = [];
  const vocabIndex = new Map();
  for (const [token, count] of df.entries()) {
    if (count >= 2 && count <= N * 0.8) {
      vocabIndex.set(token, vocabulary.length);
      vocabulary.push(token);
    }
  }

  // Phase 3: IDF 计算
  const idfMap = new Map();
  for (const token of vocabulary) {
    const docFreq = df.get(token) || 0;
    idfMap.set(token, Math.log((N + 1) / (docFreq + 1)) + 1);
  }

  // Phase 4: 为每个技能构建 TF-IDF 向量
  const dim = vocabulary.length;
  const skillVectors = new Map();

  for (let i = 0; i < skills.length; i++) {
    const vec = new Float64Array(dim);
    const tf = docTokens[i];
    // P1-3 修复: 用循环求最大值，避免 Math.max(...tf.values()) 在大 Map 时栈溢出
    const maxTF = iterableMax(tf.values(), 1);

    for (const [token, count] of tf.entries()) {
      const idx = vocabIndex.get(token);
      if (idx !== undefined) {
        // 归一化 TF * IDF
        vec[idx] = (count / maxTF) * (idfMap.get(token) || 0);
      }
    }

    // L2 归一化
    let norm = 0;
    for (let j = 0; j < dim; j++) norm += vec[j] * vec[j];
    norm = Math.sqrt(norm);
    if (norm > 0) {
      for (let j = 0; j < dim; j++) vec[j] /= norm;
    }

    skillVectors.set(skills[i].name, vec);
  }

  return { skillVectors, idfMap, vocabulary, vocabIndex, dim };
}

/**
 * 将查询文本转为 TF-IDF 向量
 * @param {string[]} tokens - 查询分词结果
 * @param {Map} idfMap - IDF 表
 * @param {Map} vocabIndex - 词汇→索引映射
 * @param {number} dim - 向量维度
 * @returns {Float64Array}
 */
function queryVector(tokens, idfMap, vocabIndex, dim) {
  const vec = new Float64Array(dim);
  const tf = new Map();
  for (const t of tokens) tf.set(t, (tf.get(t) || 0) + 1);
  // P1-3 修复: 用循环求最大值，避免 Math.max(...tf.values()) 在大 Map 时栈溢出
  const maxTF = iterableMax(tf.values(), 1);

  for (const [token, count] of tf.entries()) {
    const idx = vocabIndex.get(token);
    if (idx !== undefined) {
      vec[idx] = (count / maxTF) * (idfMap.get(token) || 0);
    }
  }

  // L2 归一化
  let norm = 0;
  for (let j = 0; j < dim; j++) norm += vec[j] * vec[j];
  norm = Math.sqrt(norm);
  if (norm > 0) {
    for (let j = 0; j < dim; j++) vec[j] /= norm;
  }
  return vec;
}

/**
 * 余弦相似度
 */
function cosineSimilarity(vecA, vecB) {
  if (vecA.length !== vecB.length) return 0;
  let dot = 0;
  for (let i = 0; i < vecA.length; i++) dot += vecA[i] * vecB[i];
  return Math.max(0, Math.min(1, dot)); // L2 归一化后 dot = cosine
}

// 缓存向量空间 (V05 修复: 添加 mtime 检查防止缓存过期)
let _cache = null;
let _cacheMtime = 0;

function _getIndexMtime() {
  try {
    const ROOT = typeof detectClaudeRoot === 'function' ? detectClaudeRoot() : '';
    const indexFile = path.join(ROOT, 'skills-index.json');
    return require('fs').statSync(indexFile).mtimeMs;
  } catch { return 0; }
}

/**
 * 语义评分
 * @param {string} query - 用户查询
 * @param {Object} index - skills-index.json
 * @returns {{ name: string, score: number }[]}
 */
function semanticScore(query, index) {
  const currentMtime = _getIndexMtime();
  if (!_cache || (currentMtime > 0 && currentMtime !== _cacheMtime)) {
    _cache = buildVectors(index);
    _cacheMtime = currentMtime;
  }

  const tokens = tokenize(query);
  const qVec = queryVector(tokens, _cache.idfMap, _cache.vocabIndex, _cache.dim);

  const scores = [];
  for (const [name, sVec] of _cache.skillVectors.entries()) {
    const sim = cosineSimilarity(qVec, sVec);
    if (sim > 0.01) {
      scores.push({ name, score: Math.round(sim * 100) / 100 });
    }
  }

  return scores.sort((a, b) => b.score - a.score);
}

function clearCache() {
  _cache = null;
}

// 模块导出
if (typeof module !== 'undefined') {
  module.exports = {
    buildVectors, queryVector, cosineSimilarity, semanticScore,
    tokenize, clearCache,
  };
}

// CLI 入口
if (require.main === module) {
  const ROOT = detectClaudeRoot();
  const indexFile = path.join(ROOT, 'skills-index.json');

  try {
    const index = JSON.parse(fs.readFileSync(indexFile, 'utf8'));
    const vectors = buildVectors(index);
    console.log(`向量空间: ${vectors.vocabulary.length} 维, ${vectors.skillVectors.size} 技能`);

    const testQueries = [
      '帮我用 React 写一个表单组件',
      'PyTorch 训练图像分类模型',
      'Docker 部署到生产环境',
      '写一份 BP 商业计划书',
      '数据库查询太慢了怎么办',
    ];

    for (const q of testQueries) {
      const results = semanticScore(q, index);
      const top3 = results.slice(0, 3).map(r => `${r.name}(${r.score})`).join(', ');
      console.log(`\n"${q}"\n  → ${top3}`);
    }
  } catch (e) {
    console.error('Error:', e.message);
  }
}
