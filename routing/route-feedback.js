// Route Feedback Collector — learn from routing outcomes
// Watches route logs, compares predicted vs actual skill usage,
// and generates disambiguation rule suggestions.
const fs = require('fs');
const path = require('path');

const ROOT = require('./lib/root.js');
const DEBUG_DIR = path.join(ROOT, 'debug');

// Load disambiguation rules
let rules;
try {
  rules = require('./disambiguation-rules.json');
} catch { rules = { _meta: { version: 'v1.0', ruleCount: 0 } }; }

function collectFeedback(traceId, query, predictedSkill, actualSkill, confidence) {
  if (!predictedSkill || !actualSkill) return;
  if (predictedSkill === actualSkill) return; // correct — skip
  
  const entry = {
    ts: new Date().toISOString(),
    traceId,
    query: (query || '').substring(0, 200),
    predicted: predictedSkill,
    actual: actualSkill,
    confidence,
    mismatch: true,
  };
  
  // Append to daily feedback log
  const dateStr = new Date().toISOString().slice(0, 10);
  const feedbackFile = path.join(DEBUG_DIR, 'route-feedback-' + dateStr + '.jsonl');
  
  try {
    if (!fs.existsSync(DEBUG_DIR)) fs.mkdirSync(DEBUG_DIR, { recursive: true });
    fs.appendFileSync(feedbackFile, JSON.stringify(entry) + '\n');
  } catch {}
  
  // Suggest disambiguation rule
  suggestRule(predictedSkill, actualSkill, query);
}

function suggestRule(predicted, actual, query) {
  const key = `${predicted}→${actual}`;
  
  // Don't spam — track suggestions
  const suggestFile = path.join(DEBUG_DIR, 'route-suggestions.json');
  let suggestions = {};
  try { suggestions = JSON.parse(fs.readFileSync(suggestFile, 'utf8')); } catch {}
  
  if (!suggestions[key]) suggestions[key] = { count: 0, queries: [] };
  suggestions[key].count++;
  if (suggestions[key].queries.length < 5) {
    suggestions[key].queries.push(query.substring(0, 80));
  }
  
  try { fs.writeFileSync(suggestFile, JSON.stringify(suggestions, null, 2)); } catch {}
}

// Analyze feedback and generate rules
function analyzeAndGenerate(threshold = 3) {
  const suggestFile = path.join(DEBUG_DIR, 'route-suggestions.json');
  let suggestions = {};
  try { suggestions = JSON.parse(fs.readFileSync(suggestFile, 'utf8')); } catch { return []; }
  
  const newRules = [];
  for (const [key, data] of Object.entries(suggestions)) {
    if (data.count >= threshold) {
      const [predicted, actual] = key.split('→');
      newRules.push({
        pattern: `redirect ${predicted} → ${actual}`,
        predicted,
        actual,
        confidence: Math.min(data.count / 10, 0.9),
        sampleQueries: data.queries.slice(0, 3),
        suggestedAt: new Date().toISOString(),
      });
    }
  }
  return newRules;
}

module.exports = { collectFeedback, analyzeAndGenerate };
