// BWR Routing Benchmark for BookwormPRO v7.0.0
const path = require('path');

const ROUTING_DIR = __dirname;
console.log('=== BWR Routing Benchmark v7.0.0 ===');
console.log('Engine: ' + ROUTING_DIR);
console.log();

// Phase 1: Load modules
let routeEngine, intentClassifier, bwrBuilder, goldenSet;
console.log('--- Phase 1: Module Loading ---');
const t0 = Date.now();
try {
  routeEngine = require('./route-engine.js');
  console.log('  route-engine: OK');
} catch(e) { console.error('  route-engine FAIL:', e.message); process.exit(1); }
try {
  intentClassifier = require('./intent-classifier.js');
  console.log('  intent-classifier: OK');
} catch(e) { console.error('  intent-classifier FAIL:', e.message); process.exit(1); }
try {
  bwrBuilder = require('./bwr-builder.js');
  console.log('  bwr-builder: OK');
} catch(e) { console.error('  bwr-builder FAIL:', e.message); process.exit(1); }
try {
  goldenSet = require('./golden-set.json');
  console.log('  golden-set: ' + goldenSet.entries.length + ' entries');
} catch(e) { console.error('  golden-set FAIL:', e.message); process.exit(1); }
console.log('  Load time: ' + (Date.now() - t0) + 'ms');

// Check what API surface we have
console.log();
console.log('--- Phase 2: API Discovery ---');
console.log('  intentClassifier keys:', Object.keys(intentClassifier).join(', '));
console.log('  routeEngine keys:', Object.keys(routeEngine).join(', '));
console.log('  bwrBuilder keys:', Object.keys(bwrBuilder).join(', '));

// Intent classification benchmark
console.log();
console.log('--- Phase 3: Intent Classification ---');
const queries = [
  '帮我写一个Python脚本来处理CSV文件',
  '部署到阿里云服务器需要什么配置',
  'hello',
  '分析这个安全漏洞CVE-2024-1234',
  '画一个系统架构图',
  '如何优化数据库查询性能',
  '写一份商业计划书',
  '微信小程序怎么做用户登录',
];

// Find the classify function
const classifyFn = intentClassifier.classify || intentClassifier.classifyIntent || intentClassifier.default;
if (!classifyFn && typeof intentClassifier === 'function') {
  // maybe it exports a function directly
}

const icResults = [];
const t1 = Date.now();
for (const q of queries) {
  try {
    // Try different API patterns
    let result;
    if (typeof intentClassifier === 'function') {
      result = intentClassifier(q);
    } else if (intentClassifier.classify) {
      result = intentClassifier.classify(q);
    } else if (intentClassifier.classifyIntent) {
      result = intentClassifier.classifyIntent(q);
    } else {
      console.log('  Cannot find classify function. Trying direct call...');
      result = intentClassifier(q);
    }
    icResults.push({ query: q.substring(0,40), intents: result.intents || [], complexity: result.complexity || '?' });
  } catch(e) {
    console.log('  WARN: ' + q.substring(0,30) + '... → ' + e.message.substring(0,60));
  }
}
const icTime = Date.now() - t1;
console.log('  Successful: ' + icResults.length + '/' + queries.length);
console.log('  Time: ' + icTime + 'ms (' + (icResults.length > 0 ? (icTime/icResults.length).toFixed(1) : '?') + 'ms avg)');

for (const r of icResults) {
  const intents = Array.isArray(r.intents) ? r.intents.join(',') : String(r.intents);
  console.log('    ' + r.query.substring(0,35).padEnd(37) + ' → [' + intents.substring(0,25) + '] ' + r.complexity);
}

// Full routing pipeline
console.log();
console.log('--- Phase 4: Full Route Pipeline ---');
const routeResults = [];
const t2 = Date.now();
for (const r of icResults.slice(0, 5)) {
  try {
    const routing = routeEngine.runRouteEngine(r.query, { intents: r.intents, complexity: r.complexity });
    const primary = routing.primary || routing.skill || '?';
    const conf = routing.confidence || 0;
    const candidates = (routing.candidates || []).slice(0, 3).map(c => c.name || c).join(', ');
    routeResults.push({ query: r.query.substring(0,35), primary, conf, candidates });
  } catch(e) {
    console.log('  WARN: ' + r.query.substring(0,30) + ' → ' + e.message.substring(0,60));
  }
}
const routeTime = Date.now() - t2;
console.log('  Successful: ' + routeResults.length + '/5');
console.log('  Time: ' + routeTime + 'ms (' + (routeResults.length > 0 ? (routeTime/routeResults.length).toFixed(1) : '?') + 'ms avg)');

if (routeResults.length > 0) {
  console.log();
  for (const r of routeResults) {
    console.log('    ' + r.query.padEnd(37) + ' → ' + r.primary.padEnd(22) + ' conf=' + r.conf.toFixed(2) + '  [' + r.candidates + ']');
  }
}

// Skills index
console.log();
console.log('--- Phase 5: Skills Index ---');
try {
  const idx = routeEngine.loadSkillsIndex ? routeEngine.loadSkillsIndex() : 'N/A';
  console.log('  ' + (Array.isArray(idx) ? idx.length + ' skills loaded' : 'API: loadSkillsIndex=' + typeof routeEngine.loadSkillsIndex));
} catch(e) {
  console.log('  WARN: ' + e.message.substring(0,80));
}

// Summary
console.log();
console.log('=== SUMMARY ===');
console.log('Load:      ' + (Date.now() - t0) + 'ms');
console.log('Intent:    ' + (icResults.length > 0 ? (icTime/icResults.length).toFixed(1) : '?') + 'ms avg');
console.log('Route:     ' + (routeResults.length > 0 ? (routeTime/routeResults.length).toFixed(1) : '?') + 'ms avg');
console.log('GoldenSet: ' + goldenSet.entries.length + ' test cases');
