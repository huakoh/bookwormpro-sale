#!/usr/bin/env node
'use strict';
const fs = require('fs');
const path = require('path');

const ROOT = path.join(process.env.USERPROFILE, '.claude');
const DEBUG = path.join(ROOT, 'debug');
const SCRIPTS = path.join(ROOT, 'scripts');

function time(label, fn) {
  const t0 = performance.now();
  let result;
  try { result = fn(); } catch (e) { result = 'ERROR: ' + e.message; }
  const ms = (performance.now() - t0).toFixed(2);
  process.stdout.write(label.padEnd(50) + ms.padStart(8) + ' ms\n');
  return result;
}

process.stdout.write('\n=== Hook Hotpath Profiling ===\n\n');
process.stdout.write('Operation'.padEnd(50) + 'Time'.padStart(8) + '\n');
process.stdout.write('-'.repeat(60) + '\n');

// 1. Module require times
time('require fs+path+crypto', () => { require('fs'); require('path'); require('crypto'); });
time('require hooks/lib/root.js', () => require(path.join(ROOT, 'hooks/lib/root.js')));
time('require hooks/lib/read-stdin.js', () => require(path.join(ROOT, 'hooks/lib/read-stdin.js')));
time('require hooks/lib/fast-cache.js', () => require(path.join(ROOT, 'hooks/lib/fast-cache.js')));
time('require hooks/lib/safe-append.js', () => require(path.join(ROOT, 'hooks/lib/safe-append.js')));

// 2. Scripts (routing deps)
time('require scripts/route-engine.js', () => require(path.join(SCRIPTS, 'route-engine.js')));
time('require scripts/intent-classifier.js', () => require(path.join(SCRIPTS, 'intent-classifier.js')));
time('require scripts/bwr-builder.js', () => require(path.join(SCRIPTS, 'bwr-builder.js')));
time('require scripts/route-state.js', () => require(path.join(SCRIPTS, 'route-state.js')));
time('require scripts/feature-flags.js', () => require(path.join(SCRIPTS, 'feature-flags.js')));

// 3. Data loading
time('JSON.parse stats-compiled.json', () => {
  return JSON.parse(fs.readFileSync(path.join(ROOT, 'stats-compiled.json'), 'utf8'));
});

time('JSON.parse skills-index-lite.json', () => {
  return JSON.parse(fs.readFileSync(path.join(ROOT, 'skills-index-lite.json'), 'utf8'));
});

time('JSON.parse settings.json', () => {
  return JSON.parse(fs.readFileSync(path.join(ROOT, 'settings.json'), 'utf8'));
});

// 4. Route accuracy 3-day scan (the suspected bottleneck)
time('Route accuracy 3-day JSONL scan', () => {
  const cutoff = Date.now() - 3 * 86400 * 1000;
  const files = fs.readdirSync(DEBUG).filter(f => /^route-\d{4}-\d{2}-\d{2}\.jsonl$/.test(f));
  let total = 0, hit = 0, lineCount = 0;
  for (const f of files) {
    const lines = fs.readFileSync(path.join(DEBUG, f), 'utf8').split('\n');
    for (const L of lines) {
      if (!L) continue;
      lineCount++;
      try {
        const j = JSON.parse(L);
        const ts = new Date(j.ts).getTime();
        if (!Number.isFinite(ts) || ts < cutoff) continue;
        const q = (j.query || '').trim();
        if (q.length <= 3 || q.startsWith('[Image') || !q) continue;
        if (j.topResult === 'none' && (!j.candidates || j.candidates.length === 0)) continue;
        total++;
        if (j.topConfidence && j.topConfidence > 0) hit++;
      } catch {}
    }
  }
  return { total, hit, lineCount, accuracy: total > 0 ? (hit / total * 100).toFixed(1) + '%' : 'N/A' };
});

// 5. File system overhead
time('fs.readdirSync(hooks/) + filter .js', () => {
  return fs.readdirSync(path.join(ROOT, 'hooks')).filter(f => f.endsWith('.js')).length;
});

time('fs.readdirSync(debug/)', () => {
  return fs.readdirSync(DEBUG).length;
});

time('fs.existsSync x10 (session-state files)', () => {
  const dir = path.join(ROOT, 'session-state');
  for (let i = 0; i < 10; i++) fs.existsSync(path.join(dir, 'test-' + i + '.json'));
});

process.stdout.write('-'.repeat(60) + '\n');
