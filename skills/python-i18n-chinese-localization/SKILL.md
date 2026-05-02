---
name: python-i18n-chinese-localization
description: >
  Add Chinese (zh_CN) i18n to a Python CLI app using a self-contained
  .mo file translator. Works on Windows without system gettext locale
  dependencies. Covers: i18n module, .po→.mo compiler, string extraction
  script, and phased rollout across banner/commands/gateway modules.
category: devops
allowed-tools: "Read, Write, Edit, Bash, Glob, Grep"
---

# Python i18n 中文汉化流程

为 Python CLI 应用添加完整的中文 i18n 支持，使用自实现 .mo 翻译器（避免 Windows gettext 编码问题）。

## 何时使用
- 为现有 Python CLI/Agent 项目添加中文汉化
- 项目有 50+ 个用户可见字符串分布在多个模块
- 需要语言自动检测和 config 切换

## 核心架构

```
bwm_cli/i18n.py              ← 自包含翻译器（struct 解析 .mo，UTF-8）
locale/
  zh_CN/LC_MESSAGES/
    app.po / app.mo
scripts/
  compile_i18n.py            ← .po → .mo 编译
  extract_strings.py         ← 扫描 _() 调用抽取字符串
```

## Phase 1: i18n 核心 (i18n.py)

关键设计要点：
1. **不自带 gettext**：Windows 上 gettext 默认用 ASCII 解码 .mo 文件，遇到中文 0xe8 字节报错。用 `struct` 直接解析 .mo 二进制格式。
2. **语言检测顺序**：`config.yaml language` → `LANG` 环境变量 → 默认 `zh_CN`
3. **线程安全**：用 `threading.Lock()` 保护初始化

.mo 格式关键：header 28 字节，string_data_start = 28 + 2 * N * 8。必须在表偏移量中使用 `string_data_start + offset_in_data`，否则偏移量指向错误的二进制 header 数据。

## Phase 1b: .po → .mo 编译

正确编译 .mo 文件的结构：

```python
HEADER = 28
O_TABLE = HEADER                          # original strings table
T_TABLE = HEADER + N * 8                  # translation strings table
STRING_START = HEADER + 2 * N * 8         # string data begins

# 每对：(length, offset = STRING_START + position_in_data)
for off, length in orig_pos:
    result.extend(struct.pack("<I", length))
    result.extend(struct.pack("<I", STRING_START + off))
```

⚠️ **常见错误**：把 `len(data) + O + off` 当作偏移量 — 这会产生完全错误的指针。

## Phase 2: 逐文件应用 _()

方法和陷阱：

1. **`_` 变量名冲突**：Python 代码中常用 `_` 作 throwaway 变量。
   示例：`_, unavailable_toolsets = check_tool_availability()` — 这会 shadow i18n 的 `_` 函数。
   修复：改名为 `_avail` 或其他名称。

2. **f-string 中的 _()**：`_(f"...{var}...")` 不可行。用 `.format()`：
   ```python
   # 错误
   print(_(f"Model switched: {model}"))
   # 正确
   print(_("Model switched: {model}").format(model=model))
   ```

3. **Rich markup 内的 _()**：f-string 中用 `{_(...)}` 嵌入：
   ```python
   f"[dim]{_('个 active')}[/]"  # ✓ 可以
   ```

## Phase 3: 翻译文件维护

追加翻译：
```bash
python scripts/append_i18n.py   # 追加新条目到 .po
python scripts/compile_i18n.py  # 重新编译 .mo
```

抽取新字符串：
```bash
python scripts/extract_strings.py  # 生成 .pot 模板
```

## Windows 环境注意事项

| 问题 | 方案 |
|------|------|
| patch 工具 CRLF 失败 | 用 `sed -i` 或 Python `write_file` |
| heredoc `<<` 被当作后台进程 | 用 write_file 或 Python 脚本 |
| gettext ASCII 编码崩溃 | 自实现 .mo parser (见上) |
| `_` 是合法 Python 变量名 | grep 检查所有 `_, xxx = ` 赋值 |

## 产出物清单

| 文件 | 用途 |
|------|------|
| `bwm_cli/i18n.py` | 翻译引擎 |
| `locale/zh_CN/LC_MESSAGES/app.po` | 中文翻译源 |
| `locale/zh_CN/LC_MESSAGES/app.mo` | 编译后二进制 |
| `scripts/compile_i18n.py` | 编译工具 |
| `scripts/extract_strings.py` | 抽取工具 |
| `task_plan.md` | 实施计划（可选） |
