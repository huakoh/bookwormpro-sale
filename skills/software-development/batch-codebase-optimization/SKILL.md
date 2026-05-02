---
name: batch-codebase-optimization
description: 大规模代码库优化工作流 — 当需要对现有大项目进行 5+ 文件的多模块增强时使用。覆盖规划、并行执行、subagent 超时处理、patch 工具 CRLF 退避、文件冲突协调、批量验证。
version: 1.0.0
author: BookwormPRO
license: MIT
metadata:
  bookworm:
    tags: [batch, optimization, codebase, multi-module, workflow]
---

# 批量代码库优化工作流

适用于需要跨多个文件进行 5+ 模块增强的大项目场景（如功能补齐、系统升级）。

## 触发条件

- 有 5+ 个需要创建或修改的文件/模块
- 目标是一个大型现有代码库（非从零开始）
- 涉及 Python + CLI 集成（argparse 注册等）
- Windows + Git Bash 环境

## 工作流程

### 1. 规划阶段

```python
# 输出编号优先级清单
todo = [
    {"content": "P0: 核心模块A — 最大缺口", "id": "1", "status": "pending"},
    {"content": "P1: 辅助模块B", "id": "2", "status": "pending"},
    # ... 等等
]
```

- 按缺口严重性排序（非开发便利性）
- 标注哪些可并行（无依赖）vs 串行（需等待前序）

### 2. 并行执行策略

**独立模块 → subagent 并行**：
```python
delegate_task(
    goal="Create module X at path/to/x.py with features A,B,C",
    context="Follow existing code patterns from path/to/existing.py",
    role="orchestrator",  # 如果单个 subagent 可能超时
    toolsets=["terminal", "file", "web"]
)
```

**CLI 集成 → 亲自做**：
- argparse 注册在 main.py 中，避免并发写入冲突
- 等 subagent 完成模块文件后，再修改 CLI 入口

### 3. Subagent 超时处理

Subagent 可能在写文件后超时。关键检查顺序：

```python
# 1. 检查目标文件是否存在
ls -la <target_file>

# 2. 如果存在 → 读取验证完整性
read_file(target_file)

# 3. 如果内容完整 → 直接使用，无需重写
# 4. 如果内容不完整 → 用 write_file 补全
```

> **陷阱**：不要在未知文件状态下直接 `write_file`，会覆盖 subagent 已写入的有效内容。先 `read_file` 确认。

### 4. Patch 工具 CRLF 退避

Windows Git Bash 下 `patch` 工具 100% 因 CRLF 行末不匹配而失败。退避优先级：

| 情况 | 解决方案 |
|------|----------|
| 小文件（<500行） | `read_file` → `write_file` 全量重写 |
| 大文件局部修改 | `terminal` + Python 脚本做字符串替换 |
| 超大文件（>5000行） | `terminal` + Python `str.replace()` 精确替换 |

**Python 字符串替换模板**：
```python
python -c "
path = r'<absolute_path>'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old = 'exact_old_string_with_crlf'  # 从 read_file 获取精确内容
new = 'replacement_string'

if old in content:
    content = content.replace(old, new, 1)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('OK')
else:
    # 搜索定位实际字符串
    idx = content.find('partial_marker')
    print(repr(content[idx:idx+200]))
"
```

### 5. 验证阶段

每个模块用内联 Python 脚本独立验证，不依赖 CLI 能运行：

```python
python -c "
import sys; sys.path.insert(0, r'<project_root>')
from module import Class, function

# 1. 初始化验证
obj = Class()
print('Init OK')

# 2. 写入测试
obj.do_something(test_data)
print('Write OK')

# 3. 查询验证
result = obj.query()
assert result, 'Query returned empty'
print('Query OK')
"
```

### 6. 语法检查收尾

```bash
python -c "import py_compile; py_compile.compile(r'<file>.py', doraise=True)"
```

## 常见陷阱

1. **main.py 膨胀**：subagent 可能给 main.py 加大量空行/重复代码 → 修改前先确认行号
2. **UTF-8 BOM**：Windows Python 写文件可能加 BOM → 读时用 `encoding='utf-8'` 不加 `-sig`
3. **行末混合**：subagent 可能写 `\n` 而你读到的原始文件是 `\r\n` → Python `replace` 用 `repr()` 确认
4. **属性缺失**：构造 argparse.Namespace 时要带齐所有被访问的属性
