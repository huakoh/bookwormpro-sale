// probe-one.js — 单 MCP 服务器探针（30s 超时）
// 用法: node probe-one.js <server-name>
// 读取 ~/.claude.json → 找到指定服务器 → 30s 超时 probe

const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');

const CONFIG = JSON.parse(fs.readFileSync(os.homedir() + '/.claude.json', 'utf8'));
const servers = CONFIG.mcpServers || {};

const targetName = process.argv[2];
if (!targetName) {
  console.error('Usage: node probe-one.js <server-name>');
  process.exit(1);
}

const cfg = servers[targetName];
if (!cfg) {
  console.log(JSON.stringify({ name: targetName, status: 'NOT_FOUND', detail: 'not in .claude.json' }));
  process.exit(1);
}

const TIMEOUT_MS = 30000;
const start = Date.now();
let stdout = '', stderr = '', settled = false, child;

function done(status, detail) {
  if (settled) return;
  settled = true;
  try { child && child.kill('SIGKILL'); } catch (_) {}
  const result = {
    name: targetName, kind: 'stdio', status, detail,
    ms: Date.now() - start,
    stderrTail: stderr.split('\n').filter(Boolean).slice(-3).join(' | ').substring(0, 200)
  };
  console.log(JSON.stringify(result));
}

try {
  const env = Object.assign({}, process.env, cfg.env || {});
  child = spawn(cfg.command, cfg.args || [], {
    env, stdio: ['pipe', 'pipe', 'pipe'],
    shell: false, windowsHide: true
  });
} catch (e) {
  done('SPAWN_ERROR', e.message);
}

if (child) {
  child.on('error', (e) => done('SPAWN_ERROR', e.message));
  child.on('exit', (code, sig) => {
    if (settled) return;
    done(code === 0 ? 'EXITED_OK' : 'CRASHED', `exit=${code} sig=${sig}`);
  });
  child.stdout.on('data', (d) => {
    stdout += d.toString();
    for (const line of stdout.split('\n')) {
      if (line.includes('"jsonrpc"') && line.includes('"result"')) {
        try {
          const msg = JSON.parse(line);
          if (msg.id === 1 && msg.result) {
            const proto = msg.result.protocolVersion || '?';
            const srv = (msg.result.serverInfo && msg.result.serverInfo.name) || '?';
            return done('OK', `proto=${proto} server=${srv}`);
          }
        } catch (_) {}
      }
    }
  });
  child.stderr.on('data', (d) => { stderr += d.toString(); });

  const req = JSON.stringify({
    jsonrpc: '2.0', id: 1, method: 'initialize',
    params: {
      protocolVersion: '2024-11-05', capabilities: {},
      clientInfo: { name: 'mcp-probe', version: '0.0.1' }
    }
  }) + '\n';

  try { child.stdin.write(req); } catch (_) {}
  setTimeout(() => done('TIMEOUT', `no response in ${TIMEOUT_MS}ms`), TIMEOUT_MS);
}
