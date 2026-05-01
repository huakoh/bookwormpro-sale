'use strict';



/**

 * 路由引擎 — BM25 + 多信号融合 + 消歧 + 冷启动 + 精排

 * @module scripts/route-engine

 *

 * 从 route-interceptor-bundle.js 提取 (Phase 0 宪法合规拆分)

 * 原始位置: bundle L176-434

 */



const fs = require('fs');

const path = require('path');



const CLAUDE_ROOT = require('./lib/root.js');
const DEBUG_DIR = path.join(CLAUDE_ROOT, 'debug');
const SCRIPTS_DIR = __dirname;  // modules co-located in routing/


// ─── 模块加载 (复用 bundle 的 safeRequire 模式) ───



const _cache = {};

function safeRequire(modulePath) {

  const basename = path.basename(modulePath);

  if (_cache[basename] !== undefined) return _cache[basename] || null;

  try { _cache[basename] = require(modulePath); return _cache[basename]; }

  catch { _cache[basename] = null; return null; }

}



// ─── skills-index 缓存 ───



let _skillsIndexCache = null;

let _skillsIndexMtime = 0;



function loadSkillsIndex(indexPath) {

  try {

    const stat = fs.statSync(indexPath);

    if (_skillsIndexCache && stat.mtimeMs === _skillsIndexMtime) {

      return _skillsIndexCache;

    }

    _skillsIndexCache = JSON.parse(fs.readFileSync(indexPath, 'utf8'));

    _skillsIndexMtime = stat.mtimeMs;

    return _skillsIndexCache;

  } catch { return null; }

}



// ─── 路由引擎主函数 ───



/**

 * 运行完整路由引擎

 * @param {string} prompt - 用户输入

 * @param {string} cwd - 当前工作目录

 * @param {object} [precomputedIntent] - 预计算的意图分类结果

 * @returns {{ primary, candidates, confidence, chain, composable, domain }}

 */

function runRouteEngine(prompt, cwd, precomputedIntent) {

  const routeAnalyzer = safeRequire(path.join(SCRIPTS_DIR, 'route-analyzer.js'));

  if (!routeAnalyzer) {

    return { primary: 'developer-expert', candidates: [], confidence: 0, chain: [] };

  }



  const indexFile = path.join(CLAUDE_ROOT, 'skills-index.json');

  const index = loadSkillsIndex(indexFile);

  if (!index) {

    return { primary: 'developer-expert', candidates: [], confidence: 0, chain: [] };

  }



  // BM25 评分

  const queryTokens = routeAnalyzer.tokenize(prompt);

  const bm25Params = routeAnalyzer.buildBM25Params(index);



  // 上下文信号

  let contextScores = {}, projectBoosts = {}, workflowPrediction = null;

  const contextTracker = safeRequire(path.join(SCRIPTS_DIR, 'context-tracker.js'));

  if (contextTracker) {

    try {

      const composableIdx = contextTracker.buildComposableIndex(index);

      const ctxState = contextTracker.loadState ? contextTracker.loadState(cwd) : undefined;

      for (const skill of index.skills) {

        contextScores[skill.name] = contextTracker.computeContextScore(skill.name, composableIdx, ctxState);

      }

    } catch {}

  }



  const projectDetector = safeRequire(path.join(SCRIPTS_DIR, 'project-detector.js'));

  if (projectDetector) {

    try { projectBoosts = projectDetector.getProjectBoost(cwd || process.cwd()); } catch {}

  }



  // workflow-patterns: 磁盘缓存替代实时读 30 天日志

  try {

    const wfCacheFile = path.join(DEBUG_DIR, '.workflow-patterns-cache.json');

    if (fs.existsSync(wfCacheFile)) {

      const cacheAge = Date.now() - fs.statSync(wfCacheFile).mtimeMs;

      if (cacheAge < 30 * 60 * 1000) {

        const cached = JSON.parse(fs.readFileSync(wfCacheFile, 'utf8'));

        if (cached.data && cached.data.length > 0) {

          const wfMod = safeRequire(path.join(SCRIPTS_DIR, 'workflow-patterns.js'));

          if (wfMod) {

            const sessions = wfMod.extractSkillSequences(cached.data, 30);

            workflowPrediction = wfMod.minePatterns(sessions, 2);

          }

        }

      }

    }

  } catch {}



  // L1 域分类 — 缩小候选集

  let domainInfo = null;

  let candidateSkillSet = null;

  const domainClassifier = safeRequire(path.join(SCRIPTS_DIR, 'domain-classifier.js'));

  if (domainClassifier) {

    try {

      const intentResult = precomputedIntent || { intents: [], entities: [] };

      domainInfo = domainClassifier.classifyDomain(prompt, intentResult.intents, intentResult.entities);

      if (domainInfo.confidence >= 0.3) {

        candidateSkillSet = new Set(domainInfo.candidates);

      }

    } catch {}

  }



  // 语义评分 (TF-IDF 向量余弦相似度)

  let semanticScores = {};

  const semanticScorer = safeRequire(path.join(SCRIPTS_DIR, 'semantic-scorer.js'));

  if (semanticScorer) {

    try {

      const semResults = semanticScorer.semanticScore(prompt, index);

      for (const r of semResults) {

        semanticScores[r.name] = r.score;

      }

    } catch {}

  }



  // 自适应融合权重

  let fw = { bm25: 0.40, semantic: 0.30, context: 0.15, project: 0.10, workflow: 0.05 };

  const fusionLearner = safeRequire(path.join(SCRIPTS_DIR, 'fusion-weight-learner.js'));

  if (fusionLearner) {

    try { fw = fusionLearner.loadWeights(cwd); } catch {}

  }



  // 构建倒排索引加速精确匹配

  const invertedIndex = routeAnalyzer.buildInvertedIndex ? routeAnalyzer.buildInvertedIndex(index) : null;



  // 评分: BM25 + Semantic + Context + Project + Workflow

  const results = index.skills.map(skill => {

    const { totalScore, matchedKeywords } = routeAnalyzer.scoreSkill(skill, queryTokens, bm25Params, invertedIndex);

    const ctxScore = contextScores[skill.name] || 0;

    const projBoost = projectBoosts[skill.name] || 0;

    const semScore = semanticScores[skill.name] || 0;

    let wfScore = 0;

    if (workflowPrediction) {

      for (const [key, count] of Object.entries(workflowPrediction.bigrams || {})) {

        const [, to] = key.split('→');

        if (to === skill.name) { wfScore = Math.min(1, count * 0.1); break; }

      }

    }



    // 自适应多信号融合 (semScore=0 时渐变降级)

    let finalScore;

    if (totalScore > 0) {

      if (semScore > 0) {

        finalScore = totalScore * fw.bm25 + semScore * fw.semantic + ctxScore * fw.context + projBoost * fw.project + wfScore * fw.workflow;

      } else {

        const noSem = fw.bm25 + fw.context + fw.project + fw.workflow;

        if (noSem <= 0) {

          finalScore = totalScore;

        } else {

          finalScore = totalScore * (fw.bm25 / noSem) + ctxScore * (fw.context / noSem) + projBoost * (fw.project / noSem) + wfScore * (fw.workflow / noSem);

        }

      }

    } else if (semScore > 0.1) {

      finalScore = semScore * 0.6;

    } else {

      finalScore = 0;

    }



    // L2 域内精排 — 高置信度时隔离域外技能

    if (candidateSkillSet && finalScore > 0 && !candidateSkillSet.has(skill.name)) {

      if (domainInfo && domainInfo.confidence > 0.6) {

        finalScore *= 0.2;

      } else {

        finalScore *= 0.5;

      }

    }



    return { name: skill.name, score: Math.round(finalScore * 100) / 100 };

  }).sort((a, b) => b.score - a.score);



  // embedding-router: top-2 分差 < 10% 时 tie-breaker

  if (results.length >= 2 && results[0].score > 0 && results[1].score > 0) {

    const gap = (results[0].score - results[1].score) / results[0].score;

    if (gap < 0.10) {

      const embeddingRouter = safeRequire(path.join(SCRIPTS_DIR, 'embedding-router.js'));

      if (embeddingRouter) {

        try {

          const top2Scores = [results[0].score, results[1].score];

          if (embeddingRouter.shouldActivate(top2Scores)) {

            const top10Names = results.slice(0, 10).map(r => r.name);

            const embeddingScores = embeddingRouter.computeSimilarity(prompt, top10Names);

            const embMap = new Map(embeddingScores.map(es => [es.skill, es.similarity]));

            for (const r of results) {

              const embSim = embMap.get(r.name) || 0;

              if (embSim > 0) {

                r.score = Math.round((r.score + embSim * r.score * 0.10) * 100) / 100;

              }

            }

            results.sort((a, b) => b.score - a.score);

          }

        } catch {}

      }

    }

  }



  // 冲突消歧

  let disambiguated = results;

  let firedRules = [];

  if (routeAnalyzer.applyDisambiguation) {

    try {

      const disambResult = routeAnalyzer.applyDisambiguation(results, prompt, index);

      disambiguated = disambResult.results || results;

      firedRules = disambResult.firedRules || [];

    } catch {}

  }



  // adaptive-disambiguator: Bayesian 后验融合

  const adaptiveDisamb = safeRequire(path.join(SCRIPTS_DIR, 'adaptive-disambiguator.js'));

  if (adaptiveDisamb && disambiguated.length > 0) {

    try {

      const hardRuleResults = {

        boosted: firedRules.filter(r => r.action === 'boost' || r.winner).map(r => r.winner || r.skill).filter(Boolean),

        penalized: firedRules.filter(r => r.action === 'penalize').map(r => r.skill).filter(Boolean),

        firedRules: firedRules.map(r => r.id || r.rule || '').filter(Boolean),

      };

      const intentResult = precomputedIntent || { intents: [], entities: [] };

      const bayesianResult = adaptiveDisamb.adaptiveDisambiguate(

        disambiguated.slice(0, 5),

        { prompt, domain: domainInfo, intent: intentResult },

        hardRuleResults

      );

      if (bayesianResult && bayesianResult.length > 0) {

        const tail = disambiguated.slice(5);

        disambiguated = [...bayesianResult, ...tail];

      }

    } catch {}

  }



  // 冷启动防护

  let coldStartApplied = false;

  let coldStartSkills = [];

  const routeTelemetry = safeRequire(path.join(SCRIPTS_DIR, 'route-telemetry.js'));

  if (routeAnalyzer.applyColdStartBoost && routeTelemetry) {

    try {

      const routeStats = routeTelemetry.getSkillRouteStats(30);

      const { boostedSkills } = routeAnalyzer.applyColdStartBoost(disambiguated, routeStats);

      if (boostedSkills && boostedSkills.length > 0) {

        coldStartApplied = true;

        coldStartSkills = boostedSkills;

        disambiguated.sort((a, b) => b.score - a.score);

      }

    } catch {}

  }



  // top-k reranking 精排

  let reranked = disambiguated;

  if (routeAnalyzer.rerankTopK) {

    try {

      reranked = routeAnalyzer.rerankTopK(disambiguated, queryTokens, index, 10);

    } catch {}

  }



  // 归一化

  const normalized = routeAnalyzer.normalizeScores(reranked).slice(0, 5);

  const recommendation = routeAnalyzer.getRecommendation(normalized);

  const chain = [];

  const composable = routeAnalyzer.buildComposableHints(index, normalized);



  const primary = recommendation.skill || recommendation.primary || 'developer-expert';

  const candidates = normalized.filter(r => r.confidence >= 0.3);

  const confidence = normalized[0]?.confidence || 0;



  // CONFIDENCE_CAP_SHORT_QUERY_PATCH_2026_04_20

  // 短查询置信度上限: token 数 ≤3 时 confidence 不超过 0.8，防 BM25 过拟合

  let _finalConfidence = confidence;

  if (queryTokens.size <= 3 && _finalConfidence > 0.8) {

    _finalConfidence = 0.8;

    try {

      const logLine = JSON.stringify({

        t: Date.now(), event: 'confidence_cap',

        tokens: queryTokens.size, original: confidence, capped: 0.8,

        primary: normalized[0] && normalized[0].name,

      }) + '\n';

      fs.appendFileSync(path.join(DEBUG_DIR, 'confidence-cap.log'), logLine);

    } catch {}

  }







  // COLD_START_CONFIDENCE_CAP_v1_APPLIED

  // 冷启动置信度上限: coldStartApplied=true 且 rank1/rank2 分差 < 0.15 → cap 0.65

  // 防止冷启动 boost 后 gap 较小时系统过度自信

  if (coldStartApplied && normalized.length >= 2) {

    const _n0 = normalized[0] ? (normalized[0].confidence || 0) : 0;

    const _n1 = normalized[1] ? (normalized[1].confidence || 0) : 0;

    const gap_1_2 = _n0 - _n1;

    if (gap_1_2 < 0.15 && _finalConfidence > 0.65) {

      _finalConfidence = 0.65;

      try {

        const _capLog = JSON.stringify({

          t: Date.now(), event: 'cold_start_confidence_cap',

          gap: Math.round(gap_1_2 * 1000) / 1000,

          original: confidence, capped: 0.65,

          primary: normalized[0] && normalized[0].name,

        }) + '\n';

        fs.appendFileSync(path.join(DEBUG_DIR, 'confidence-cap.log'), _capLog);

      } catch {}

    }

  }



  // === ALIAS_RESOLVER_INJECTED_PHASE2_2026_04_25 ===

  let _aliasedPrimary = primary, _aliasedCandidates = candidates;

  try {

    const _resolver = safeRequire(path.join(SCRIPTS_DIR, 'skill-alias-resolver.js'));

    if (_resolver) {

      const _r = _resolver.resolve(primary);

      if (_r.wasAlias) _aliasedPrimary = _r.resolved;

      _aliasedCandidates = _resolver.resolveCandidates(candidates);

    }

  } catch {}

  return {

    primary: _aliasedPrimary, candidates: _aliasedCandidates, confidence: _finalConfidence, chain, composable,

    domain: domainInfo ? domainInfo.domain : null,

    _firedRules: firedRules || [],

    _coldStartApplied: coldStartApplied || false,

    _coldStartSkills: coldStartSkills || [],

    _startTs: Date.now(),

  };

}



module.exports = { runRouteEngine, loadSkillsIndex, safeRequire };

