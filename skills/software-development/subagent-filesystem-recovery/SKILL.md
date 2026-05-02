---
name: subagent-filesystem-recovery
description: When a subagent (delegate_task) times out, check the filesystem for partial results before assuming failure. Subagents often write files before the timeout kills them. Use this to recover work and avoid redundant effort.
version: 1.0.0
author: BookwormPRO
tags: [subagent, delegate_task, timeout, recovery, filesystem]
---

# Subagent Filesystem Recovery

当 `delegate_task` 子代理超时（exit_reason: timeout）时，不要假设它什么都没做。子代理在 600s 超时前可能已经写入了大量文件。

## 触发条件

- `delegate_task` 返回 `status: timeout` 或 `exit_reason: timeout`
- 任务涉及文件写入（create/modify files）

## 恢复流程

### 1. 检查预期输出文件是否存在

```bash
# 根据子代理的 goal/context 推断预期输出路径
ls -la <expected_output_path>
wc -l <expected_output_path>  # 检查完整性
```

### 2. 验证文件内容

```python
import py_compile
py_compile.compile(r'path/to/file.py', doraise=True)
print('syntax OK')
```

### 3. 检查是否被并行修改

子代理可能修改了同一个文件（如 main.py），其他子代理的并行写入会导致行数膨胀。检查方式：

```bash
wc -l <file>  # 与预期行数对比
git diff --stat <file>  # 如果有 git，查看变更量
```

### 4. 集成到父代理流程

确认文件完整后，直接在父代理中继续：
- 如果是新增模块：语法检查 → 导入测试
- 如果是修改现有文件：搜索关键函数确认变更正确 → 继续集成

## 实际案例

本次会话中，一个 orchestrator 子代理被委托创建 `audit.py` 和 `memory_temporal.py`：

```
Subagent result: status=timeout, api_calls=19, duration=600.89s
```

**恢复结果：**
- `bwm_cli/audit.py` → 377 行，语法 OK
- `agent/memory_temporal.py` → 892 行，语法 OK  
- `bwm_cli/backup.py` → 新增 190 行三层备份函数
- `bwm_cli/main.py` → 从 9191 行膨胀到 18393 行（含 backup --git/--push/--full 标志）

**关键教训：** 子代理 600s 超时前已完成 19 次 API 调用，所有 4 个文件均已写入。检查文件系统比重新执行快得多。

## 注意事项

- 子代理写入的文件可能包含 CRLF 混合换行符（Windows Git Bash）
- 验证修改时注意行数是否合理（main.py 膨胀到 2x 说明可能有重复内容或格式问题）
- 如果文件被多个子代理同时修改，优先检查最新版本是否语法正确
- **`.po` 文件特殊处理**：子代理经常超时在翻译提取阶段。`git diff --stat` 查看 `.po` 的增量行数，再用 `grep -c "^msgid"` 确认条目数。即使超时，部分翻译条目通常已写入且有效

## CRLF 修复脚本模式 (Windows)

子代理在 Windows CRLF 文件上经常超时、产出部分结果但仍需手动修正。**不要在父代理中用 patch 工具逐行修改 CRLF 文件**——会因换行符不匹配而失败。用以下模式：

### 模式：创建修复脚本 → terminal 执行

```python
# 1. 用 write_file 创建修复脚本（Python 源码用 LF 没问题）
write_file(path="_fix_xxx.py", content="""
import os
path = r"C:\\Users\\BOOKWORMPRO_USER\\BookwormPRO\\target_file.py"
with open(path, 'r', newline='') as f:  # newline='' 保留原始换行符
    content = f.read()

# 尝试 \\r\\n 和 \\n 两种模式（Win Git Bash 通常是 \\r\\n）
old = "except Exception:\\r\\n    return \\"\\""
new = "except Exception:\\r\\n    logger.debug(\\"failed\\", exc_info=True)\\r\\n    return \\"\\""
c = content.count(old)
if c:
    content = content.replace(old, new)
else:
    # fallback: 尝试 LF
    old_lf = old.replace('\\\\r\\\\n', '\\\\n')
    new_lf = new.replace('\\\\r\\\\n', '\\\\n')
    c = content.count(old_lf)
    if c:
        content = content.replace(old_lf, new_lf)

with open(path, 'w', newline='') as f:
    f.write(content)
print(f"Fixed {c} occurrence(s)")
""")

# 2. 执行修复脚本
terminal("python _fix_xxx.py")

# 3. 清理
terminal("rm _fix_xxx.py")
```

### 为什么这个模式有效

- `newline=''` 保留原始 `\r\n`，避免 `write()` 时意外转换
- 先尝试 `\r\n` (Win Git Bash 默认), 回退 `\n`
- 脚本运行在 `terminal` 中而非子代理中，不受 delegate timeout 限制
- 语法检查 (`py_compile`) 验证修改后文件仍然有效

## 实战案例 (2026-05-01 审计批量修复)

本次审计发现 17 个问题（6 P1 + 11 P2），通过 3 路并行 delegate 修复。全部 3 个子代理 600s 超时，但实际产出：

- `agent/text_filter.py` — 143行新模块，语法 OK
- `model_tools.py` — 4/5 处 hook 异常添加了 logger.debug
- `cli.py` — 6处 init/cleanup 异常全部添加 logger.debug
- `tui_gateway/server.py` — 2处 shell=True 已移除
- `bwm_cli/memory_setup.py` — shell=True 已移除
- `tools/environments/docker.py` — 2处 shell=True 已移除
- `tools/file_tools.py` — 并发锁绕过 → 返回错误
- `agent/memory_integration.py` — 字符串 → MemoryLayer 枚举
- `agent/google_oauth.py` + `bwm_cli/auth.py` — 安全注释已添加
- `qwen3_coder_parser.py` + `glm45_parser.py` — SECURITY 注释通过修复脚本补加
- `tools/terminal_tool.py` — 密码线程异常通过修复脚本补加

**关键：** 超时后先用 `git status --short` 快速查看所有修改，再用 `py_compile` 批量语法检查，最后用修复脚本补全遗漏项。整个流程耗时约 2 次 terminal 调用，而非重新执行 3 个 600s 的 delegate。
