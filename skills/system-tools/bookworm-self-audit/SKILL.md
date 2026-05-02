---
name: bookworm-self-audit
description: >
  BookwormPRO 全面自检管线 — 6 环节流水线（五柱体检 + .env审计 + 日志噪音 + 凭证冲突 + 连通性测试 + 自动修复），
  产出统一健康报告。触发词：bookworm自检、自检、self audit、全面体检。
version: 1.0.0
author: BookwormPRO (2026-05-02 实战验证)
tags: [health-check, audit, diagnostics, self-audit, bookwormpro]
maturity: stable
cost_level: medium
---

# BookwormPRO 全面自检管线

## 触发条件
- "bookworm自检" / "自检" / "全面体检"
- "self audit" / "bookworm self-audit"
- 子集触发: "bookworm自检 只看XXX"（XXX = cron/mcp/agent/skills/routing/env/日志/凭证/连通）

## 6 环节流水线

```
环节1  五柱体检    → Cron / MCP / Agent / Skills / Routing
环节2  .env 审计   → 标记在用/废弃/错误配置
环节3  日志噪音    → WARNING/ERROR 分布 + top patterns
环节4  凭证冲突    → credential_pool 重复/冲突/URL不一致
环节5  连通性测试  → 所有 provider 逐一 API 验证
环节6  自动修复    → 已知问题一键修（可选，需 --fix）
```

## 执行流程

### 环节1: 五柱体检

#### 1.1 Cron
```bash
python -c "
import json
from pathlib import Path
d = json.load(open(Path.home() / '.bookwormpro/cron/jobs.json'))
issues = [j for j in d['jobs'] if not j.get('model')]
for j in d['jobs']:
    print(f'  {j[\"id\"][:12]} | {j.get(\"name\",\"?\"):25s} | model={j.get(\"model\",\"NULL\")} | enabled={j.get(\"enabled\",\"?\")}')
print(f'Total: {len(d[\"jobs\"])} jobs, ModelNull: {len(issues)}')
"
```

#### 1.2 MCP
```bash
cd ~ && node mcp-probe.js 2>&1
# 读取结果统计
python -c "
import json
d = json.load(open('/c/Users/BOOKWORMPRO_USER/mcp-probe-result.json'))
ok = sum(1 for x in d if x['status']=='OK')
to = sum(1 for x in d if x['status']=='TIMEOUT')
cr = sum(1 for x in d if x['status']=='CRASHED')
print(f'Total={len(d)} OK={ok} TIMEOUT={to} CRASHED={cr}')
"
```

#### 1.3 Skills
```bash
python -c "
from pathlib import Path
import re
skills = Path.home() / '.bookwormpro' / 'skills'
ok = nofm = noname = nodesc = empty = total = 0
for f in sorted(skills.rglob('SKILL.md')):
    total += 1
    sz = f.stat().st_size
    if sz == 0: empty += 1; continue
    t = f.read_text(encoding='utf-8')
    if not t.startswith('---'): nofm += 1; continue
    parts = t.split('---', 2)
    if len(parts) < 3: nofm += 1; continue
    if not re.search(r'^name:\s*\S', parts[1], re.M): noname += 1
    if not re.search(r'^description:\s*\S', parts[1], re.M): nodesc += 1
    ok += 1
print(f'Total={total} OK={ok} Empty={empty} NoFM={nofm} NoName={noname} NoDesc={nodesc}')
"
```

#### 1.4 Routing
```bash
python -c "
import json
from pathlib import Path
df = Path.home() / '.claude/scripts/disambiguation-rules.json'
d = json.load(open(df))
rules = d['_meta']['ruleCount'] if '_meta' in d else '?'
ver = d['_meta']['version'] if '_meta' in d else '?'
print(f'  Rules: {rules} (v{ver})')
print(f'  File: {df} ({df.stat().st_size:,} bytes)')
"
```

### 环节2: .env 审计

```bash
python -c "
from pathlib import Path
env = Path.home() / '.bookwormpro' / '.env'
lines = env.read_text().strip().split('\n')
print(f'Total: {len(lines)} lines\n')

# 分类标记
known_active = ['ANTHROPIC_BASE_URL', 'DEEPSEEK_API_KEY', 'DEEPSEEK_BASE_URL',
    'GOOGLE_API_KEY', 'DASHSCOPE_API_KEY', 'DASHSCOPE_BASE_URL',
    'AUXILIARY_VISION_MODEL', 'BROWSERBASE_PROJECT_ID',
    'WEIXIN_', 'WECOM_']

for line in lines:
    if not line.strip() or line.startswith('#'):
        continue
    key = line.split('=')[0]
    val = line.split('=',1)[1] if '=' in line else ''
    is_sensitive = '***' in val or len(val) > 40
    display_val = '***' if is_sensitive else val[:60]

    # 检测问题
    issues = []
    if 'qwen-vl-max' in val and 'alibaba/' in val:
        issues.append('🔴 OpenRouter命名风格，应改为 qwen-vl-max')
    if 'OPENROUTER' in key.upper() or 'OPENAI' in key.upper():
        issues.append('⚠ 可能已废弃（当前 deepseek 主provider）')
    if key == 'AUXILIARY_VISION_MODEL' and 'alibaba/' in val:
        issues.append('🔴 模型路径错误')
    if 'bww.your-domain.com' in val and 'API_KEY' not in key:
        issues.append('⚠ BWW 中转站，需确认 API key 可用')

    tag = '🟢' if not issues else '🔴'
    print(f'{tag} {key}={display_val}')
    for i in issues:
        print(f'    {i}')
"
```

### 环节3: 日志噪音分析

```bash
echo "=== WARNING 分布 ==="
echo "Total WARNING: $(grep -c 'WARNING' ~/.bookwormpro/logs/agent.log 2>/dev/null)"
echo "Total ERROR: $(grep -c 'ERROR' ~/.bookwormpro/logs/agent.log 2>/dev/null)"
echo "skipping env: $(grep -c 'skipping env' ~/.bookwormpro/logs/agent.log 2>/dev/null)"
echo "auxiliary_client: $(grep -c 'auxiliary_client.*WARNING' ~/.bookwormpro/logs/agent.log 2>/dev/null)"
echo ""

echo "=== Top WARNING patterns ==="
grep 'WARNING' ~/.bookwormpro/logs/agent.log 2>/dev/null | \
  grep -oP 'agent\.\S+|root' | sort | uniq -c | sort -rn | head -8

echo ""
echo "=== 今日新增 ==="
echo "今日 WARNING: $(grep \"$(date +%Y-%m-%d).*WARNING\" ~/.bookwormpro/logs/agent.log 2>/dev/null | wc -l)"
echo "今日 ERROR: $(grep \"$(date +%Y-%m-%d).*ERROR\" ~/.bookwormpro/logs/agent.log 2>/dev/null | wc -l)"
```

### 环节4: 凭证冲突检测

```bash
python -c "
import json
from pathlib import Path

# 读 auth.json
auth = json.load(open(Path.home() / '.bookwormpro/auth.json'))
pool = auth.get('credential_pool', {})

print('=== credential_pool 条目 ===')
conflicts = []
for provider, entries in pool.items():
    for e in entries:
        label = e.get('label', '?')
        base = e.get('base_url', 'N/A')
        source = e.get('source', '?')
        print(f'  {provider:15s} | {label:25s} | {base:50s} | {source}')

        # 检测冲突模式
        if 'RELAY' in label.upper():
            conflicts.append(f'🔴 {provider}: {label} — RELAY条目，与主provider可能冲突')
        if 'OPENROUTER' in label.upper() and 'bww.your-domain.com' in base:
            conflicts.append(f'🔴 {provider}: {label} — BWW URL但标为OpenRouter')

if not conflicts:
    print('\n✅ 无凭证冲突')
else:
    print(f'\n{len(conflicts)} 冲突:')
    for c in conflicts:
        print(f'  {c}')

# 检查残留备份文件
backups = list(Path.home().glob('.bookwormpro/auth.json.*'))
if backups:
    print(f'\n⚠ {len(backups)} 残留备份文件:')
    for b in backups:
        print(f'  {b.name}')
"

# 检查是否有 .env 里的OPENAI残留
grep -c "OPENAI_" ~/.bookwormpro/.env 2>/dev/null && echo "⚠ .env中仍有OPENAI_残留" || echo "✅ .env无OPENAI残留"
```

### 环节5: Provider 连通性测试

```bash
python -c "
import os
from pathlib import Path
from dotenv import load_dotenv
import openai

load_dotenv(Path.home() / '.bookwormpro' / '.env')

tests = [
    ('deepseek', 'DEEPSEEK_API_KEY', 'DEEPSEEK_BASE_URL', 'deepseek-chat'),
    ('dashscope', 'DASHSCOPE_API_KEY', 'DASHSCOPE_BASE_URL', 'qwen-plus'),
    ('gemini', 'GOOGLE_API_KEY', None, None),
]

for name, key_env, url_env, model in tests:
    key = os.environ.get(key_env)
    base = os.environ.get(url_env)
    if not base and name != 'gemini':
        print(f'  {name:15s} ⚪ SKIP (no base_url)')
        continue
    try:
        client = openai.OpenAI(api_key=key or 'test', base_url=base)
        models = client.models.list()
        count = len(models.data) if hasattr(models, 'data') else '?'
        print(f'  {name:15s} 🟢 OK ({count} models)')
    except Exception as e:
        err = str(e)
        if '401' in err:
            print(f'  {name:15s} 🔴 401 (API key invalid/expired)')
        elif '403' in err:
            print(f'  {name:15s} 🔴 403 (access denied)')
        else:
            print(f'  {name:15s} 🔴 {err[:60]}')

# ANTHROPIC check (BWW relay)
bww_base = os.environ.get('ANTHROPIC_BASE_URL')
if bww_base:
    print(f'  anthropic(bww)  ⚪ BWW relay (需 ANTHROPIC_API_KEY 系统级变量)')
"
```

### 环节6: 自动修复（需要 --fix 参数）

触发方式: `bookworm自检 修复` 或 `bookworm自检 --fix`

已知可自动修复项:
1. `.env` 中 `AUXILIARY_VISION_MODEL=alibaba/qwen-vl-max` → 改为 `qwen-vl-max`
2. `.env` 中 `OPENAI_BASE_URL` / `OPENAI_API_KEY` 残留 → 删除
3. `auth.json.bak-*` / `auth.json.corrupt` 备份文件 → 删除
4. `credential_pool` 中 `RELAY_AS_*` 条目 → 删除

修复前**必须**展示变更计划，等待用户确认。

## 输出格式

```
══════ BookwormPRO 全面自检 · YYYY-MM-DD HH:MM ══════

  环节1 五柱体检
    Cron     🟢/🔴  N jobs / M model=null
    MCP      🟢/🔴  N/N online
    Skills   🟢/🔴  N 合规 / M 问题
    Routing  🟢/🔴  N rules (vX.X.X)

  环节2 .env 审计
    🟢 N 在用 / 🔴 M 需修复

  环节3 日志噪音
    WARNING: N total / M today
    Top: [pattern1] [pattern2] [pattern3]

  环节4 凭证冲突
    🟢 无冲突 / 🔴 M 冲突

  环节5 连通性
    🟢 N/N 通过 / 🔴 M 失败

  环节6 自动修复
    (仅 --fix 模式) 已修复 M/N

  综合: 🟢/🟡/🔴  M 项需关注
══════════════════════════════════════════════════════
```

## 子集模式

| 触发词 | 执行环节 |
|--------|----------|
| `bookworm自检` | 全部 1→5 |
| `bookworm自检 修复` | 全部 1→6 |
| `bookworm自检 只看cron` | 仅 1.1 |
| `bookworm自检 只看mcp` | 仅 1.2 |
| `bookworm自检 只看skills` | 仅 1.3 |
| `bookworm自检 只看env` | 仅 2 |
| `bookworm自检 只看日志` | 仅 3 |
| `bookworm自检 只看凭证` | 仅 4 |
| `bookworm自检 只看连通` | 仅 5 |

## 反模式

- ❌ 只看 WARNING 数量不看今日增量（历史噪音≠当前问题）
- ❌ 跳过 MCP 活体探测（静态配置≠运行时连通）
- ❌ 忽略 .env 中 OpenRouter 命名风格的模型路径（DashScope 不认 `alibaba/` 前缀）
- ❌ 只看 auth.json 不看 `.bak-*` 备份（密码学残留）
- ❌ 修复前不展示计划直接动手（第零章第 1 条）

## 常见问题速查 (2026-05-02 实战新增)

| 问题 | 根因 | 修复 |
|------|------|------|
| auxiliary_client 6165 条 WARNING (no provider available) | 辅助任务(压缩/摘要/记忆冲刷)找不到可用 provider，fallback 链全部失败 | `.env` 加 `OPENAI_API_KEY` + `OPENAI_BASE_URL` 指向主 provider 的 OpenAI 兼容端点 (如 deepseek: `OPENAI_BASE_URL=https://api.deepseek.com/v1`) |
| .env 模型名 OpenRouter 风格 | `alibaba/qwen-vl-max` 格式在 DashScope 不认 | 改为 `qwen-vl-max` (去 provider 前缀) |
| cron 任务名接近但 id 不同 | 多次创建导致 soul-drift-weekly + soul-drift-monday 并存 | 删 id 较短/较旧的，保留正式命名的 |
| agent.log 膨胀 (29k 行 4.2MB) | 历史 WARNING 累积 (尤其 auxiliary_client+credential_pool) | 截断保留最后 5000 行，日志轮转应由系统自动处理 |
| auth.json RELAY_AS_* 条目 | BWW 中转站配置时手动添加的 RELAY 凭证，与 env 官方 key URL 冲突 | `bookworm auth remove openrouter` 或编辑 auth.json 手动删 |

## 与 bookwormpro-five-pillar-health-check 的关系

本 skill 是 `bookwormpro-five-pillar-health-check` 的超集：
- 环节1 复用五柱体检的全部逻辑
- 环节2-6 为增量（.env审计/日志噪音/凭证冲突/连通性/自动修复）
- 日常快速体检用 "五柱体检"，深度全面审计用 "bookworm自检"
