// BWR Accuracy Test — Golden Set Benchmark
const routeEngine = require('./route-engine.js');
const intentClassifier = require('./intent-classifier.js');
const goldenSet = require('./golden-set.json');

console.log('=== Golden Set Accuracy Benchmark ===');
console.log('Entries:', goldenSet.entries.length);

const t0 = Date.now();
let correct = 0, total = 0, intentsOk = 0;
const errors = [];

for (const entry of goldenSet.entries) {
  if (!entry.expectedSkill || entry.expectedSkill === 'unknown') continue;
  total++;
  
  try {
    const intent = intentClassifier.classifyIntent(entry.query);
    const routing = routeEngine.runRouteEngine(entry.query, intent);
    const predicted = routing.primary || '?';
    
    // Exact match or in candidates
    const candidates = (routing.candidates || []).map(c => c.name || c);
    const isCorrect = predicted === entry.expectedSkill || candidates.includes(entry.expectedSkill);
    
    if (isCorrect) correct++;
    else {
      errors.push({
        query: entry.query.substring(0, 60),
        expected: entry.expectedSkill,
        predicted,
        candidates: candidates.slice(0, 3).join(', '),
        confidence: routing.confidence,
      });
    }
  } catch(e) {
    errors.push({ query: entry.query.substring(0, 60), expected: entry.expectedSkill, predicted: 'ERROR: ' + e.message.substring(0, 40) });
  }
}

const elapsed = Date.now() - t0;

console.log();
console.log('  Total tested:  ' + total);
console.log('  Correct:       ' + correct + ' (' + (correct/total*100).toFixed(1) + '%)');
console.log('  Errors:        ' + errors.length);
console.log('  Total time:    ' + elapsed + 'ms');
console.log('  Avg per query: ' + (elapsed/total).toFixed(1) + 'ms');
console.log();

if (errors.length > 0) {
  console.log('=== Top Errors ===');
  for (const e of errors.slice(0, 15)) {
    console.log('  Expected: ' + e.expected.padEnd(25) + ' → Got: ' + (e.predicted || '?').padEnd(25) + ' | ' + e.query.substring(0, 55));
  }
  if (errors.length > 15) console.log('  ... and ' + (errors.length - 15) + ' more');
}

// Quick compare: route on a second run (cached)
console.log();
console.log('=== Cached Run (2nd pass) ===');
const t1 = Date.now();
let c2 = 0;
for (const entry of goldenSet.entries.slice(0, 10)) {
  if (!entry.expectedSkill) continue;
  const intent = intentClassifier.classifyIntent(entry.query);
  routeEngine.runRouteEngine(entry.query, intent);
  c2++;
}
console.log('  10 queries: ' + (Date.now() - t1) + 'ms (' + ((Date.now()-t1)/c2).toFixed(1) + 'ms avg)');

// CI threshold check
const MIN_ACCURACY = parseFloat(process.env.BWR_MIN_ACCURACY || '85.0');
const accuracy = correct / total * 100;
console.log('Threshold: ' + MIN_ACCURACY.toFixed(1) + '%');
console.log('Status: ' + (accuracy >= MIN_ACCURACY ? 'PASS' : 'FAIL'));

if (accuracy < MIN_ACCURACY) {
  console.error('ERROR: Accuracy ' + accuracy.toFixed(1) + '% below threshold ' + MIN_ACCURACY.toFixed(1) + '%');
  process.exit(1);
}
process.exit(0);
