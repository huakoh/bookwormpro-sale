// BWR Bridge — stdin JSON → route → stdout JSON
// Called by bwr_bridge.py via subprocess

const routeEngine = require('./route-engine.js');
const intentClassifier = require('./intent-classifier.js');
const bwrBuilder = require('./bwr-builder.js');
const feedback = require('./route-feedback.js');

let rawInput = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => { rawInput += chunk; });
process.stdin.on('end', () => {
  const t0 = Date.now();
  let input;
  try {
    input = JSON.parse(rawInput);
  } catch(e) {
    // Collect feedback for learning
    try {
      const primary = routing.primary || '?';
      feedback.collectFeedback(traceId, query, primary, null, routing.confidence || 0);
    } catch {}

    output({ error: 'Invalid JSON input: ' + e.message });
    return;
  }

  const { query, cwd } = input;
  if (!query) {
    // Collect feedback for learning
    try {
      const primary = routing.primary || '?';
      feedback.collectFeedback(traceId, query, primary, null, routing.confidence || 0);
    } catch {}

    output({ error: 'Missing "query" field' });
    return;
  }

  try {
    // Step 1: Intent classification
    const intent = intentClassifier.classifyIntent(query);

    // Step 2: Route engine
    const routing = routeEngine.runRouteEngine(query, intent, cwd || process.cwd());

    // Step 3: Build BWR directive
    const traceId = Math.random().toString(36).slice(2, 10);
    const directive = bwrBuilder.buildBWRDirective(traceId, intent, routing, false);

    // Step 4: Recommendation
    let recommendation = 'fallback';
    if (routing.confidence >= 0.8) recommendation = 'route';
    else if (routing.confidence >= 0.5) recommendation = 'recommend';

    // Collect feedback for learning
    try {
      const primary = routing.primary || '?';
      feedback.collectFeedback(traceId, query, primary, null, routing.confidence || 0);
    } catch {}

    output({
      intent: {
        intents: intent.intents || [],
        complexity: intent.complexity || 'medium',
      },
      routing: {
        primary: routing.primary || 'developer-expert',
        confidence: routing.confidence || 0,
        candidates: (routing.candidates || []).slice(0, 5).map(c => ({
          name: c.name || c,
          confidence: c.confidence || 0,
        })),
        chain: routing.chain || [],
      },
      directive,
      recommendation,
      elapsed_ms: Date.now() - t0,
    });
  } catch(e) {
    // Collect feedback for learning
    try {
      const primary = routing.primary || '?';
      feedback.collectFeedback(traceId, query, primary, null, routing.confidence || 0);
    } catch {}

    output({ error: e.message });
  }
});

function output(data) {
  process.stdout.write(JSON.stringify(data) + '\n');
  process.exit(data.error ? 1 : 0);
}
