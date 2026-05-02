---
name: bookwormpro-five-pillar-health-check
description: BookwormPRO 五柱系统体检 — Cron/MCP/Agent/Skills/Routing 逐项健康检查 + 优化建议。触发词：系统体检、全量体检、health check、五柱、system audit。
version: 1.0.0
author: BookwormPRO (2026-05-01 实战验证)
tags: [health-check, audit, system, diagnostics, monitoring]
maturity: stable
cost_level: medium
---

# BookwormPRO 五柱系统体检

> **超集技能**: `bookworm-self-audit`（输入 `bookworm自检`）—— 包含本技能的全部五柱检查，外加 .env 审计、日志噪音分析、凭证冲突检测、Provider 连通性测试、自动修复。日常快速体检用本技能，全面深度审计用 `bookworm自检`。

## 触发条件
- "系统体检" / "全量体检" / "health check"
- "五柱" / "system audit"
- 定期维护或部署后验证

## 五柱定义

| 柱子 | 检查内容 | 关键文件 |
|------|---------|---------|
| **Cron** | 定时任务健康 | `~/.bookwormpro/cron/jobs.json`, `errors.log` |
| **MCP** | MCP 服务器连通性 | `~/.claude.json`, `mcp-probe.js` |
| **Agent** | 子 Agent + 模块完整性 | `run_agent.py`, `delegate_task` 烟雾测试 |
| **Skills** | 技能完整性 + 活跃度 | `~/.bookwormpro/skills/`, YAML 合规 |
| **Routing** | BWR 路由引擎 + 消歧规则 | `routing/`, `disambiguation-rules.json`, `golden-set.json` |

## 执行流程

### Phase 1: Cron
```bash
# 列出所有 cron jobs
bookworm cron list  # or cronjob(action='list')

# 检查错误日志
grep "cron.*ERROR\|cron.*error" ~/.bookwormpro/logs/errors.log | tail -20

# 关键检查：model 字段是否为 null
python -c "import json; d=json.load(open('~/.bookwormpro/cron/jobs.json')); [print(j['id'][:12], j['name'], 'model='+str(j.get('model'))) for j in d['jobs']]"
```

### Phase 2: MCP
```bash
# 运行全量体检
cd ~ && node mcp-probe.js

# 读取结果
cat ~/mcp-probe-result.json | python -c "import json,sys; d=json.load(sys.stdin); print(f'OK={sum(1 for x in d if x[\"status\"]==\"OK\")} TIMEOUT={sum(1 for x in d if x[\"status\"]==\"TIMEOUT\")} CRASHED={sum(1 for x in d if x[\"status\"]==\"CRASHED\")}')"

# 对 TIMEOUT 服务器单独 30s 重测
```

### Phase 3: Agent
```bash
# 子 Agent 烟雾测试
delegate_task(goal="echo AGENT_SMOKE_TEST_OK && node -e 'console.log(process.version)' && python -c 'import sys; print(sys.version.split()[0])'", toolsets=["terminal"])

# 模块完整性
wc -l run_agent.py  # 应 > 8000
find agent/ -name "*.py" | wc -l  # 应 > 50
```

### Phase 4: Skills
```bash
# 全量 YAML 合规扫描
python -c "
from pathlib import Path
skills = Path.home() / '.bookwormpro' / 'skills'
ok = nofm = noname = nodesc = empty = 0
for f in skills.rglob('SKILL.md'):
    sz = f.stat().st_size
    if sz == 0: empty += 1; continue
    t = f.read_text(encoding='utf-8')
    if not t.startswith('---'): nofm += 1; continue
    parts = t.split('---', 2)
    if len(parts) < 3: nofm += 1; continue
    import re
    if not re.search(r'^name:\s*\S', parts[1], re.M): noname += 1
    if not re.search(r'^description:\s*\S', parts[1], re.M): nodesc += 1
    ok += 1
print(f'Total={ok+empty+nofm} OK={ok} Empty={empty} NoFM={nofm} NoName={noname} NoDesc={nodesc}')
"

# 僵尸检测 (>30d 未更新)
find ~/.bookwormpro/skills/ -name "SKILL.md" -mtime +30 | wc -l
```

### Phase 5: Routing
```bash
# 金标准确率
cd routing/ && node accuracy.js

# 消歧规则数
python -c "import json; d=json.load(open('routing/disambiguation-rules.json')); print(d['_meta']['ruleCount'], 'rules', d['_meta']['version'])"

# 路由日志 (v6.6.1 源)
ls ~/.claude/debug/route-*.jsonl | tail -5
```

## 常见问题速查

| 问题 | 根因 | 修复 |
|------|------|------|
| Cron 全部 400 报错 | `model: null` → API 收到空 model | `cron/jobs.py` auto-resolve 已修复，新 job 无需手动补 |
| Cron 新建 job model=null | `cron/jobs.py:create_job` 不读 config | 已根治：auto-resolve from config.yaml default |
| MCP TIMEOUT | Python 冷启动 >8s | 30s 单独重测确认 |
| Agent 路由全回退 | skills-index-lite 无 keyword | 换用 skills-index.json (980KB) |
| Skills YAML 误报 | Windows CRLF → `read -r` 误判 | 用 Python 读 |
| 消歧规则不生效 | BM25 全 0 分 或 skill 不在 BM25 结果中 | Layer1→index fix, Layer2→submit 机制 |
| BWR trace 缺失 | v7.0.0 无独立路由追踪 | 已迁移：`routing/` 目录 + `bwr_hook.py` + bridge.js |

## 输出格式

```
══ 五柱体检 · YYYY-MM-DD ══

  Cron     🟢/🔴  N jobs / M errors
  MCP      🟢/🔴  N/N online
  Agent    🟢/🔴  烟雾测试 + 模块完整性
  Skills   🟢/🔴  N 合规 / M 僵尸
  Routing  🟢/🔴  准确率 X% / N 规则

  综合: 🟢/🟡/🔴
══════════════════════════════
```

## 反模式
- 只看 agent.log 不看 `~/.claude/debug/` (路由数据在 debug)
- 只 `grep` 不跑 live test (Agent 模块需要活体验证)
- 忽略 CRLF 导致的 YAML 扫描误报
- 忘记 cron jobs 默认 model=null 的 bug
