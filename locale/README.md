# BookwormPRO i18n 国际化维护指南

## 架构概览

```
bwm_cli/i18n.py              ← 翻译引擎 (_() 函数)
locale/
  bookwormpro.pot             ← 字符串模板 (自动生成)
  zh_CN/LC_MESSAGES/
    bookwormpro.po            ← 中文翻译 (手动编辑)
    bookwormpro.mo            ← 编译后的二进制 (由 .po 生成)
scripts/
  extract_strings.py          ← 扫描源码提取 _() 字符串
  compile_i18n.py             ← .po → .mo 编译
```

### 核心原理

所有用户可见字符串通过 `_()` 包裹：

```python
from bwm_cli.i18n import _

print(_("Welcome to BookwormPRO"))  # → 欢迎使用 BookwormPRO
print(_("Unknown command"))         # → 未知命令
```

语言检测优先级：`config.yaml language` → `LANG` 环境变量 → 默认 `zh_CN`。

## 日常维护流程

### 1. 添加新翻译

直接编辑 `locale/zh_CN/LC_MESSAGES/bookwormpro.po`：

```po
msgid "Original English text"
msgstr "中文翻译"
```

规则：
- `msgid` 必须与源码中 `_("...")` 的参数完全一致
- `msgstr` 写中文翻译
- 不要修改已有的 `msgid`
- 编码必须是 UTF-8

### 2. 编译翻译文件

```bash
cd /path/to/BookwormPRO
python scripts/compile_i18n.py
```

输出：`[i18n] Compiled N entries → locale/zh_CN/LC_MESSAGES/bookwormpro.mo`

无需重启，下次 import 自动生效（或调用 `setup_i18n(force=True)`）。

### 3. 在源码中新增可翻译字符串

```python
# Before:
print("Starting service...")

# After:
from bwm_cli.i18n import _
print(_("Starting service..."))
```

然后执行步骤 2 添加 `msgid/msgstr` 到 .po 文件。

### 4. 自动扫描遗漏字符串

```bash
python scripts/extract_strings.py
```

会扫描所有 Python 文件中的 `_("...")` 调用，更新 `locale/bookwormpro.pot` 模板文件。

用 diff 对比 .pot 和 .po 找出缺翻译的条目：

```bash
# 提取 .pot 中有但 .po 中没有的 msgid
grep '^msgid "' locale/bookwormpro.pot | sort > /tmp/pot.txt
grep '^msgid "' locale/zh_CN/LC_MESSAGES/bookwormpro.po | sort > /tmp/po.txt
diff /tmp/pot.txt /tmp/po.txt | grep '^<'
```

## 添加新语言

```bash
# 1. 创建目录
mkdir -p locale/ja/LC_MESSAGES

# 2. 复制模板
cp locale/bookwormpro.pot locale/ja/LC_MESSAGES/bookwormpro.po

# 3. 编辑 .po 填写日文翻译
# 4. 编译
python scripts/compile_i18n.py
```

注意：目前 `compile_i18n.py` 只编译 `zh_CN`。多语言需修改脚本或手动指定路径。

## 测试翻译

```python
from bwm_cli.i18n import _, setup_i18n

setup_i18n('zh_CN', force=True)
assert _("Welcome to BookwormPRO") == "欢迎使用 BookwormPRO"
assert _("Session") == "会话"
```

## 常见问题

### Q: 翻译不生效？
A: 检查 `config.yaml` 中 `language` 是否设为了 `en`。默认是 `zh_CN`。

### Q: 加了翻译但还是英文？
A: 确认 .mo 文件已编译（`python scripts/compile_i18n.py`）。如果运行时已加载，调用 `setup_i18n(force=True)` 强制重载。

### Q: 如何在 f-string 中使用 _()？
A: 用 `.format()` 代替 f-string：
```python
# 推荐
print(_("Stopped {count} processes.").format(count=n))

# 也可以用 f-string，但要确保 _() 在外部
msg = _("Model switched: {model}")
print(msg.format(model=name))
```

### Q: 为什么不直接用 Python gettext？
A: Windows 上 gettext 依赖系统 locale（常为 ASCII），中文 .mo 文件解码失败。自实现翻译器直接用 UTF-8 解析，跨平台一致。

## 语言切换

默认语言为 `zh_CN`（中文）。切换到英文：

```yaml
# ~/.bookwormpro/config.yaml
language: en
```

英文模式下，所有 `_()` 调用返回原文（msgid 本身就是英文），无需额外的 `.po` 编译。

切换回中文：`language: zh_CN` 或删除该行使用默认。
