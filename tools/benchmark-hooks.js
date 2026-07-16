#!/usr/bin/env node
'use strict';
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const ROOT = path.join(process.env.USERPROFILE || process.env.HOME, '.claude');
const CACHE_DIR = path.join(ROOT, 'hooks', '.v8-cache');
if (!fs.existsSync(CACHE_DIR)) fs.mkdirSync(CACHE_DIR, { recursive: true });

const settings = JSON.parse(fs.readFileSync(path.join(ROOT, 'settings.json'), 'utf8'));
const hookFiles = new Set();
const hookRe = /hooks[\\/]([^"' ]+\.js)/;
for (const entries of Object.values(settings.hooks || {})) {
  for (const entry of entries) {
    for (const h of (entry.hooks || [])) {
      const m = hookRe.exec(h.command || '');
      if (m) hookFiles.add(m[1]);
    }
  }
}

// 清空缓存做冷启动基准
try { fs.rmSync(CACHE_DIR, { recursive: true, force: true }); } catch {}
fs.mkdirSync(CACHE_DIR, { recursive: true });

const results = [];
let totalCold = 0, totalWarm = 0;

for (const file of [...hookFiles].sort()) {
  const full = path.join(ROOT, 'hooks', file).replace(/\\/g, '/');
  if (!fs.existsSync(full)) continue;

  // 冷启动 (无 compile cache)
  const coldEnv = Object.assign({}, process.env);
  delete coldEnv.NODE_COMPILE_CACHE;
  const t0 = Date.now();
  try { execSync('node -e "require(\'' + full + '\')"', { env: coldEnv, timeout: 3000, stdio: 'ignore' }); } catch {}
  const cold = Date.now() - t0;

  // 预热: 带缓存跑一次
  const warmEnv = Object.assign({}, process.env, { NODE_COMPILE_CACHE: CACHE_DIR });
  try { execSync('node -e "require(\'' + full + '\')"', { env: warmEnv, timeout: 3000, stdio: 'ignore' }); } catch {}

  // 热启动: 带缓存再跑一次
  const t1 = Date.now();
  try { execSync('node -e "require(\'' + full + '\')"', { env: warmEnv, timeout: 3000, stdio: 'ignore' }); } catch {}
  const warm = Date.now() - t1;

  results.push({ file, cold, warm, saved: cold - warm });
  totalCold += cold;
  totalWarm += warm;
}

console.log('\n=== Hook Compile Cache Benchmark (Node ' + process.version + ') ===\n');
console.log('File'.padEnd(42) + 'Cold   Warm   Saved');
console.log('-'.repeat(68));
for (const r of results.sort((a, b) => b.saved - a.saved)) {
  console.log(r.file.padEnd(42) + String(r.cold).padStart(4) + 'ms' + String(r.warm).padStart(5) + 'ms' + String(r.saved).padStart(5) + 'ms');
}
console.log('-'.repeat(68));
console.log('TOTAL'.padEnd(42) + String(totalCold).padStart(4) + 'ms' + String(totalWarm).padStart(5) + 'ms' + String(totalCold - totalWarm).padStart(5) + 'ms');
console.log('Speedup: ' + ((1 - totalWarm / totalCold) * 100).toFixed(1) + '%');

// 缓存大小
let sz = 0;
const walk = (d) => {
  for (const f of fs.readdirSync(d, { withFileTypes: true })) {
    if (f.isDirectory()) walk(path.join(d, f.name));
    else sz += fs.statSync(path.join(d, f.name)).size;
  }
};
try { walk(CACHE_DIR); } catch {}
console.log('Cache size: ' + (sz / 1024).toFixed(1) + ' KB\n');
