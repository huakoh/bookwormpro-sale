---
name: bookwormpro-system-health-check
description: >
  BookwormPRO 五柱系统全量体检 — Cron/MCP/Agent/Skills/Routing 逐项扫描，
  产出统一健康报告。触发词：全量体检、系统健康、五柱检查、health check。
version: 1.1.0
author: BookwormPRO (2026-05-01 实战验证)
tags: [health-check, audit, diagnostics, monitoring, bookwormpro]
category: system-tools
safety:
  level: low
  permissions: [read_file, terminal, search_files, session_search, delegate_task]
maturity: stable
cost_level: medium
---

# BookwormPRO 五柱系统全量体检

对 BookwormPRO 五大子系统执行逐项健康扫描，产出优先级分级的修复方案。

## 触发条件

- "全量体检" / "系统健康检查" / "五柱检查"
- "体检报告" / "检查所有系统"
- "最近一天/一周系统概况"

## 五柱定义

| 柱 | 检查对象 | 关键指标 |
|----|---------|---------|
| **Cron** | 定时任务 | 执行状态、model 配置、备份验证 |
| **MCP** | MCP 服务器 | 连通性、启动耗时、上次体检时间 |
| **Agent** | 子 Agent 系统 | spawn 测试、模块完整性、日志错误 |
| **Skills** | 技能生态 | YAML 合规、空文件、活跃度、类别分布 |
| **Routing** | 路由引擎 | 消歧规则、Hook 管线、凭证冲突、BWR 追踪 |

## 执行流程

### Phase 1: Cron 体检

```bash
# 列出所有 cron job
cronjob(action='list')

# 检查 jobs.json
cat ~/.bookwormpro/cron/jobs.json | python -c "import json,sys; d=json.load(sys.stdin); [print(f'{j[\"id\"][:12]} | model={j.get(\"model\")} | {j[\"last_status\"]} | {j[\"name\"]}') for j in d['jobs']]"

# 检查 model 字段 (null = BUG)
# 检查 last_error 字段获取错误详情
```

**关键陷阱**: cron job 的 `model: null` 会导致 DeepSeek API 400 错误 (空字符串 model)。修复方法：在 `jobs.json` 中补 `"model": "deepseek-v4-pro"` 并在 `cron/scheduler.py` 添加硬兜底。

### Phase 2: MCP 体检

```bash
# 运行全量探测 (11 个服务器, ~3 分钟)
cd ~ && node mcp-probe.js

# 读取结果
cat ~/mcp-probe-result.json

# 对 TIMEOUT 项单独 30s 重测
node -e "
const { spawn } = require('child_process');
// ... 30s timeout probe for single server
"
```

**关键陷阱**: Python 型 MCP 冷启动可达 9s+，8s 默认超时可能误报。需 30s 单独重测确认。

### Phase 3: Agent 体检

```python
# 烟雾测试 — 单 Agent spawn
delegate_task(goal='echo AGENT_SMOKE_TEST_OK', toolsets=['terminal'])

# 并发测试 — 2 Agent 并行
delegate_task(tasks=[
    {'goal': 'disk check', 'toolsets': ['terminal']},
    {'goal': 'module integrity', 'toolsets': ['terminal', 'file']}
])

# 检查 agent 错误日志
grep -c "delegate_task\|subagent\|orchestrator" errors.log
```

### Phase 4: Skills 体检

**脚本**: 扫描所有 SKILL.md 文件，检查 YAML 合规、空文件、大小分布、活跃度、类别分布。

**关键陷阱**: 
- Windows 上必须用 `python` 不是 `python3` (Windows Store 存根返回 exit 49)
- CRLF 行尾可能导致 YAML 检测误报
- 技能 SKILL.md 路径结构: `skills/{category}/{skill-name}/SKILL.md`
- `~/.claude/skills/` (v6.6.1) 和 `~/.bookwormpro/skills/` (v7.0.0) 是两套独立技能库

```python
# 核心审计脚本
from pathlib import Path
import re

skills_dir = Path.home() / '.bookwormpro' / 'skills'
ok = nofm = noname = nodesc = emptyf = 0

for skf in skills_dir.rglob('SKILL.md'):
    size = skf.stat().st_size
    if size == 0: emptyf += 1; continue
    text = skf.read_text(encoding='utf-8', errors='replace')
    parts = text.split('---', 2)
    if len(parts) < 3: nofm += 1; continue
    fm = parts[1]
    if not re.search(r'^name:\s*\S', fm, re.MULTILINE): noname += 1
    if not re.search(r'^description:\s*\S', fm, re.MULTILINE): nodesc += 1
    ok += 1
```

### Phase 5: Routing 体检

```bash
# 消歧规则
cat ~/.claude/scripts/disambiguation-rules.json | python -c "import json,sys; d=json.load(sys.stdin); print(f'Rules: {d[\"_meta\"][\"ruleCount\"]}')"

# Hook 健康
grep -c "hook failed" agent.log      # 排除 pytest 临时目录的测试噪声
grep -c "hook registered" agent.log

# 凭证冲突
grep "RELAY_AS_OPENROUTER\|skipping env" agent.log | wc -l

# BWR 追踪密度
grep -c "BWR:" agent.log    # 应为 >0，为 0 表示追踪未发射
```

## 输出格式

```markdown
## 五柱体检报告 · YYYY-MM-DD

### 一、Cron
| Job | 上次运行 | 状态 |
|-----|---------|------|

### 二、MCP
总计: N | OK: N | FAIL: N

### 三、Agent
子 Agent spawn: 通过/失败 | 并发: 通过/失败

### 四、Skills
总文件数 / 空文件 / 缺YAML / 缺name / 合规率

### 五、Routing
消歧规则 / Hook健康 / 凭证冲突 / BWR追踪

### 综合评估
══ 五柱 ══
Cron    🟢/🟡/🔴
MCP     🟢/🟡/🔴
Agent   🟢/🟡/🔴
Skills  🟢/🟡/🔴
Routing 🟢/🟡/🔴
```

## 常见问题速查

| 症状 | 根因 | 修复 |
|------|------|------|
| cron 400: "but you passed ." | model=null, 空字符串传 API | jobs.json 补 `"model":"deepseek-v4-pro"` |
| cron 创建后即 model=null | `cronjob create` 不继承 config.yaml 默认值 | 创建后立即 Python 脚本批量补 model |
| MCP TIMEOUT (8.2s) | Python 冷启动慢 | 30s 单独重测 |
| hook failed: command not found | pytest 临时目录测试 | 忽略, 非生产 |
| 大量 credential pool skipping | OpenRouter 双入口 | `bookworm auth remove openrouter` |
| BWR trace = 0 in agent.log | 路由追踪注入 system prompt 非日志 | 检查 `~/.claude/debug/route-*.jsonl` |
| Skills 数 (208) ≠ SKILL.md 数 (258) | gstack `.agents/skills/` 重复副本 | 无功能影响, 已过滤 |

### Cron model=null 根治方案

两层防御:
1. **立即止血**: `jobs.json` 每个 job 补 `"model": "deepseek-v4-pro"`
2. **代码根治**: `cron/scheduler.py` 追加硬兜底:

```python
# 在 config.yaml 加载的 except 块后追加
if not model:
    model = "deepseek-v4-pro"
    logger.warning("Job '%s': model was empty after resolution, hard-fallback to %s", job_id, model)
```

### 多份代码副本合并流程

当 BookwormPRO 存在多份副本时 (如 main/projects/skills_PR):
1. 分析差异: `diff` 行数 + Python 脚本对比所有 .py 文件大小
2. 合并策略: 取每份副本中较新的文件, 保留 main 的优势 (更多文件/今日修复)
3. 备份: 每个被覆盖文件存 `*.bak-merge`
4. 验证: 检查 scheduler.py hard-fallback 保留 + Python 语法检查
5. 归档: 旧目录 `mv` 为 `.archived-YYYYMMDD`

### BWR 路由引擎迁移 (v6.6.1 → v7.0.0)

从 `~/.claude/scripts/` 复制到 `BookwormPRO/routing/`:
- 核心: `route-engine.js`, `intent-classifier.js`, `bwr-builder.js`, `route-state.js`
- 辅助: `disambiguation-rules.json` (93条), `tfidf-engine.js`, `semantic-scorer.js` 等
- Lib: `root.js` (重写→`~/.bookwormpro/`), `safe-append.js`
- 数据: 复制 `skills-index-lite.json` 到 `~/.bookwormpro/`
- 适配: `route-engine.js` 中 `SCRIPTS_DIR = __dirname`; `root.js` 返回 runtime 目录
- 验证: `node accuracy.js` 金标集 170 条, 与 v6.6.1 对比准确率

## 环境注意事项

- **Windows Python**: `python` ✓ / `python3` ✗ — `python3` 是 Microsoft Store 存根，返回 exit code 49 且无输出。必须显式用 `python`。
- **CRLF 陷阱**: 多数 `.py/.md` 文件用 CRLF 行尾。`patch` 工具的 post-write verification 在 CRLF 文件上经常失败（字节数不匹配）。**在 Windows 上编辑文件时，优先用 Python 脚本而非 `patch` 工具**。
- **Python 脚本模板**（替代 patch）:
  ```python
  python -c "
  path = r'C:\path\to\file.py'
  with open(path, 'r', encoding='utf-8') as f:
      content = f.read()
  content = content.replace('old', 'new')
  with open(path, 'w', encoding='utf-8') as f:
      f.write(content)
  "
  ```
- **行号定位**: 用 `grep -n` 先找行号，再用 `read_file` 确认上下文后再改。CRLF 文件行号可能与 grep 输出偏移。
- `~/.claude/` = v6.6.1 (独立, 不可修改, 不可移动)
- `~/.bookwormpro/` = 共享运行时 (config/skills/logs/cron)
- `C:\Users\BOOKWORMPRO_USER\BookwormPRO\` = v7.0.0 唯一代码目录
- **python3 静默失败**: Windows Store python3.exe 返回 exit 49, stdout/stderr 完全为空。症状: 脚本看起来"卡住"但实际已失败。必须 `which python3 && python3 --version` 确认真实 Python。
