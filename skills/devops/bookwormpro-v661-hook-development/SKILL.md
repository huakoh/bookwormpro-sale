---
name: bookwormpro-v661-hook-development
description: >
  Bookworm v6.6.1 Hook 开发与注册方法 — 当需要为 v6.6.1 (~/.claude/) 系统创建新 hook
  (JS 文件) 并注册到 settings.json 时使用。覆盖 stdin/out 协议、生命周期事件、
  matcher 规则、状态文件管理、settings.json 注册格式。
version: 1.0.0
tags: [bookwormpro, v6.6.1, hook, dev, reference]
category: devops
maturity: stable
---

# Bookworm v6.6.1 Hook 开发与注册

> 实战验证于 2026-05-02 的 5 个 hook 创建 (circuit-breaker / rate-limit-guard /
> post-batch-progress / session-health-probe / post-skill-feedback)。

## Hook 文件结构

### 最小模板

```javascript
'use strict';

const fs = require('fs');
const path = require('path');

// Claude Root 获取 (兼容 hook lib/ 和独立运行)
const CLAUDE_ROOT = (() => {
  try { return require('./lib/root.js'); }
  catch { return path.resolve(__dirname, '..'); }
})();

function main() {
  const input = JSON.parse(fs.readFileSync(process.stdin.fd || 0, 'utf8'));
  // ... 处理逻辑 ...
  process.stdout.write(JSON.stringify({ status: 'ok' }));
}

try {
  main();
} catch (e) {
  process.stderr.write('[hook-name] Error: ' + e.message + '\n');
  process.stdout.write(JSON.stringify({ status: 'error', error: e.message }));
}
```

### stdin/out 协议

- **stdin**: JSON 对象, 包含 `tool_name`, `tool_input`, `tool_result`, `user_message`, `cwd` 等
- **stdout**: JSON 对象; 可包含 `systemMessage` (注入系统提示), `status`
- **stderr**: 仅用于调试, 不影响 hook 结果
- **不输出 stdout → hook 被视为 no-op**

### systemMessage 注入

```javascript
// 注入系统提示 (模型会在下一轮看到)
return output({ systemMessage: '⚠ 警告信息' });

// 无提示
return output({ status: 'ok' });
```

## settings.json 注册

### 注册格式

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [{
          "type": "command",
          "command": "node C:/Users/BOOKWORMPRO_USER/.claude/hooks/your-hook.js",
          "timeout": 3000
        }]
      }
    ]
  }
}
```

### 生命周期事件 (8 种)

| 事件 | 触发时机 | 典型用途 |
|------|---------|---------|
| `UserPromptSubmit` | 用户发送消息时 | 会话初始化, 健康探测, 上下文注入 |
| `PreToolUse` | 工具调用前 | 安全检查, 路由合规, 命令预检 |
| `PostToolUse` | 工具调用后 | 反馈记录, 进度跟踪, 错误检测 |
| `PreCompact` | 上下文压缩前 | 状态存档, handoff |
| `SubagentStart` | 子代理启动时 | 路由注入 |
| `Stop` | 会话结束时 | 清理, 报告 |
| `SubagentStop` | 子代理结束时 | 结果收集 |
| `Notification` | 外部通知时 | (较少用) |

### Matcher 规则

```javascript
// 空字符串 = 匹配所有工具
"matcher": ""

// 精确匹配单个工具
"matcher": "Bash"

// 正则 OR 匹配
"matcher": "Write|Edit|Patch"

// 正则模式匹配 (mcp__ 前缀)
"matcher": "mcp__.*"

// 多个条件
"matcher": "Skill|Agent"
```

**注意**: 无 SessionStart 事件 — 首个 UserPromptSubmit 承担此角色。

### Timeout 选择

| 操作类型 | 推荐 timeout | 说明 |
|---------|------------|------|
| 轻量检查 (读文件/计算) | 2000ms | circuit-breaker, rate-limit |
| 文件写入 | 3000ms | post-batch-progress, feedback |
| 网络探测 | 5000-8000ms | health-probe |
| 安全检查 | 5000ms | bash-precheck, tirith |

### 注册脚本 (Python)

```python
import json
from pathlib import Path

settings_path = Path.home() / '.claude' / 'settings.json'
data = json.loads(settings_path.read_text(encoding='utf-8'))

# 获取目标 hook 列表
target_hooks = data['hooks'].get('PostToolUse', [])

# 创建新 hook 条目
new_hook = {
    'matcher': 'Write|Edit',
    'hooks': [{
        'type': 'command',
        'command': 'node C:/Users/BOOKWORMPRO_USER/.claude/hooks/my-hook.js',
        'timeout': 3000
    }]
}

# 插入策略: insert(0) = 最高优先级, append = 最低优先级
target_hooks.insert(0, new_hook)  # 或 target_hooks.append(new_hook)

data['hooks']['PostToolUse'] = target_hooks
settings_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
```

## 状态文件管理

### 模式

```javascript
const STATE_DIR = path.join(CLAUDE_ROOT, 'session-state');
const STATE_FILE = path.join(STATE_DIR, 'state.json');

function ensureDir() {
  if (!fs.existsSync(STATE_DIR)) {
    fs.mkdirSync(STATE_DIR, { recursive: true });
  }
}

function loadState() {
  ensureDir();
  try {
    if (fs.existsSync(STATE_FILE)) {
      return JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
    }
  } catch {}
  return { /* 默认值 */ };
}

function saveState(state) {
  ensureDir();
  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2), 'utf8');
}
```

### 命名约定

- 状态文件: `session-state/<hook-name>.json` 或 `session-state/<hook-name>-state.json`
- Feedback 数据: `debug/route-feedback-live.jsonl`
- 进度文件: `<cwd>/.bookworm-progress.md`

## 常见模式

### 1. 错误检测 (PostToolUse)

```javascript
function isApiError(toolOutput) {
  if (!toolOutput || typeof toolOutput !== 'string') return false;
  const snippet = toolOutput.slice(0, 500);
  return ERROR_PATTERNS.some(p => p.test(snippet));
}
```

### 2. 滑动窗口

```javascript
const WINDOW_MS = 300000; // 5 分钟
state.events = state.events.filter(e => Date.now() - e.ts < WINDOW_MS);
```

### 3. 数据脱敏

```javascript
const REDACT_PATTERNS = [
  { pattern: /sk-[a-zA-Z0-9]{20,}/g, replacement: '[REDACTED_API_KEY]' },
  { pattern: /Bearer\s+[a-zA-Z0-9\-_\.]{20,}/g, replacement: 'Bearer [REDACTED]' },
];

function redact(str) {
  let result = (str || '').slice(0, 200);
  for (const { pattern, replacement } of REDACT_PATTERNS) {
    result = result.replace(pattern, replacement);
  }
  return result;
}
```

### 4. 文件权限 (Unix)

```javascript
function setSecurePermissions(filePath) {
  try {
    if (process.platform === 'win32') return; // Windows 无 chmod
    fs.chmodSync(filePath, 0o600);
  } catch {}
}
```

## 语法检查

```bash
node --check "C:/Users/BOOKWORMPRO_USER/.claude/hooks/your-hook.js"
```

## 反模式

- ❌ 在 hook 中使用 `setTimeout` / `setInterval` (定时外联 = 违反 NEVER 红线)
- ❌ 硬编码密钥/Token 在 hook 源码中
- ❌ hook 超时 > 10s (阻塞工具调用链)
- ❌ 写大量数据到 state 文件 (> 100KB)
- ❌ 在 hook 中修改 .env / .gitignore
- ❌ 忘记 try-catch 包裹主逻辑 (hook 崩溃 = 静默失败)
- ❌ 用 `write_file` / `patch` 工具写入 hook 源码 (Windows CRLF 会导致 patch 工具报 "verification failed" 假阴性 — 内容常实际写入但校验失败。改用 Python `open(path,'wb').write()` 二进制模式安全写入)

## 安全设计清单 (涉及外部输入/网络/二进制的 hook)

- [ ] **网络 hook**: 内置白名单域名校验 (防 SSRF)，不向任意 URL 发请求
- [ ] **二进制调用 hook**: SHA-256 验签 + `fallback=deny` (不可用时拒绝而非放行) + 超时 < 5s
- [ ] **用户数据落地 hook**: query 字段脱敏 (API Key / Token / 密码) + 文件权限 0600 + 条目上限
- [ ] **数据文件**: 写操作前备份原文件; 合并场景用 diff 策略, 不直接覆盖
- [ ] **状态文件**: 自举初始化 (lazy mkdir), 不假设目录预先存在

## 验证清单

- [ ] `node --check` 语法通过
- [ ] settings.json 已注册 (含正确的 matcher 和 timeout)
- [ ] 状态目录自举 (lazy mkdir, 不依赖预先存在)
- [ ] 错误处理完整 (try-catch + stderr 日志)
- [ ] 不违反 NEVER 红线 (无 eval, 无暴露凭证, 无外联到未知域名)
- [ ] timeout 合理 (轻量 < 3s, 网络 < 8s)
