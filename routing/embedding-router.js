#!/usr/bin/env node
/**
 * 向量嵌入路由辅助模块 (v6.0 Phase 3)
 *
 * 当前实现: TF-IDF 余弦相似度增强版（不依赖外部 LLM API）
 * 未来预留: LLM Gateway embedding 接口
 *
 * 工作原理:
 *   1. 对每个技能的描述文本 + 关键词构建更丰富的 TF-IDF 向量
 *      (相比 semantic-scorer.js，增加了描述权重加成和同义词扩展)
 *   2. 用户查询同样构建向量
 *   3. 余弦相似度计算并返回排序结果
 *
 * 触发条件:
 *   当 BM25 top-2 分数差距 < 15% 时，由路由引擎调用辅助决策
 *
 * 缓存策略:
 *   技能描述向量缓存到 debug/.embedding-cache.json
 *   仅在 skills-index.json 的 mtime 变更时重建
 *
 * 关键约束:
 *   - fail-open: 任何异常不影响主路由流程
 *   - 预留 LLM Gateway 接口（当前回退到 TF-IDF）
 */

const fs = require('fs');
const path = require('path');

const detectClaudeRoot = () => require('./paths.config.js').PATHS.root;

const ROOT = detectClaudeRoot();
const DEBUG_DIR = path.join(ROOT, 'debug');
const INDEX_FILE = path.join(ROOT, 'skills-index.json');
const CACHE_FILE = path.join(DEBUG_DIR, '.embedding-cache.json');

// 向量维度上限（防止低频词爆炸）
const MAX_VOCAB_SIZE = 3000;
// 最低文档频率（出现在至少 2 个文档）
const MIN_DF = 2;
// 最高文档频率比例（不超过 70% 文档出现的词视为停用词）
const MAX_DF_RATIO = 0.70;

// 描述文本在向量构建中的权重倍数（相对于关键词）
const DESC_WEIGHT_FACTOR = 1.5;

// 内存缓存（跨调用复用）
let _vectorCache = null;

// =====================================================
// 内部: TF-IDF 向量构建
// =====================================================

/**
 * 分词函数（增强版: 中文滑动窗口 + 英文单词 + 2-gram 组合）
 * @param {string} text
 * @returns {string[]} token 列表（允许重复，保留词频信息）
 */
function tokenizeText(text) {
  const tokens = [];
  if (!text) return tokens;

  const textLower = text.toLowerCase();

  // 中文: 2-4 字滑动窗口
  const cnChars = textLower.match(/[\u4e00-\u9fff]+/g) || [];
  for (const chunk of cnChars) {
    for (let len = 2; len <= Math.min(4, chunk.length); len++) {
      for (let i = 0; i <= chunk.length - len; i++) {
        tokens.push(chunk.slice(i, i + len));
      }
    }
  }

  // 英文: 完整单词（允许连字符）
  const enWords = textLower.match(/[a-z][a-z0-9.-]*/g) || [];
  for (const w of enWords) {
    if (w.length >= 2) tokens.push(w);
    // 拆分连字符词
    const parts = w.split(/[-./]/);
    for (const p of parts) {
      if (p.length >= 2 && p !== w) tokens.push(p);
    }
  }

  return tokens;
}

/**
 * 将技能信息转为文档文本
 * @param {Object} skill - skills-index 中的技能项
 * @param {number} descFactor - 描述文本权重倍数
 * @returns {string[]} token 列表（描述按权重重复）
 */
function skillToTokens(skill, descFactor) {
  const tokens = [];

  // 技能名称（高权重 × 3）
  const nameTokens = tokenizeText(skill.name);
  for (let i = 0; i < 3; i++) tokens.push(...nameTokens);

  // 描述文本（权重 × descFactor）
  const descTokens = tokenizeText(skill.description || '');
  const descRepeat = Math.max(1, Math.round(descFactor));
  for (let i = 0; i < descRepeat; i++) tokens.push(...descTokens);

  // 关键词（权重 × keyword.weight，简化为重复次数）
  for (const kw of (skill.keywords || [])) {
    const kwTokens = tokenizeText(kw.keyword);
    const repeat = Math.max(1, Math.round((kw.weight || 1) * 0.5));
    for (let i = 0; i < repeat; i++) tokens.push(...kwTokens);
  }

  return tokens;
}

/**
 * 构建 TF-IDF 向量空间
 * @param {Object} index - skills-index.json
 * @returns {{ skillVectors: Map, idfMap: Map, vocabulary: string[], vocabIndex: Map, dim: number }}
 */
function buildEmbeddingVectors(index) {
  const skills = index.skills || [];
  const N = skills.length;

  // Phase 1: 为每个技能收集 token 列表
  const docTokenLists = [];
  const df = new Map(); // token → 文档频率

  for (const skill of skills) {
    const tokens = skillToTokens(skill, DESC_WEIGHT_FACTOR);
    // 构建 TF 映射
    const tf = new Map();
    for (const t of tokens) {
      tf.set(t, (tf.get(t) || 0) + 1);
    }
    docTokenLists.push(tf);

    // 统计 DF
    for (const t of tf.keys()) {
      df.set(t, (df.get(t) || 0) + 1);
    }
  }

  // Phase 2: 构建词汇表（过滤低频/高频词，限制大小）
  const candidates = [];
  for (const [token, count] of df.entries()) {
    if (count >= MIN_DF && count <= N * MAX_DF_RATIO) {
      // IDF 分数作为排序依据（高 IDF = 更具区分性）
      const idf = Math.log((N + 1) / (count + 1)) + 1;
      candidates.push({ token, count, idf });
    }
  }
  // 按 IDF 降序排序，取前 MAX_VOCAB_SIZE
  candidates.sort((a, b) => b.idf - a.idf);
  const topCandidates = candidates.slice(0, MAX_VOCAB_SIZE);

  const vocabulary = topCandidates.map(c => c.token);
  const vocabIndex = new Map();
  for (let i = 0; i < vocabulary.length; i++) {
    vocabIndex.set(vocabulary[i], i);
  }

  // Phase 3: IDF 计算
  const idfMap = new Map();
  for (const { token } of topCandidates) {
    const docFreq = df.get(token) || 0;
    idfMap.set(token, Math.log((N + 1) / (docFreq + 1)) + 1);
  }

  // Phase 4: 为每个技能构建 TF-IDF 向量（L2 归一化）
  const dim = vocabulary.length;
  const skillVectors = new Map();

  for (let i = 0; i < skills.length; i++) {
    const vec = new Float64Array(dim);
    const tf = docTokenLists[i];
    // 用循环求最大值，避免大 Map 时 Math.max(...tf.values()) 栈溢出
    let maxTF = 1;
    for (const v of tf.values()) if (v > maxTF) maxTF = v;

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

    skillVectors.set(skills[i].name, vec);
  }

  return { skillVectors, idfMap, vocabulary, vocabIndex, dim };
}

/**
 * 将查询文本转为 TF-IDF 向量
 * @param {string} queryText - 原始查询
 * @param {Map} idfMap
 * @param {Map} vocabIndex
 * @param {number} dim
 * @returns {Float64Array}
 */
function buildQueryVector(queryText, idfMap, vocabIndex, dim) {
  const tokens = tokenizeText(queryText);
  const tf = new Map();
  for (const t of tokens) tf.set(t, (tf.get(t) || 0) + 1);
  // 用循环求最大值，避免大 Map 时 Math.max(...tf.values()) 栈溢出
  let maxTF = 1;
  for (const v of tf.values()) if (v > maxTF) maxTF = v;

  const vec = new Float64Array(dim);
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
 * 余弦相似度（L2 归一化后直接点积）
 * @param {Float64Array} vecA
 * @param {Float64Array} vecB
 * @returns {number} 0~1
 */
function cosineSimilarity(vecA, vecB) {
  if (vecA.length !== vecB.length) return 0;
  let dot = 0;
  for (let i = 0; i < vecA.length; i++) dot += vecA[i] * vecB[i];
  return Math.max(0, Math.min(1, dot));
}

// =====================================================
// 内部: 向量缓存管理
// =====================================================

/**
 * 获取 skills-index.json 的 mtime（用于缓存失效判断）
 * @returns {number} 时间戳毫秒，失败返回 0
 */
function getIndexMtime() {
  try {
    return fs.statSync(INDEX_FILE).mtimeMs;
  } catch {
    return 0;
  }
}

/**
 * 从磁盘加载缓存（如果 mtime 匹配且格式有效）
 * @param {number} currentMtime
 * @returns {Object|null} 向量数据或 null
 */
function loadCacheFromDisk(currentMtime) {
  try {
    if (!fs.existsSync(CACHE_FILE)) return null;
    const raw = JSON.parse(fs.readFileSync(CACHE_FILE, 'utf8'));
    // 缓存校验: mtime 必须匹配
    if (raw.indexMtime !== currentMtime) return null;
    if (!raw.vocabulary || !raw.idfData || !raw.vectorData) return null;

    // 反序列化向量数据
    const vocabIndex = new Map();
    const vocabulary = raw.vocabulary;
    for (let i = 0; i < vocabulary.length; i++) {
      vocabIndex.set(vocabulary[i], i);
    }

    const idfMap = new Map(raw.idfData);
    const skillVectors = new Map();
    const dim = vocabulary.length;

    for (const [name, arr] of Object.entries(raw.vectorData)) {
      skillVectors.set(name, new Float64Array(arr));
    }

    return { skillVectors, idfMap, vocabulary, vocabIndex, dim };
  } catch {
    return null;
  }
}

/**
 * 将向量数据序列化到磁盘缓存
 * @param {Object} vectors - buildEmbeddingVectors 的返回值
 * @param {number} indexMtime
 */
function saveCacheToDisk(vectors, indexMtime) {
  try {
    if (!fs.existsSync(DEBUG_DIR)) {
      fs.mkdirSync(DEBUG_DIR, { recursive: true });
    }

    // 序列化向量（Float64Array → 普通数组）
    const vectorData = {};
    for (const [name, vec] of vectors.skillVectors.entries()) {
      vectorData[name] = Array.from(vec);
    }

    const cache = {
      indexMtime,
      generatedAt: new Date().toISOString(),
      vocabulary: vectors.vocabulary,
      idfData: Array.from(vectors.idfMap.entries()),
      vectorData,
    };

    fs.writeFileSync(CACHE_FILE, JSON.stringify(cache));
  } catch {
    // 缓存写失败不影响主流程
  }
}

/**
 * 获取（或重建）向量空间，优先使用内存缓存
 * @returns {Object|null} 向量数据，失败返回 null
 */
function getVectors() {
  try {
    const mtime = getIndexMtime();

    // 1. 内存缓存命中
    if (_vectorCache && _vectorCache._indexMtime === mtime) {
      return _vectorCache;
    }

    // 2. 磁盘缓存命中
    const diskCache = loadCacheFromDisk(mtime);
    if (diskCache) {
      diskCache._indexMtime = mtime;
      _vectorCache = diskCache;
      return _vectorCache;
    }

    // 3. 重建向量空间
    if (!fs.existsSync(INDEX_FILE)) return null;
    const index = JSON.parse(fs.readFileSync(INDEX_FILE, 'utf8'));
    const vectors = buildEmbeddingVectors(index);
    vectors._indexMtime = mtime;

    // 异步写缓存（不阻塞返回）
    setImmediate(() => saveCacheToDisk(vectors, mtime));

    _vectorCache = vectors;
    return _vectorCache;
  } catch {
    return null;
  }
}

// =====================================================
// 公共 API
// =====================================================

/**
 * 判断是否应该激活 embedding 辅助路由
 * 触发条件: BM25 top-2 分数差距 < 15%
 *
 * @param {number[]} top2Scores - top-2 候选的分数数组 [score1, score2]
 * @returns {boolean}
 */
function shouldActivate(top2Scores) {
  if (!Array.isArray(top2Scores) || top2Scores.length < 2) return false;
  const [score1, score2] = top2Scores;
  if (score1 <= 0) return false;
  const gap = (score1 - score2) / score1;
  return gap < 0.15;
}

/**
 * 基于 TF-IDF 余弦相似度计算技能相关性
 * （当前实现，不依赖外部 LLM API）
 *
 * @param {string} query - 用户查询文本
 * @param {string[]} [skillNames] - 限定的技能名列表；为空时对所有技能评分
 * @returns {{ skill: string, similarity: number }[]} 按相似度降序排列
 */
function computeSimilarity(query, skillNames) {
  try {
    const vectors = getVectors();
    if (!vectors) return [];

    const qVec = buildQueryVector(query, vectors.idfMap, vectors.vocabIndex, vectors.dim);

    const results = [];
    const targetNames = (skillNames && skillNames.length > 0)
      ? new Set(skillNames)
      : null;

    for (const [name, sVec] of vectors.skillVectors.entries()) {
      if (targetNames && !targetNames.has(name)) continue;
      const similarity = cosineSimilarity(qVec, sVec);
      if (similarity > 0.005) {
        results.push({ skill: name, similarity: Math.round(similarity * 1000) / 1000 });
      }
    }

    return results.sort((a, b) => b.similarity - a.similarity);
  } catch {
    return []; // fail-open
  }
}

/**
 * 预留接口: 基于 LLM 真实 embedding 的相似度计算
 * 当 llmGateway 可用时使用真实 embedding，否则回退到 TF-IDF
 *
 * @param {string} query - 用户查询文本
 * @param {string[]} skillDescriptions - 技能描述列表（格式: [{skill, description}]）
 * @param {Object|null} llmGateway - LLM Gateway MCP 实例（可选）
 * @returns {Promise<{ skill: string, similarity: number }[]>}
 */
async function computeEmbeddingSimilarity(query, skillDescriptions, llmGateway) {
  // 当 LLM Gateway 可用时，使用真实 embedding（未来实现）
  if (llmGateway && typeof llmGateway.embed === 'function') {
    try {
      // 预留: 调用 LLM Gateway 的 embedding 接口
      // const queryEmb = await llmGateway.embed(query);
      // const results = [];
      // for (const { skill, description } of skillDescriptions) {
      //   const skillEmb = await llmGateway.embed(description);
      //   const sim = cosineSimilarity(queryEmb, skillEmb);
      //   results.push({ skill, similarity: sim });
      // }
      // return results.sort((a, b) => b.similarity - a.similarity);
      throw new Error('LLM Gateway embedding 接口尚未实现，回退到 TF-IDF');
    } catch {
      // 回退到 TF-IDF
    }
  }

  // 回退: 使用 TF-IDF 余弦相似度
  const skillNames = (skillDescriptions || []).map(s =>
    typeof s === 'string' ? s : (s.skill || s.name)
  ).filter(Boolean);

  return computeSimilarity(query, skillNames.length > 0 ? skillNames : undefined);
}

/**
 * 清除内存缓存（供测试使用）
 */
function clearCache() {
  _vectorCache = null;
}

/**
 * 获取向量空间元信息（供调试使用）
 * @returns {{ vocabSize: number, skillCount: number, fromCache: boolean } | null}
 */
function getVectorStats() {
  try {
    const vectors = getVectors();
    if (!vectors) return null;
    return {
      vocabSize: vectors.vocabulary.length,
      skillCount: vectors.skillVectors.size,
      dim: vectors.dim,
    };
  } catch {
    return null;
  }
}

// =====================================================
// 模块导出
// =====================================================
if (typeof module !== 'undefined') {
  module.exports = {
    // 核心接口
    shouldActivate,
    computeSimilarity,
    computeEmbeddingSimilarity,
    // 工具函数
    clearCache,
    getVectorStats,
    // 底层函数（供测试）
    tokenizeText,
    cosineSimilarity,
    buildQueryVector,
  };
}

// CLI 入口
if (require.main === module) {
  const query = process.argv.slice(2).join(' ') || '帮我优化首屏加载速度';
  console.log(`=== embedding-router 测试 ===`);
  console.log(`查询: "${query}"`);

  const stats = getVectorStats();
  if (stats) {
    console.log(`向量空间: ${stats.vocabSize} 词, ${stats.skillCount} 技能, ${stats.dim} 维`);
  }

  // 测试 shouldActivate
  console.log(`\nshouldActivate([0.85, 0.82]): ${shouldActivate([0.85, 0.82])}`);
  console.log(`shouldActivate([0.85, 0.60]): ${shouldActivate([0.85, 0.60])}`);

  // 测试 computeSimilarity
  const results = computeSimilarity(query);
  console.log(`\nTop-5 相似度:`);
  results.slice(0, 5).forEach((r, i) => {
    console.log(`  ${i + 1}. ${r.skill.padEnd(30)} ${r.similarity}`);
  });
}
