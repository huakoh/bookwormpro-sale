#!/usr/bin/env node
// Skill 别名解析模块 (v6.6 Phase 2 合并兼容层)
// fail-open: 任何异常都返回原名，绝不阻断路由

const fs = require('fs');
const path = require('path');
const os = require('os');

const ROOT = path.join(os.homedir(), '.claude');
const ALIAS_FILE = path.join(ROOT, 'skill-alias.json');
const LOG_FILE = path.join(ROOT, 'debug', 'skill-alias-resolutions.jsonl');

let _cache = null;
let _mtime = 0;

function loadAliases() {
  try {
    const stat = fs.statSync(ALIAS_FILE);
    if (_cache && stat.mtimeMs === _mtime) return _cache;
    const data = JSON.parse(fs.readFileSync(ALIAS_FILE, 'utf8'));
    _cache = {
      aliases: data.aliases || {},
      policy: data.policy || { log_when_resolved: false, fail_open: true },
      deprecatedUntil: data.deprecated_until || {},
    };
    _mtime = stat.mtimeMs;
    return _cache;
  } catch {
    return { aliases: {}, policy: { fail_open: true }, deprecatedUntil: {} };
  }
}

function resolve(name) {
  if (!name || typeof name !== 'string') return { resolved: name, wasAlias: false };
  const conf = loadAliases();
  const target = conf.aliases[name];
  if (!target || target === name) return { resolved: name, wasAlias: false };
  const out = { resolved: target, wasAlias: true, original: name };
  if (conf.deprecatedUntil[name]) out.expiresOn = conf.deprecatedUntil[name];
  if (conf.policy.log_when_resolved) safeLog(out);
  return out;
}

function resolveCandidates(candidates) {
  if (!Array.isArray(candidates)) return candidates;
  const seen = new Map();
  for (const c of candidates) {
    const r = resolve(c.name || c.skill || c);
    const key = r.resolved;
    if (!seen.has(key)) {
      seen.set(key, { ...c, name: key, score: c.score, _aliasOrigin: r.wasAlias ? r.original : undefined });
    } else if (c.score > seen.get(key).score) {
      seen.get(key).score = c.score;
    }
  }
  return Array.from(seen.values());
}

function safeLog(entry) {
  try {
    const line = JSON.stringify({ ts: new Date().toISOString(), ...entry }) + '\n';
    fs.appendFileSync(LOG_FILE, line);
  } catch {}
}

function listAliases() {
  return Object.entries(loadAliases().aliases).map(([from, to]) => ({ from, to }));
}

module.exports = { resolve, resolveCandidates, listAliases, loadAliases };

if (require.main === module) {
  const args = process.argv.slice(2);
  if (args[0]) {
    process.stdout.write(JSON.stringify(resolve(args[0]), null, 2) + '\n');
  } else {
    const all = listAliases();
    process.stdout.write('Loaded ' + all.length + ' alias mappings:\n');
    all.forEach(a => process.stdout.write('  ' + a.from + ' -> ' + a.to + '\n'));
    process.stdout.write('\nUsage: node skill-alias-resolver.js <skill-name>\n');
  }
}
