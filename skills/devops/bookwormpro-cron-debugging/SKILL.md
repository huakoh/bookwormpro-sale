---
name: bookwormpro-cron-debugging
description: >
  BookwormPRO cron 任务排障工作流。当定时任务报 error、未正常执行、或需要排查
  cron 调度问题时使用。覆盖日志定位、根因分析、修复模板和验证流程。
  触发词: cron 报错, cron 失败, 定时任务排查, cron job error, 备份未执行。
maturity: stable
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
---

# BookwormPRO Cron 排障工作流

## 数据源定位

```
任务配置: ~/.bookwormpro/cron/jobs.json        (schema: jobs[], model, provider, schedule, last_error)
系统配置: ~/.bookwormpro/config.yaml            (model.provider / model.default)
错误日志: ~/.bookwormpro/logs/errors.log        (搜索 [cron_JOBID] 前缀)
Agent日志: ~/.bookwormpro/logs/agent.log        (搜索 cron_batch 相关)
```

## 排障 Step-by-Step

### Step 1 — 查看任务状态

```bash
# 方式一: cronjob list (如果有工具)
# 方式二: 直接读 jobs.json
python -c "
import json
with open(r'C:\Users\BOOKWORMPRO_USER\.bookwormpro\cron\jobs.json','r',encoding='utf-8') as f:
    d = json.load(f)
for j in d['jobs']:
    s = j.get('last_status','-')
    e = (j.get('last_error','') or '')[:80]
    print(f'{j[\"id\"][:12]} | {s:8s} | {j[\"name\"]} | {e}')
"
```

### Step 2 — 查错误日志找根因

```bash
# 搜索 cron 相关错误 (带 job_id 前缀)
grep -n "cron_\|\[cron" ~/.bookwormpro/logs/errors.log | tail -20

# 按时间窗口搜索
grep "2026-05-01T09" ~/.bookwormpro/logs/errors.log | grep -i "cron\|error"
```

**关键判断**: 如果错误消息包含 `but you passed .` (DeepSeek) 或类似空 model 名错误，
直接跳到 Step 4 修复。

### Step 3 — 识别根因类型

| 错误特征 | 根因 | 修复 |
|---------|------|------|
| `but you passed .` (DeepSeek) | model 为空字符串 | 补 model 字段 (Step 4) |
| `Agent completed but produced empty response` | 模型调用失败后被调度器吞掉 | 查 errors.log 找真实错误 |
| `Git Bash not found` | cron 环境无 Git Bash PATH | 确认 Windows 环境下 cron 运行依赖 |
| `PermissionDeniedError: 403` | OpenRouter token 无权访问某模型 | 换模型或检查 API key |
| `Non-retryable client error` | 不可重试的 API 错误 | 读具体 message |
| `The supported API model names are X or Y, but you passed .` | **model 为 null/空字符串 → API 拒绝** | Step 4 |

### Step 3a — 深度根因：model=null → 空字符串 (2026-05-01 实战验证)

**完整因果链**:
```
jobs.json "model": null
  → scheduler.py line 838: model = job.get("model") or os.getenv("...") or None
    → config.yaml 加载可能失败 (yaml 模块/路径)
      → AIAgent(model=None) → API 调用时 model="" 
        → DeepSeek: "but you passed ." (400)
```

**关键证据链**:
1. errors.log 中同秒双报错: `[cron_JOBID1]` 和 `[cron_JOBID2]` 同时 400
2. agent.log 中辅助客户端正常: `auxiliary_client → deepseek-v4-pro [OK]`
3. **辅助客户端和主请求 model 解析路径不同** — 不要被辅助客户端日志误导
4. `last_error` 字段是调度器二次归纳: `"Agent completed but produced empty response"` 掩盖了真实 400 错误

**深层根因**: `cron/scheduler.py` 中 config.yaml 加载包裹在 try-except 中，如果 `import yaml` 失败或文件读取失败，model 保持 None/空字符串一路传到 AIAgent。

### Step 4 — 修复 model=null 导致空字符串

**症状**: jobs.json 中 `"model": null`，cron 调度器未从 config.yaml 继承默认值。

**安全修复** (Python 脚本，带备份):

```bash
python -c "
import json, shutil

path = r'C:\Users\BOOKWORMPRO_USER\.bookwormpro\cron\jobs.json'
shutil.copy2(path, path + '.bak')   # 先备份

with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)

default_model = 'deepseek-v4-pro'   # 或从 config.yaml 读取

for job in data['jobs']:
    if job.get('model') is None:
        job['model'] = default_model
        print(f'  [FIXED] {job[\"id\"][:12]} {job[\"name\"]}')

with open(path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

# verify
with open(path, 'r', encoding='utf-8') as f:
    verify = json.load(f)
for job in verify['jobs']:
    assert job.get('model') == default_model, f'FAIL: {job[\"id\"]}'
print('OK: all jobs patched')
"
```

### Step 5 — 验证修复

```bash
# 确认 model 字段已写入
python -c "
import json
with open(r'C:\Users\BOOKWORMPRO_USER\.bookwormpro\cron\jobs.json','r') as f:
    d = json.load(f)
for j in d['jobs']:
    print(f'{j[\"id\"][:12]} | model={j.get(\"model\")} | {j[\"name\"]}')
"
```

## 陷阱 (Pitfalls)

1. **patch 工具有时无法正确写入 JSON** (Windows CRLF/encoding 冲突) → 直接用 Python 脚本重写
2. **errors.log 中 `last_error` 是二次归纳**，真实根因在 errors.log 的同时间戳 ERROR 行
3. **辅助客户端和主请求 model 解析路径不同**，不要被辅助客户端日志(如 `auxiliary_client → deepseek-v4-pro [OK]`)误导以为 model 配置正常
4. **修改 jobs.json 后 cron 调度器可能缓存旧配置** → 不确定是否需要重启时，等下一个调度窗口验证

## 已知 Bug 模式

**Bug**: cron 调度器在 `jobs.json` 中 `model: null` 时，不从 `config.yaml` 的 `model.default` 继承，导致 AIAgent 收到空字符串 model。

**影响范围**: 所有未显式指定 model 的 cron job (新建 job 默认 model=null)。

**临时修复**: 每个 job 显式写入 `"model": "deepseek-v4-pro"`。

**永久修复** (代码层): `cron/scheduler.py` 中在 config.yaml 加载后增加硬兜底:

```python
# 在 except Exception 块之后，Apply IPv4 preference 之前插入:
# Hard fallback: never pass empty model to AIAgent (prevents API 400)
if not model:
    model = "deepseek-v4-pro"
    logger.warning("Job '%s': model was empty after resolution, hard-fallback to %s", job_id, model)
```

**防御加固建议** (run_agent.py): `AIAgent.__init__` 中 model 参数默认值 `""` 过于宽松。建议拒绝空字符串并 fallback 到 config 默认值。但 AIAgent 的 model 解析链复杂 (normalize/runtime/fallback 多路径)，仅加 warning 日志即可，真正修复在 scheduler 层。

## 备份验证模式 (2026-05-01 新增)

cron 备份任务常见缺陷：只执行不验证。**备份无验证 = 无备份。**

### 验证步骤模板

在备份 cron job 的 prompt 末尾追加：

```
备份完成后，验证备份文件完整性：
1. 列出最新备份: ls -t ~/.bookwormpro/backups/*.zip | head -1
2. 检查文件大小: ls -lh (上面找到的文件) 确认 > 10KB
3. 抽查内容: unzip -l (上面找到的文件) | tail -5 确认有文件列表
4. 三步都通过输出 '备份验证通过'，任一步失败输出 '备份验证失败'
```
