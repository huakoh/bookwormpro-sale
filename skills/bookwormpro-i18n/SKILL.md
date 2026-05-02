---
name: bookwormpro-i18n
description: BookwormPRO 国际化(i18n)汉化维护。当用户需要对 BookwormPRO 进行汉化、添加翻译、修复中文显示、编译 .po 文件、扫描新字符串时使用。
category: devops
---

# BookwormPRO i18n 汉化技能

## 触发条件
- 用户要求"汉化"、"翻译成中文"、"加翻译"、"i18n"
- 用户要求编译 .po 文件、扫描新字符串
- 用户报告中文显示问题

## 关键文件

| 文件 | 作用 |
|------|------|
| `bwm_cli/i18n.py` | 翻译引擎，导入 `_()` 函数 |
| `locale/zh_CN/LC_MESSAGES/bookwormpro.po` | 中文翻译文件（手动编辑） |
| `locale/zh_CN/LC_MESSAGES/bookwormpro.mo` | 编译后的二进制 |
| `scripts/compile_i18n.py` | .po → .mo 编译器 |
| `scripts/extract_strings.py` | 扫描源码提取 `_()` 字符串 |
| `locale/README.md` | 维护文档 |

## 工作流程

### 在源码中添加翻译
```python
from bwm_cli.i18n import _
print(_("Original English text"))
```

### 添加翻译条目
编辑 `locale/zh_CN/LC_MESSAGES/bookwormpro.po`，追加：
```po
msgid "Original English text"
msgstr "中文翻译"
```

### 编译
```bash
cd BookwormPRO/
python scripts/compile_i18n.py
```

### 验证
```python
from bwm_cli.i18n import _, setup_i18n
setup_i18n('zh_CN', force=True)
assert _("Original English text") == "中文翻译"
```

## 架构要点

1. **自实现翻译器**（不用 Python gettext），UTF-8 原生解析 .mo 文件
2. **语言检测顺序**：`config.yaml language` → `LANG` 环境变量 → 默认 `zh_CN`
3. **导入方式**：`from bwm_cli.i18n import _` 一行即可
4. **f-string 处理**：用 `.format()` 代替，`_("Stopped {n}").format(n=count)`

## 常见陷阱与解决方案

### 1. Python gettext 在 Windows 上不支持中文
Python 标准库 `gettext` 依赖系统 locale，Windows 默认 locale 为 ASCII/GBK，加载含中文的 .mo 文件时报 `'ascii' codec can't decode byte 0xe8`。**使用自实现翻译器**（`bwm_cli/i18n.py` 的 `_Translator` 类），直接 UTF-8 解析 .mo 二进制。

### 2. Windows 工具链注意事项
- **patch 工具**：CRLF vs LF 导致验证失败 → 用 `sed -i` 或 `write_file`
- **sed 换行**：`sed 's/old/new\\nnew2/'` 不生效 → 用 `sed -i 'Na text'` 在某行后插入
- **终端 heredoc**：`<< 'EOF'` 被 shell 解释为后台 `&` → 写到 `.py` 脚本文件再执行
- **git checkout 陷阱**：`git checkout <file>` 在 Windows 将 LF→CRLF，导致后续 `content.replace()` 全部失败 → 用二进制 bytes 替换显式匹配 `\r\n`
- **Rich markup 对齐**：`str.ljust()/rjust()` 不适用含 Rich markup 的字符串（markup 增加长度但不占显示宽度）→ 用独立空格前缀字符串 `" " * n`

### 3. `_` 变量名冲突
源码中常用 `_, unused = func()` 丢弃返回值。导入 `from bwm_cli.i18n import _` 后，如果文件内存在 `_` 作为局部变量，会遮蔽翻译函数。**修复**：将丢弃变量重命名如 `_avail, unavailable = func()`。

### 4. f-string 内嵌 `_()`
```python
# 错误：f"{_(key)}" — 某些 Python 版本解析异常
# 正确：先翻译再插入，或改用 .format()
msg = _("Stopped {count} processes.").format(count=n)
print(_("Model switched: {model}").format(model=name))
```

### 5. 编译 .mo 的偏移量陷阱
.mo 格式：`[28B header][N*8B 原文表][N*8B 译文表][字符串数据]`。偏移量必须 = `STRING_START + off_in_data`（`STRING_START = 28 + 2*N*8`），不是 `len(data) + 表偏移 + off`。

### 6. 测试断言需中英文双向兼容
命令描述/类别名经 `_()` 包装后，测试中硬编码英文会失败。
```python
# 修复前
assert cmd.category == "Session"
# 修复后（接受双语）
assert cmd.category in ("Session", "会话")
```

### 7. config.yaml 语言切换
顶层键 `language: en` 或 `language: zh_CN`。注意不要跟 `tts.xai.language` 混淆（那是 TTS 语音语言，不是 UI 语言）。`_detect_language()` 读取 `load_cli_config().get("language")`，为空时回退到 `LANG` 环境变量 → `zh_CN`。

### 8. 用 Python 写含转义序列的 .py 源文件
当程序中用 `f.write(content)` 写入含 `"\\n"` 的 Python 源码时，Python 字符串 `"\\n"` 会变成换行符 `0x0A` 写入文件，导致源码中出现跨行字符串字面量（`SyntaxError: unterminated string literal`）。**症状**：文件行显示 `left_content = "` 然后下一行 `".join(left_lines)`。

**修复**：用二进制替换字节 `bytes([0x22, 0x0a, 0x22])`（引号+换行+引号）→ `bytes([0x22, 0x5c, 0x6e, 0x22])`（引号+反斜杠+n+引号）。或用 `repr()` 生成正确的转义序列。

### 9. Rich markup 字符串长度 ≠ 显示宽度
在终端 banner 中用 `str.ljust(RIGHT_W)` 或 `str.rjust()` 居中时，Rich markup 标签（如 `[bold cyan]...[/]`）计入字符串长度但不算显示宽度，导致居中偏移。 **解决**：将纯空格 padding 字符串与 Rich markup 拼接在 f-string 外部：`f"{' ' * pad}[dim]╭...╮[/]"`。

### 10. Windows 下 Python text-mode 文件编辑导致 CRLF 损坏

用 `open(path, 'r', encoding='utf-8')` 读取 → `content.replace()` → `open(path, 'w', newline='')` 写入的流程在 Windows 下会破坏文件：
- text mode 读取将 `\r\n` → `\n`
- `content.replace()` 在 LF-only 内容上操作
- `newline=''` 写入不添加 CR，导致原 `\r\n` 全部变成 `\n`
- 症状：文件行数爆炸（654→4497），每次写入都插入多余空行

**修复**：用二进制模式操作，精确匹配 CRLF 字节序列：
```python
with open(path, 'rb') as f:
    data = f.read()
data = data.replace(b'target bytes with \\r\\n', b'replacement bytes with \\r\\n')
with open(path, 'wb') as f:
    f.write(data)
```
对于含中文的替换，用十六进制字节构建模式：
```python
old = b'_cprint(f\"  [\\xe6\\x88\\x90\\xe5\\x8a\\x9f] Model switched: {result.new_model}\")'
new = b'_cprint(\"  \" + _(\"[\\xe6\\x88\\x90\\xe5\\x8a\\x9f] Model switched: {model}\").format(model=result.new_model))'
```

### 11. 自动导入注入不能插入括号内的多行导入

`from bwm_cli.timeouts import (\n    get_provider_request_timeout,\n    ...\n)` — 在此括号块内插入 `from bwm_cli.i18n import _` 会产生 `SyntaxError: invalid syntax`。

**修复**：检测导入行的开括号，跳过直至找到闭括号 `)`，然后在其后插入。

### 12. f-string + 自动翻译包装函数的双层 `_()` 模式

当 `_cprint()` 等包装函数内部已调用 `_(text)`，而传入的又是 f-string 时：
```python
_cprint(f"Model: {name}")  # f-string 先求值 → _("Model: claude-sonnet") → 无匹配
```
修复：将 f-string 转为 `.format()` + `_()`：
```python
_cprint("  " + _("Model: {name}").format(name=name))
# _() 先翻译模板 → "模型：{name}" → .format() 填充 → _cprint 再次 _() → 已是中文，直通
```
双层 `_()` 无害：中文传入 `_()` 无匹配则原样返回。

---

## 大规模汉化策略

### 自动化管道

全量汉化分 6 阶段自动化（`scripts/i18n_pipeline.py`）：

| 阶段 | 操作 | 说明 |
|------|------|------|
| 1 | 扫描 | 遍历全部 .py 文件，检测输出调用、i18n 导入、`_` 冲突 |
| 2 | 注入 | 给高频输出文件添加 `from bwm_cli.i18n import _` |
| 3 | 解决 | 重命名 `_` 抛弃变量为 `_unused`/`_ign`/`_i` |
| 4 | 提取 | 扫描所有已注入文件的静态字符串 + 包装函数参数 |
| 5 | 生成 | 对比现有 .po，生成新条目（含词汇表翻译） |
| 6 | 编译 | 运行 `compile_i18n.py` + 验证核心翻译 |

运行：`python scripts/i18n_pipeline.py [--dry-run] [--phase N] [--from-phase N]`

### 包装函数自动翻译（最高效策略）

与其逐个包裹 `print()`，不如修改输出包装函数内部调用 `_()`：

```python
# 修改前
def _cprint(text: str):
    _pt_print(_PT_ANSI(text))

# 修改后 — 覆盖全部 243 处 _cprint() 调用
def _cprint(text: str):
    _pt_print(_PT_ANSI(_(text)))
```

已在以下包装函数中实施：
| 函数 | 文件 | 覆盖调用数 |
|------|------|-----------|
| `_cprint()` | cli.py | ~243 |
| `_safe_print()` | run_agent.py | ~100 |
| `_vprint()` | run_agent.py | ~90（继承 _safe_print） |
| `check_ok/warn/fail/info()` | doctor.py | ~329 |
| `_notify()` / `_notify_error()` | run_agent.py | ~10 |

**效果**：静态字符串自动翻译，f-string 保持不变（不会破坏动态内容）。

### 批量翻译占位符

`scripts/i18n_translate_placeholders.py` — 基于 120+ 条词汇表批量翻译 `[待翻译]`/`[EN]` 占位符。

### 冲突解决脚本

`scripts/i18n_resolve_conflicts.py` — 批量处理 `_` 变量冲突，使用字节级精确替换。

## 代码审查清单

修改核心文件后执行：
- [ ] 二进制模式编辑后 `py_compile.compile(file, doraise=True)` 验证语法
- [ ] 检查文件中是否有 `_` 作为局部变量（grep `_, .* =`），需先重命名再导入
- [ ] 自动导入注入后检查未插入括号内多行导入块
- [ ] 翻译条目 `msgid` 与源码 `_("...")` 参数完全一致（含空格、标点）
- [ ] 编译 .mo：`python scripts/compile_i18n.py`
- [ ] 验证：`python -c "from bwm_cli.i18n import _, setup_i18n; setup_i18n('zh_CN',force=True); print(_('Welcome to BookwormPRO'))"` 应输出中文
- [ ] 翻译条目约 1203 条，可通过 `scripts/i18n_pipeline.py --from-phase 4` 增量更新
