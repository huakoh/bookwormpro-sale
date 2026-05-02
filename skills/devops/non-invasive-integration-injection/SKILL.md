---
name: non-invasive-integration-injection
description: 非侵入式系统集成模式 — 创建轻量 *_integration.py 包装模块而非直接修改核心文件，通过单行 import 注入功能，失败时自动降级不影响主流程
version: 1.0.0
author: BookwormPRO
tags: [integration, pattern, system-extension, architecture]
---

# 非侵入式集成注入模式

当需要为现有大型系统（如 AIAgent）添加新功能时，避免直接修改核心文件。

## 问题

直接修改 `run_agent.py`(12K+行) 或 `prompt_builder.py` 会：
- 增加合并冲突风险
- 难以回滚
- 使核心文件膨胀
- 测试隔离困难

## 方案：Wrapper 集成模块

创建轻量 `*_integration.py` 模块，仅需在核心文件中添加一行 import。

### 模板

```python
"""
<feature>_integration.py — 非侵入式接入 <核心系统>

Usage (在核心文件中添加):
    try:
        from agent.<feature>_integration import <hook_function>
    except ImportError:
        <hook_function> = lambda *a, **kw: None
"""

import logging
logger = logging.getLogger(__name__)

_ENABLED = True  # 可通过配置关闭

def hook_function(*args, **kwargs):
    """执行集成功能，失败时静默降级。"""
    if not _ENABLED:
        return
    try:
        # 实际逻辑
        _do_work(*args, **kwargs)
    except Exception:
        logger.debug("集成钩子失败，不影响主流程", exc_info=True)
```

### 注入点选择

在核心文件中找到合适的钩子位置：

| 系统 | 注入位置 | 示例 |
|------|---------|------|
| Agent 工具调用后 | `handle_function_call()` 返回后 | audit_tool_call() |
| 系统提示构建 | `sections.append()` 循环 | get_temporal_memory_prompt() |
| 会话开始/结束 | `run_conversation()` 首尾 | audit_session_event() |
| 文件写入后 | `write_file()` / `patch()` 调用后 | audit_file_modify() |

### 安全原则

1. **try/except 包裹所有调用**：集成失败绝不阻断主流程
2. **ImportError 降级**：import 失败时用一个空 lambda 替代
3. **可配置开关**：提供 `_ENABLED` 标志位
4. **日志隔离**：使用 `logger.debug()` 避免噪音

## 实战案例

### 案例 1：审计集成 (audit_integration.py)

```python
# run_agent.py 中仅添加：
try:
    from agent.audit_integration import audit_tool_call, audit_session_event
except ImportError:
    audit_tool_call = audit_session_event = lambda *a, **kw: None

# 在工具调用后注入：
audit_tool_call(self.session_id, function_name, function_args, result=function_result)
```

### 案例 2：记忆集成 (memory_integration.py)

```python
# prompt_builder.py 中仅添加：
try:
    from agent.memory_integration import get_temporal_memory_prompt
except ImportError:
    get_temporal_memory_prompt = lambda: ""

# 在系统提示构建时注入：
temporal_prompt = get_temporal_memory_prompt()
if temporal_prompt:
    sections.append(temporal_prompt)
```

## 适用场景

- 为 Agent 添加审计/日志/监控
- 扩展记忆系统
- 注入自定义系统提示
- 添加遥测/使用统计
- 实验性功能（可随时关闭）

## 反模式

- 不要在集成模块中 import 核心文件（循环依赖）
- 不要修改核心文件的数据结构
- 不要阻塞核心流程（所有操作异步/快速返回）
- 不要在集成模块中抛出未捕获异常

## 陷阱记录（实战踩坑）

### prompt_builder.py 字符串注入事故

向 Python 多行字符串常量追加内容时，极易产生 `unterminated string literal`。
症状: `py_compile` 报 SyntaxError at line 189。
原因: 注入的 `"\n"` 未正确闭合引号，导致后续字符串被解释为非法语法。
教训: 注入后立即 `py_compile.compile(path, doraise=True)` 验证。

### Windows CRLF

`patch` 工具在 Windows Git Bash 始终失败，用 `write_file` 一次性重写。

### 陷阱 1：Python 字符串注入破坏语法
**场景**：向 `prompt_builder.py` 的 `MEMORY_GUIDANCE = (...)` 多行字符串常量末尾注入新行时，
新行的 `"..."` 如果不小心产生 `"\)` 之后跟独立空行 `"` 的断句，会导致 `unterminated string literal`。
**教训**：注入到 Python 多行字符串常量时，用 `\n"` 正确结束上一行，确保新行是完整字面量 `"text..."`
**修复**：必须 `py_compile.compile()` 验证后再提交

### 陷阱 2：Windows CRLF 导致文件写入验证失败
**场景**：`patch` 工具在 Windows Git Bash 下对任何 .py 文件写入后读取的字符数不一致（差 80-100 chars），
因为文件中的 `\r\n` 被部分转换为 `\n`。
**应对**：复杂编辑先用 `read_file`（不带 offset/limit）读全文，再用 Python `write_file` 写入完整内容。

### 陷阱 3：Description YAML 多行格式不匹配
**场景**：尝试用简单正则 `description:\s*\"(.+?)\"` 提取 `description: >\n  ...` 格式的多行描述时匹配失败。
**应对**：YAML folded block scalar (`>`) 需要特殊处理，或用 `skill_view(name)` API 而非正则。
