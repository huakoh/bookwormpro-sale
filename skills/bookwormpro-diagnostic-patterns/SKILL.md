---
name: bookwormpro-diagnostic-patterns
description: BookwormPRO 系统诊断速查 — 五柱体检方法论、cron model=null 根治、BWR 路由位置、跨项目独立性、vision 路由失败排障、DeepSeek reasoning 400 排障
version: 1.0.0
tags: [diagnostic, pitfall, ops, BookwormPRO]
category: devops
maturity: stable
---

# BookwormPRO 诊断速查

> **统一入口**: 输入 `bookworm自检` 即可自动运行 6 环节全面管线（五柱 + .env + 噪音 + 凭证 + 连通 + 修复）。详见 `bookworm-self-audit` 技能。

今天发现的 6 个关键陷阱和诊断模式。

## 五柱体检法

```
Cron → MCP → Agent → Skills → Routing
  ↓       ↓       ↓        ↓         ↓
 cronjob  mcp-    delegate  find      route-
 list     probe   _task     SKILL.md  engine.js
```

每柱优先**活体验证**（spawn/exec），不只看静态数据。

## Cron model=null 陷阱

**症状**: cron job 报 `Non-retryable client error: 400 - but you passed .`
**根因**: 新建 cron job 默认 `model: null`，scheduler.py 行 838 回退到空字符串
**止血**: `jobs.json` 每个 job 补 `"model": "deepseek-v4-pro"`
**根治**: `cron/scheduler.py` 追加硬兜底（after yaml fallback）:
```python
if not model:
    model = "deepseek-v4-pro"
```
**防御**: `run_agent.py:875` 默认 `model: str = ""` 应拒绝空串

## BWR 路由追踪位置

**错误认知**: "0 BWR traces in agent.log → 路由未工作"
**正确位置**: BWR 数据在 `~/.claude/debug/route-YYYY-MM-DD.jsonl`（v6.6.1）或 `~/.bookwormpro/debug/`（v7.0.0）
**BWR Hook 集成**:
```python
from routing.bwr_hook import BWRHook
hook = BWRHook()
msg = hook.inject_directive(user_message)
```

## 跨项目独立性

- Bookworm v6.6.1: `~/.claude/` — **不可修改**
- BookwormPRO v7.0.0: `C:\Users\BOOKWORMPRO_USER\BookwormPRO\` — 工作目录
- 共享运行时: `~/.bookwormpro/` — config/skills/logs/cron
- **规则**: v7.0.0 需 v6.6.1 代码 → 复制，不引用路径

## 代码统一合并

散落多处的代码合并到主目录:
1. `diff` 三份副本的 run_agent.py
2. 只复制 NEWER 文件（size > main）
3. 保留 main 的独有文件
4. 归档旧副本 `.archived-YYYYMMDD`
5. GitHub push 同步

## Hook 失败误判

agent.log 中 `hook failed` 若路径含 `pytest-of-BOOKWORMPRO_USER` → 测试噪声，非生产故障。
生产 hook 注册在 `~/.claude/settings.json` → `UserPromptSubmit → prompt-dispatcher.js`

## 消歧引擎 Submit 机制

**症状**: 消歧规则匹配但目标 skill 路由错误
**根因**: `route-analyzer.js:applyDisambiguation` — boost 仅对 BM25 结果中已存在的 skill 生效
**修复**: 添加 submit 逻辑 — 规则触发但 skill 不在结果中时注入虚拟条目:
```javascript
results.push({
  name: rule.boost,
  score: maxScore * 0.5,  // 基准分 = 最高分 × 50%
  _submitted: true,
});
```
**效果**: 准确率 84.1% → 88.9% (+4.8%)

## 路由准确率基准

```
75.4%  →  原始金标 (170条, skills-index-lite.json 无 keywords → BM25=0)
84.1%  →  换用 skills-index.json (980KB) + 16 消歧规则
88.9%  →  Submit 机制 (规则匹配但skill不在BM25时注入虚拟条目)
91.7%  →  +7 消歧规则 (R119-R125)
96.8%  →  索引补全 13 个缺失技能 (spotify/youtube/huggingface等)
```

**金标测试命令**: `cd routing && node accuracy.js`

## BWR 引擎迁移模式

从 v6.6.1(~/.claude/scripts/) → v7.0.0(BookwormPRO/routing/):
1. 复制所有路由相关 .js/.json 文件
2. 复制 lib 依赖 (root.js, safe-append.js, read-stdin.js)
3. 路径适配: CLAUDE_ROOT → BOOKWORMPRO_ROOT, ../hooks/lib/ → ./lib/
4. route-engine.js: SCRIPTS_DIR = __dirname (模块同目录)
5. lib/root.js: 返回 ~/.bookwormpro/ (runtime数据) 非项目根
6. 验证: `node -e "require('./route-engine.js')"` 9模块链加载

## skills-index 陷阱

- `skills-index-lite.json`: 94技能, 无 keywords/tokens → BM25 全 0 分
- `skills-index.json`: 980KB, 含 keyword/weight/tier → BM25 正常
- route-engine.js 行60必须指向 skills-index.json (非 lite)
- 索引缺失技能时: 补 keywords 数组 `[{keyword, weight, tier}]`

## 消歧规则格式

```json
{"id": "R94", "note": "...", "trigger": "regex", "boost": "target-skill",
 "penalty": ["wrong-skill"], "weight": 0.35}
```
- trigger: regex string, 自动编译为 RegExp('i')
- boost: 目标 skill 名, 必须与 skills-index 中 name 一致
- submit机制: boost target 不在 BM25 结果中时自动注入 `{name, score: max*0.5, _submitted: true}`

## Hermes 引用清理模式

| 风险 | 操作 | 示例 |
|------|------|------|
| 🟢 低 | HTTP Header, 显示名, 注释 | User-Agent: HermesAgent → BookwormPRO |
| 🟡 中 | 添加别名, 标记弃用 | get_bookwormpro_home() → get_hermes_home() |
| 🔴 高 | 不改公共API | get_hermes_home() 339处引用, 保留 |

## npm deprecation 修复

```bash
npm config delete minimum-release-age
```
症状: 7/11 MCP 启动时 `npm warn Unknown user config "minimum-release-age"`

## 凭证池冲突 — 三级排查法

### 症状
`skipping env:OPENROUTER_API_KEY seed — RELAY_AS_OPENROUTER targets different URL` (521+ 条噪音)

### 根因
`auth.json` 中 `credential_pool.openrouter[]` 存在一条 `RELAY_AS_OPENROUTER`（手动添加，`base_url: https://bww.your-domain.com/v1`），与 `OPENROUTER_API_KEY` 环境变量的目标 URL（`openrouter.ai`）冲突。credential_pool 每次尝试验证时都会 skip 一次。

### 三级排查

**Level 1 — 检查 live auth.json**
```bash
python -c "
import json
pool = json.load(open('~/.bookwormpro/auth.json'))['credential_pool']
for p, entries in pool.items():
    for e in entries:
        print(f'{p}: {e[\"label\"]} → {e.get(\"base_url\",\"\")}')
"
```
如果已干净 → 进入 Level 2

**Level 2 — 区分历史噪音 vs 活跃问题**
```bash
grep "skipping env:OPENROUTER" agent.log | tail -1
```
看最后一条时间戳：如果 >1 天前 → 历史噪音，问题已修复。如果今天 → 进入 Level 3。

**Level 3 — 检查备份文件**
```bash
ls ~/.bookwormpro/auth.json.*  # bak-before-restore, corrupt 等
grep RELAY_AS_OPENROUTER ~/.bookwormpro/auth.json.*
```
备份文件常残留旧条目，虽不影响运行但会误导诊断。确认后删除。

### 清理步骤
1. live auth.json 删除 RELAY 条目（若还存在）
2. 删除所有 auth.json 备份文件: `rm auth.json.bak-before-restore auth.json.corrupt`
3. 验证: `grep -c RELAY_AS ~/.bookwormpro/auth.json` → 0
4. 确认无新噪音: 等待 1 分钟后 `grep "skipping env" agent.log | tail -1` 时间戳不变

### 联动清理
RELAY 条目移除后，同步清理 `.env` 中关联项:
- `OPENAI_BASE_URL`（仅为 BWW relay 设置）
- `OPENAI_API_KEY`（仅为 BWW relay 设置）

## Git 工作流 (BookwormPRO)

```bash
cd C:/Users/BOOKWORMPRO_USER/BookwormPRO
git reset HEAD --quiet          # 清 index
git add <精准文件列表>            # 逐个 add, 不用 git add .
git diff --cached --stat        # 核对
git diff --cached               # 逐行核对
git commit -m "type(scope): ..." # 提交
git push origin main            # NEVER force push
```

## Gateway 状态检查

BookwormPRO Gateway 是独立进程（非 CLI 会话的一部分），负责企业微信/个人微信/Telegram 等多平台消息收发。

### 检查进程是否存活

```bash
# Windows: 通过命令行参数定位 Gateway 进程
wmic process where "name='python.exe'" get processid,commandline | grep "hermes-gateway"
# 应输出: python.exe -u scripts/hermes-gateway run  <PID>
```

**误判陷阱**: 简单的 `tasklist | grep gateway` 可能漏报，因为 Python 进程名显示为 `python.exe` 而非 `gateway`。必须用 `wmic` 查看完整命令行。

### 检查日志

```bash
# 查看最近日志（确认平台连接状态）
tail -30 ~/.bookwormpro/logs/gateway.log
# 关键行:
#   [成功] wecom connected     — 企业微信已连接
#   [成功] weixin connected    — 个人微信已连接
#   Gateway running with N platform(s) — 运行中
```

### 验证 Webhook 端口

```bash
curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 http://127.0.0.1:8644/
# HTTP 404 = webhook 监听正常（无路由配置时返回 404）
# 超时/拒绝连接 = Gateway 已停止
```

### 检查进程启动时间

```bash
wmic process where processid=<PID> get creationdate
```

### 常见故障模式

| 症状 | 原因 | 处理 |
|------|------|------|
| Gateway 进程不在 | 未启动或已崩溃 | `python scripts/hermes-gateway run` |
| WeCom WebSocket 频繁断开 | 网络波动 / openws 限流 | 日志中 `Reconnected` 为自动恢复，无需干预 |
| Weixin poll error | ilinkai 连接超时 | 重试机制已内置，连续失败 3 次才需关注 |

### 日志最后修改时间判断

```bash
stat ~/.bookwormpro/logs/gateway.log | grep Modify
# 如果最后修改时间超过 5 分钟且无新日志，进程可能已僵死
```

## BWR 反馈闭环

- `routing/route-feedback.js` — 自动收集 mismatch → 生成消歧建议
- `routing/bwr_reporter.py` — Agent 调用 skill 后回填 actualSkill
- `~/.bookwormpro/debug/route-feedback-live.jsonl` — 反馈数据文件

## DeepSeek reasoning_content 400 排障

**症状**: `HTTP 400: The reasoning_content in the thinking mode must be passed back to the API.`
**三连特征**: 同一 session 中 deepseek-v4-pro → v4-flash 都出 400，更换模型也无法恢复。

### 根因分析

错误提示「reasoning_content 必须回传」意味着会话历史中存在未带 `reasoning_content` 的 assistant 消息。

**两个独立阶段**:

| 阶段 | 时机 | 修复入口 |
|------|------|----------|
| 创建时 | 新消息生成后 | `_build_assistant_message()` — 即时 pin `reasoning_content=""` |
| 回放时 | 已有消息发送 API 前 | `_copy_reasoning_content_for_api()` — 逐条补丁 |

### 两个独立修复（必须同时生效）

| 提交 | 修复内容 | 场景 | 测试 |
|------|----------|------|------|
| `e89323ac` | 拆分 DeepSeek/Kimi 条件：DeepSeek 所有 assistant 消息都补 `reasoning_content=""`，Kimi 仅 tool_calls | 已正确设置 `_needs_deepseek_tool_reasoning()` 的场景 | 26/26 passed |
| `1f504d44` | 移除 `_build_assistant_message` 中的 `hasattr` 门控：当 SDK 响应的 `ChatCompletionMessage` 对象没有 `reasoning_content` 属性时，整个 pin 逻辑被跳过 | SDK 不包含该属性（旧版本、非流式响应） | 26/26 passed |

**注意**: 两个修复必须在同一行：`hasattr` 门控会绕过 `_needs_deepseek_tool_reasoning()` 检查，即使 E1 的条件拆分正确，只要 SDK 缺属性，保护就不生效。

### 验证当前代码是否已生效

```bash
python -c "
from run_agent import AIAgent
agent = object.__new__(AIAgent)
agent.provider = 'deepseek'
agent.model = 'deepseek-v4-pro'
agent.base_url = 'https://api.deepseek.com/v1'

# 测试1: 没有 reasoning_content 属性的 SDK 消息
class SDKMsg:
    content = 'hello'
    tool_calls = []
msg = agent._build_assistant_message(SDKMsg(), 'stop')
assert msg.get('reasoning_content') == '', f'FAIL: {msg.get(\"reasoning_content\")}'
print('PASS: no-attr SDK message pinned to empty string')

# 测试2: 历史消息回放
source = {'role': 'assistant', 'content': 'hi'}
api_msg = {}
agent._copy_reasoning_content_for_api(source, api_msg)
assert api_msg.get('reasoning_content') == ''
print('PASS: replay padded with empty string')
"
```

### 区分「修复未生效」和「历史毒化」

如果验证代码通过但 session 仍报 400 → 该 session 在旧代码下已写入毒化消息。**必须用新 session，旧 session 无法挽救。**

### 修复 Git 工作流（Windows CRLF）

BookwormPRO 的 `run_agent.py` 有混合 CRLF/LF 换行，`patch` 工具经常失败：

```python
# 用 Python 脚本修改，代替 patch
from pathlib import Path
target = Path(r'C:\Users\BOOKWORMPRO_USER\BookwormPRO\run_agent.py')
raw = target.read_bytes()
# ... bytes-level find-and-replace ...
target.write_bytes(new_raw)
# 然后验证: python -m py_compile run_agent.py
```

验证成功后：

```bash
python -m pytest tests/run_agent/test_deepseek_reasoning_content_echo.py -v
# 期望: 26/26 passed
```

### 修复后需重启 gateway

```bash
python scripts/hermes-gateway restart
# 需要管理员权限
```

### 修复验证

```bash
# 运行完整测试套
cd /path/to/BookwormPRO
python -m pytest tests/run_agent/test_deepseek_reasoning_content_echo.py -v
# 期望: 26/26 passed
```

### 关键代码分支 (run_agent.py)

```
_build_assistant_message (L7674-7686):
  hasattr(reasoning_content)?
  ├─ Yes, not None → preserve
  ├─ Yes, None + needs_deepseek → pin ""
  ├─ Yes, None + tool_calls + needs_kimi → pin ""
  └─ Yes, None + other providers → leave alone

_copy_reasoning_content_for_api (L7791-7813):
  role==assistant?
  ├─ has reasoning_content (str) → pass through
  ├─ has reasoning (str, non-empty) → promote to reasoning_content
  ├─ needs_deepseek → pad ""
  ├─ tool_calls + needs_kimi → pad ""
  └─ other → leave alone
```

## Vision 路由失败 (non-vision provider)

**症状**: `vision_analyze` 返回 `unknown variant 'image_url', expected 'text'`
**触发**: 当前主模型不支持多模态输入 (DeepSeek v4 Pro 等 text-only 模型)
**根因**: `resolve_vision_provider_client()` auto-detect 对未在 `_PROVIDER_VISION_MODELS` 中的 provider 回退到 `main_model`，但该模型不支持 vision

### 三步路由逻辑 (auxiliary_client.py L2283-2316)

```
Step A: _PROVIDER_VISION_MODELS.get(main_provider)
  命中 (xiaomi→mimo-v2.5, zai→glm-5v-turbo) → 使用专用 vision 模型
  未命中 ↓

Step B: main_provider in _PROVIDERS_NATIVE_VISION_MAIN_MODEL
  命中 (openai, anthropic, google, gemini, mistral, xai, groq) → 主模型做 vision
  未命中 ↓

Step C: 跳过主 provider → fallback 到 aggregator 链
  → OpenRouter (gemini-3-flash-preview)
  → BookwormPRO Portal
```

### 诊断流程

```bash
# 1. 确认主 provider
grep "provider:" ~/.bookwormpro/config.yaml

# 2. 检查模型 vision 能力
python -c "
import json
with open('~/.bookwormpro/models_dev_cache.json') as f:
    data = json.load(f)
    # 检查主 provider 模型是否支持 image 输入
"

# 3. 检查路由配置
grep -n "_PROVIDER_VISION_MODELS\|_PROVIDERS_NATIVE_VISION_MAIN_MODEL" \
  C:/Users/BOOKWORMPRO_USER/BookwormPRO/agent/auxiliary_client.py
```

### 快速 workaround (不改代码)

```yaml
# config.yaml — 强制 vision 走 OpenRouter
auxiliary:
  vision:
    provider: openrouter
```

### 新增 provider 到白名单

如果新 provider 的主模型原生支持 vision:
```python
# auxiliary_client.py L165-178
_PROVIDERS_NATIVE_VISION_MAIN_MODEL: set = {
    "openai", "anthropic", "google", "gemini",
    "mistral", "xai", "groq",
    "new_provider",  # ← 新增
}
```

如果新 provider 有专用 vision 模型:
```python
_PROVIDER_VISION_MODELS: Dict[str, str] = {
    "xiaomi": "mimo-v2.5",
    "zai": "glm-5v-turbo",
    "new_provider": "their-vision-model",  # ← 新增
}
```

### Provider Health Probe (copilot false-positive)

**症状**: `provider_health.probe('copilot', 'https://api.githubcopilot.com')` 返回 DEGRADED/DEAD
**根因**: GitHub Copilot API 不暴露标准 REST `/models` 端点。`GET /models` → HTTP 400, `HEAD /` → HTTP 404。`_build_probe_url()` 无 copilot 专用 probe 路径。
**处理**: Copilot 使用 ACP subprocess 传输，非 HTTP。重置误报健康状态：
```python
from agent.provider_health import reset as health_reset
health_reset('copilot')
```
**脚本**: `scripts/provider_health_probe.py` — 全量 provider 健康探测，自动发现 auth.json + .env 中的 provider。

## auxiliary_client.py CRLF 陷阱

`auxiliary_client.py` (148KB, 3400+ 行) 与 `run_agent.py` 一样有混合 CRLF/LF 换行，`patch` 工具经常报告 "verification failed" 但修改实际已生效。**规则**: patch → 读回修改行 → 内容正确就继续，跳过重复应用。语法检查 `py_compile` 必须过。



## HTTP 连接池初始化缺失 (run_agent.py)

**症状**: 新窗口启动后立即报错
```
Failed to initialize agent: Failed to initialize OpenAI client:
'AIAgent' object has no attribute '_http_pool_lock'
```

**根因**: `run_agent.py` 连接池复用补丁在 5 处用了 `with self._http_pool_lock:` (L4403/4969/5158/5198)，但 `__init__` 中漏了初始化。老会话存活是因为生命周期中某处隐式创建了该属性；新窗口首次 `close()` 时 `AttributeError`。

**修复** (`run_agent.py` L1358, `self.client = None` 之后):
```python
self.client = None
self._client_kwargs = {}
# 新增:
self._http_client_pool = {}
self._http_pool_lock = threading.Lock()
self._http_client_pool_last_use = {}
```

**验证**: `python -c "import py_compile; py_compile.compile('run_agent.py', doraise=True)"`

## _validate_config_structure 未定义 (config.py)

**症状**: `bookworm` 启动时 28 行警告
```
Warning: Failed to load config: name '_validate_config_structure' is not defined
```
（重复刷屏，但 Agent 仍能启动）

**根因**: Gateway 加固补丁回滚时删除了 `_validate_config_structure` 函数定义，但调用处（`bwm_cli/config.py` L6284）残留。

**诊断**:
```python
python -c "
from pathlib import Path
f = Path.home() / 'BookwormPRO' / 'bwm_cli' / 'config.py'
c = f.read_text()
has_call = '_validate_config_structure(' in c
has_def = 'def _validate_config_structure' in c
print(f'Call: {has_call}, Def: {has_def}')
"
# Call: True, Def: False → 空心调用
```

**修复**: `git checkout -- bwm_cli/config.py` 回退到干净版本（同时移除调用和定义），或注入 stub：
```python
def _validate_config_structure(config):
    return []  # no-op stub
```

## Python import 作用域陷阱 (run_agent.py 修复加深)

**症状**: `cannot access local variable 'threading' where it is not associated with a value`
**根因**: 在方法内部写 `import threading; if hasattr(...): self.lock = threading.Lock()` — Python 编译器看到后面的 `threading.Lock()` 就将 `threading` 标记为局部变量，但 `import threading` 在 `hasattr` 为 True 时被跳过，导致变量未初始化。

**修复**: 将 `import` 移入条件块内，并使用别名：
```python
# ❌ 错误
import threading
if not hasattr(self, '_lock'):
    self._lock = threading.Lock()

# ✅ 正确
if not hasattr(self, '_lock'):
    import threading as _t
    self._lock = _t.Lock()
```

**通用规则**: 条件块内的 `import` 必须使用 `as` 别名，且只能在条件为 True 的分支中使用

```bash
find ~/.bookwormpro/skills/ -name "SKILL.md" -mtime +30 | wc -l
```
报告自动写入 `~/.bookwormpro/debug/skills-zombies.json`

## auxiliary_client 盲区修复

**症状**: agent.log 大量 `auxiliary_client: Auxiliary auto-detect: no provider available (tried: openrouter, bookwormpro, local/custom, openai-codex, api-key)`（累计 6165+ 条）
**根因**: 辅助任务（上下文压缩/摘要/记忆冲刷）的 provider 解析链只尝试 OpenRouter → Portal → local/custom → Codex → api-key，均不可用
**修复**: .env 注入 `OPENAI_API_KEY` + `OPENAI_BASE_URL=https://api.deepseek.com/v1`，利用 DeepSeek 的 OpenAI 兼容端点接管辅助任务
**验证**: 等待一次压缩/摘要触发，检查 agent.log 是否仍有 "no provider available"

## DashScope 模型命名陷阱

**症状**: `AUXILIARY_VISION_MODEL=alibaba/qwen-vl-max` → 404 model_not_found
**根因**: `alibaba/` 前缀是 OpenRouter 的命名约定。DashScope `/compatible-mode/v1` 使用原生命名 `qwen-vl-max`
**修复**: 去掉 `alibaba/` 前缀，改为 `qwen-vl-max`
**通用规则**: 使用 DashScope compatible-mode 端点时，所有模型名不加 provider 前缀

## 会话产物

- `bookworm-self-audit` (318行, 6环管线) → 统一自检入口
- `bookworm自检 修复` → 自动修复已知问题
- `bookworm自检 只看cron/env/日志/凭证/连通` → 子集模式
