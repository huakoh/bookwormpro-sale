---
name: mcp-probe
version: 1.0.0
description: |
  MCP 服务器连通性体检。对 .claude.json 中注册的全部 MCP (stdio + http) 发
  initialize 握手包或 HEAD 请求，输出每个服务器的启动耗时、健康状态和根因诊断。
  触发词: "体检MCP", "测MCP", "MCP健康检查", "MCP连通性", "mcp-probe",
  "probe mcp", "MCP全量测试", "MCP诊断", "所有MCP是否正常"。
maturity: stable
allowed-tools:
  - Bash
  - Read
  - Edit
  - Grep
  - Glob
---

# /mcp-probe — MCP 连通性体检

对用户 `~/.claude.json` 中注册的全部 MCP 服务器做一次并/串行健康检查，输出结构化报告。

## 数据源

```
配置: ~/.claude.json (mcpServers 字段)
脚本: ~/mcp-probe.js (探测实现)
结果: ~/mcp-probe-result.json (每次运行覆写)
```

## 探测策略

| 类型 | 探测方法 | 健康判据 |
|------|---------|---------|
| **stdio** (command+args) | spawn 子进程 → stdin 发 `initialize` JSON-RPC 包 → 监听 stdout 回包 | 收到 `{"id":1,"result":{...}}` 即 OK |
| **http** (type:http, url) | HTTPS HEAD 请求 | HTTP < 500 即 OK (401/405 表示 auth-required 也算通) |
| **超时** | 默认 8 秒 | 超过判为 TIMEOUT |
| **.cmd/.bat** | Windows 需 `shell: true` (Node 18.20+ CVE-2024-27980) | 已内置 |

## 执行流程

### Step 1 — 运行探测脚本

```bash
cd ~
node mcp-probe.js
```

**预期耗时**: 3-5 分钟（串行 28 个服务器，每个最多 8s + stdio 启动时间）。

如果脚本不存在，先提示用户: "检测到 `mcp-probe.js` 不存在，需要我先创建吗？" 然后基于本 Skill 末尾附录的模板生成。

### Step 2 — 读取结果

```bash
cat ~/mcp-probe-result.json
```

JSON 结构:

```json
[
  {
    "name": "github",
    "kind": "stdio",
    "status": "OK",
    "detail": "proto=2024-11-05 server=github-mcp-server",
    "ms": 1735,
    "stderrTail": ""
  },
  ...
]
```

**状态枚举**:
- `OK` — 握手成功或 HTTP 可达
- `TIMEOUT` — 超时未响应（可能首次安装 npm 包慢，建议单独重测 30s 超时）
- `CRASHED` — 启动后立即 exit，看 stderrTail 定位
- `SPAWN_ERROR` — 进程都没起来（PATH 问题 / 命令缺失）
- `NET_ERROR` — HTTP 网络失败
- `HTTP_ERROR` — HTTP 返回 5xx

### Step 3 — 输出报告

固定格式 markdown 表格，按状态分组:

```markdown
## MCP 连通性体检报告

**总计**: 28 个 | **OK**: N | **FAIL**: M | **TIMEOUT**: K

### ✅ 健康 (N)

| # | MCP | 类型 | 启动耗时 | serverInfo |
|---|-----|------|---------|-----------|
| 1 | github | stdio | 1.7s | github-mcp-server |
| ... | ... | ... | ... | ... |

### ❌ 异常 (M+K)

| # | MCP | 状态 | 可能原因 | 建议修复 |
|---|-----|------|---------|---------|
| 1 | slack | CRASHED | 缺环境变量 | 检查 .claude.json env 段 |
```

### Step 4 — 根因诊断（对每个 FAIL）

按 stderrTail 关键字匹配常见模式:

| stderrTail 关键字 | 根因 | 修复建议 |
|------|------|---------|
| `Please set XXX env` | 缺环境变量 | 在 `.claude.json.mcpServers.<name>.env` 补上 |
| `ERR_MODULE_NOT_FOUND` | npx 缓存 ESM/CJS 错配 | 清 `_npx/<hash>/` 目录后重试 |
| `Lock compromised` / `ECOMPROMISED` | npm 子依赖 postinstall 失败 | 看 npm log 找失败的子包，常见 puppeteer/sharp/canvas |
| `spawn EINVAL` | Node 18.20+ 拒绝直接 spawn .cmd | 脚本应已修; 若仍出现则升级脚本 |
| `'xxx.cmd' 不是内部或外部命令` | PATH 问题 | `where xxx.cmd` 确认安装 |
| `Unauthorized` / 401 | HTTP MCP 需要 OAuth | 属正常（需用户在 Claude Code 内授权）|
| `ECONNREFUSED` / `ETIMEDOUT` | 代理或网络问题 | 检查 clash/verge 代理状态 |

### Step 5 — 主动给修复方案

对每个 FAIL，不止列问题，要主动问用户"需要我直接修复吗？" — 如果用户同意:

- **缺环境变量**: 引导用户获取 token → Edit `.claude.json` 写入
- **npm 缓存损坏**: 直接执行清理命令（先确认用户授权）
- **puppeteer 下载失败**: 加 `PUPPETEER_SKIP_DOWNLOAD=true` + `PUPPETEER_EXECUTABLE_PATH`
- **HTTP 401**: 提示用户在 Claude Code 运行 `/mcp` → Authenticate

## 可选子命令

用户可在触发时附加参数:

### `/mcp-probe quick`
只测 HTTP MCP（秒级），跳过 stdio 启动慢的。

### `/mcp-probe <name>`
只测指定的一个 MCP，用 30s 超时（Python MCP 冷启动可能 5-10s）。

```bash
cd ~
node ~/.bookwormpro/skills/mcp-probe/scripts/probe-one.js <name>
```

输出单行 JSON。若 `mcp-probe.js` 全量体检中某服务器 TIMEOUT 但超时值边界（如 8.2s），用此脚本重测区分"偶发慢"和"持续故障"。

**已验证案例**: windows-mcp 在 8s 批量体检中超时（8.2s），30s 重测后 OK（9.2s / 4.1s），确认为 Python 冷启动波动而非故障。

### `/mcp-probe diff`
对比上次 `mcp-probe-result.json` 和这次结果，找出状态变化的 MCP（从 OK 变 FAIL 或反之）。

### `/mcp-probe fix`
全量探测 + 对 FAIL 项自动应用已知修复（需用户最终确认）。

## 输出约定

- 使用 markdown 表格，不用 emoji 滥用
- 启动耗时保留 1 位小数（秒）
- stderrTail 超 120 字符截断加 `...`
- 如果全部 OK，用一句话总结: "**28/28 MCP 全绿，系统健康**"
- 如果有 FAIL，末尾附修复优先级 (P0/P1/P2)

## 注意事项

- **不修改业务配置**: 修复仅限 `env` 段补全、npx 缓存清理、PUPPETEER 相关 env
- **不回显 token**: 若探测中读到 stderr 含 `xoxb-` / `sk-` 等格式的凭证，要脱敏后再显示
- **并发安全**: 脚本采用串行探测避免 CPU/IO 风暴，不建议改成 Promise.all
- **幂等性**: 重复执行不产生副作用，result.json 每次覆写

---

## 附录: mcp-probe.js 模板

若脚本丢失，用以下模板重建到 `~/mcp-probe.js`:

```javascript
// MCP connectivity probe
const { spawn } = require('child_process');
const https = require('https');
const fs = require('fs');

const CONFIG = JSON.parse(fs.readFileSync(require('os').homedir() + '/.claude.json', 'utf8'));
const servers = CONFIG.mcpServers || {};
const TIMEOUT_MS = 8000;

function probeStdio(name, cfg) {
  return new Promise((resolve) => {
    const start = Date.now();
    let stdout = '', stderr = '', settled = false, child;
    const done = (status, detail) => {
      if (settled) return;
      settled = true;
      try { child && child.kill('SIGKILL'); } catch (_) {}
      resolve({ name, kind: 'stdio', status, detail, ms: Date.now() - start,
        stderrTail: stderr.split('\n').filter(Boolean).slice(-3).join(' | ').substring(0, 200) });
    };
    try {
      const env = Object.assign({}, process.env, cfg.env || {});
      const needsShell = /\.(cmd|bat)$/i.test(cfg.command);
      child = spawn(cfg.command, cfg.args || [], {
        env, stdio: ['pipe', 'pipe', 'pipe'],
        shell: needsShell, windowsHide: true,
      });
    } catch (e) { return done('SPAWN_ERROR', e.message); }
    child.on('error', (e) => done('SPAWN_ERROR', e.message));
    child.on('exit', (code, sig) => {
      if (settled) return;
      done(code === 0 ? 'EXITED_OK' : 'CRASHED',
        `exit=${code} sig=${sig} stderr="${stderr.slice(-150).replace(/\n/g, ' ')}"`);
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
      params: { protocolVersion: '2024-11-05', capabilities: {},
        clientInfo: { name: 'mcp-probe', version: '0.0.1' } },
    }) + '\n';
    try { child.stdin.write(req); } catch (_) {}
    setTimeout(() => done('TIMEOUT', `no response in ${TIMEOUT_MS}ms`), TIMEOUT_MS);
  });
}

function probeHttp(name, url) {
  return new Promise((resolve) => {
    const start = Date.now();
    const u = new URL(url);
    const req = https.request({
      host: u.host, path: u.pathname + u.search, method: 'HEAD',
      timeout: TIMEOUT_MS, headers: { 'User-Agent': 'mcp-probe/0.1' },
    }, (res) => {
      resolve({ name, kind: 'http', status: res.statusCode < 500 ? 'OK' : 'HTTP_ERROR',
        detail: `HTTP ${res.statusCode}`, ms: Date.now() - start, stderrTail: '' });
      res.resume();
    });
    req.on('error', (e) => resolve({ name, kind: 'http', status: 'NET_ERROR',
      detail: e.code + ':' + e.message, ms: Date.now() - start, stderrTail: '' }));
    req.on('timeout', () => { req.destroy(); });
    req.end();
  });
}

(async () => {
  const names = Object.keys(servers);
  console.log(`probing ${names.length} MCP servers (TIMEOUT=${TIMEOUT_MS}ms)...`);
  const results = [];
  for (const name of names) {
    const cfg = servers[name];
    let r;
    if (cfg.type === 'http' || (cfg.url && /^https?:/.test(cfg.url))) {
      r = await probeHttp(name, cfg.url);
    } else if (cfg.command) {
      r = await probeStdio(name, cfg);
    } else {
      r = { name, kind: 'unknown', status: 'UNKNOWN_CONFIG',
        detail: JSON.stringify(cfg).slice(0, 100), ms: 0, stderrTail: '' };
    }
    const tag = r.status === 'OK' ? 'OK ' : (r.status === 'TIMEOUT' ? '???' : 'FAIL');
    console.log(`[${tag}] ${r.name.padEnd(22)} ${String(r.ms).padStart(5)}ms  ${r.status.padEnd(14)} ${r.detail}`);
    if (r.stderrTail) console.log(`     stderr: ${r.stderrTail}`);
    results.push(r);
  }
  console.log('\n=== SUMMARY ===');
  const byStatus = {};
  for (const r of results) byStatus[r.status] = (byStatus[r.status] || 0) + 1;
  for (const [k, v] of Object.entries(byStatus).sort((a, b) => b[1] - a[1])) {
    console.log(`  ${k.padEnd(16)} ${v}`);
  }
  fs.writeFileSync(require('os').homedir() + '/mcp-probe-result.json', JSON.stringify(results, null, 2));
  console.log('\nwrote mcp-probe-result.json');
})();
```
