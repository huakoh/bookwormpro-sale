---
name: bookwormpro-i18n-chinese-localization
description: >
  Add or extend Chinese (zh_CN) i18n to BookwormPRO CLI using a self-contained
  translation engine.  Use when asked to 汉化, localize, translate UI strings,
  or add language support to BookwormPRO.  Covers the i18n module architecture,
  .po/.mo workflow, pitfalls (Windows gettext, CRLF, _() shadowing), and the
  phased rollout strategy.
category: devops
---

# BookwormPRO i18n Chinese Localization

## Architecture

```
BookwormPRO/
├── bwm_cli/i18n.py              ← Self-contained translator (NO system gettext dependency)
├── locale/
│   └── zh_CN/LC_MESSAGES/
│       ├── bookwormpro.po        ← Human-editable translations (UTF-8)
│       └── bookwormpro.mo        ← Compiled binary
└── scripts/
    ├── compile_i18n.py           ← .po → .mo compiler (pure Python, no msgfmt needed)
    └── extract_strings.py        ← Scans code for _("...") calls, generates .pot
```

## Why Self-Contained Translator (NOT Python gettext)

Python's `gettext.translation()` on Windows fails with:
```
'ascii' codec can't decode byte 0xe8
```
because Windows defaults to the system ANSI locale (cp1252), and Chinese
UTF-8 bytes trigger a decode error during .mo file loading.

**Solution:** `bwm_cli/i18n.py` implements `_Translator` class that:
- Reads .mo binary directly with `read_bytes()` (UTF-8 safe)
- Parses the .mo format manually (magic 0x950412DE, offset tables, string data)
- No dependency on system locale, LANG env var, or GNU gettext

## Usage

```python
from bwm_cli.i18n import _, setup_i18n, get_language

setup_i18n('zh_CN')           # Explicit, or auto-detect
print(_("Welcome"))           # → 欢迎使用 BookwormPRO
print(_("个 active"))         # → 个活跃
```

Language detection order: `config.yaml language:` → `LANG` env → default `zh_CN`.

## Adding a New Translation

1. Edit `locale/zh_CN/LC_MESSAGES/bookwormpro.po`:
   ```
   msgid "Original English text"
   msgstr "中文翻译"
   ```
2. Run `python scripts/compile_i18n.py` to rebuild .mo
3. Verify: `python -c "from bwm_cli.i18n import _; print(_('Original English text'))"`

## Wrapping Code for i18n

### Simple strings
```python
print(_("Session saved"))        # Was: print("Session saved")
```

### f-strings with markup
```python
# Before:
right_lines.append(f"{LBL('工具')} [bright_cyan]{len(tools)}[/] [dim]个 active[/]")

# After:
right_lines.append(f"{LBL('工具')} [bright_cyan]{len(tools)}[/] [dim]{_('个 active')}[/]")
```

### f-strings with variables (use .format)
```python
# Before:
print(f"[成功] Model switched: {result.new_model}")

# After:
print(_("[成功] Model switched: {model}").format(model=result.new_model))
```

## Pitfalls

### 1. Windows CRLF breaks patch tool
The `patch` tool fails with "wrote X chars, read back Y chars" on Windows.
**Workaround:** Use `sed -i` in terminal for simple replacements, or
`write_file` with full file content for complex edits. Always re-read with
`read_file` (no offset/limit) before `write_file` to get exact on-disk content
including CRLF.

### 2. `_` variable shadowing
If `_` is used as a throwaway variable anywhere in the file scope (e.g.,
`_, foo = some_func()`), it shadows the i18n `_()` function and causes
`TypeError: 'list' object is not callable`.

**Fix:** Rename the throwaway variable (e.g., `_unused, foo = ...` or
`_avail, foo = ...`).

### 3. Import insertion must avoid try/except blocks
When adding `from bwm_cli.i18n import _` via sed or script, ensure the
insertion point is at the top-level import section, NOT inside a function
or try/except block.  Prefer inserting after stable anchor strings like
`from bwm_cli import __version__` or `from bwm_constants import`.

### 4. .mo offset calculation
The offsets in the .mo binary point to positions in the **final file**,
calculated as `STRING_START + offset_in_data`.  `STRING_START = 28 + 2*N*8`
where N = number of entries + 1 (header).  Getting this wrong causes
gettext (or the custom parser) to read garbage.

## ANSI Escape Codes Block Translation

`_(text)` silently passes through when text contains `\033[...m` — .po msgids never include ANSI. Error/warning messages with `_cprint(f"\033[31m[失败] ...")` stay English. No clean workaround for auto-translate helpers; f-string call sites must be manually restructured to separate tag from message.

## Source vs Installed Module (pip install -e)

After source edits, `bookworm` may still load old site-packages copy. Verify:
```python
import cli; print(cli.__file__)  # Must show BookwormPRO source path
```
If not: `cd BookwormPRO && pip install -e . --user`

## Full-Scale i18n Pipeline (2026-05-02)

For batch i18n across 50+ files, use `scripts/i18n_pipeline.py`:

```bash
python scripts/i18n_pipeline.py [--dry-run] [--phase N] [--from-phase N]
```

| Phase | Action | Automation | Pitfall |
|-------|--------|-----------|---------|
| 1 | Scan 164 .py files → output calls, i18n status, `_` conflicts | ✓ | Dry-run first |
| 2 | Inject `from bwm_cli.i18n import _` | ✓ Skip if unresolved `_` conflicts | **Never insert inside parenthesized multi-line imports** |
| 3 | Resolve `_` conflicts (rename → `_unused/_ign/_i`) | ⚠ 14/19 auto, 5 need manual | gateway/run.py, run_agent.py need manual |
| 4 | Extract unique strings from `_(...)`, check_*, _cprint, print, color() | ✓ Conservative regex | Filters ANSI escapes, Rich tags, f-string placeholders |
| 5 | Generate .po with TECH_GLOSSARY translations | ⚠ ~40% auto-covered | Remaining marked `[待翻译]` or `[待审]` |
| 6 | Compile .mo + verify 8 core translations | ✓ Full auto | — |

**2026-05-02 session results**: 146→1005 unique strings extracted, 233→1203 .po entries, 59 files injected, 19 conflicts resolved.

## ANSI Escape Codes Block Translation + Source vs Installed

**ANSI pitfall**: `_(text)` fails when text contains `\033[...m` codes — .po msgids are plain text, never match. ANSI error messages remain English. Workaround: separate tag from message at call site.

**Source vs installed**: `bookworm` may run from site-packages. Verify `import cli; cli.__file__` points to source. If not: `pip install -e .`

## Auto-Translate Helper Pattern (WARNING: only catches static strings)

Modify output wrapper functions to call `_()` internally — covers hundreds of call sites at once:

```python
# BEFORE
def _cprint(text: str):
    _pt_print(_PT_ANSI(text))

# AFTER — 243 _cprint() calls auto-translated, f-strings pass through harmlessly
def _cprint(text: str):
    _pt_print(_PT_ANSI(_(text)))
```

**Applied to**: `_cprint()` (cli.py, 243 calls), `_safe_print()`+`_vprint()` (run_agent.py, ~190), `check_ok/warn/fail/info()` (doctor.py, 329).

**Limitation**: f-string arguments evaluate BEFORE `_()` sees them → stay English. Those call sites need manual `.format()` conversion.

## CRLF-Safe File Editing on Windows

**NEVER** use `content.replace()` in text mode on large Windows files — CRLF→LF conversion during read corrupts binary-exact replacements on write (654→4497 lines seen in model_tools.py).

**Safe**: binary mode with exact `\r\n` byte sequences:
```python
with open(path, 'rb') as f:
    data = f.read()
data = data.replace(b'target\r\nbytes', b'replacement\r\nbytes')
with open(path, 'wb') as f:
    f.write(data)
```

## Qualified Import for Discord Italic Conflict

`gateway/run.py` uses `_(text)_` for Discord italic markdown. Do NOT use `from bwm_cli.i18n import _`.

**Fix**: `from bwm_cli import i18n` then call `i18n._("text")` — keeps `_(markdown)_` intact.

## F-String Auto-Conversion — DO NOT ATTEMPT

Regex-based `f"..."` → `.format()` conversion caused SyntaxError (57/60 succeeded, 1 corrupted file). Manual conversion only.

## Verification

For batch i18n across 50+ files, use `scripts/i18n_pipeline.py`:

```
python scripts/i18n_pipeline.py [--dry-run] [--phase N] [--from-phase N]
```

| Phase | Action | Safe to automate | Key pitfall |
|-------|--------|------------------|-------------|
| 1 | Scan all .py files → output calls, i18n status, `_` conflicts | ✓ Dry-run first | — |
| 2 | Inject `from bwm_cli.i18n import _` at import section | ✓ Skip files with unresolved `_` conflicts | Insert after multi-line import blocks, not inside |
| 3 | Resolve `_` conflicts (rename `_` → `_unused/_ign/_i`) | ⚠ Review complex patterns | `gateway/run.py`, `run_agent.py` need manual |
| 4 | Extract unique strings from `_()` and helper calls | ✓ Conservative regex | Only catches `_("text")` and known helper patterns |
| 5 | Generate .po entries with placeholder translations | ⚠ 129 `[待翻译]` entries need human review | TECH_GLOSSARY covers ~40% |
| 6 | Compile .mo + verify 8 core translations | ✓ Full auto | — |

**⚠ Critical**: The pipeline injects imports and resolves conflicts, but does NOT automatically wrap `print()` calls in `_()`. That requires per-file work (see "Auto-Translate Helper Pattern" below).

## Auto-Translate Helper Pattern

The most efficient way to i18n files with many output calls: modify output helper functions to call `_()` internally, rather than wrapping every call site.

```python
# BEFORE — every call site needs _()
def check_ok(text, detail=""):
    print(f"  [成功] {text}" + (f" ({detail})" if detail else ""))

# AFTER — helper auto-translates static strings, f-strings pass through harmlessly
def check_ok(text, detail=""):
    print(f"  [成功] {_(text)}" + (f" ({_(detail)})" if detail else ""))

check_ok("Native install — full host filesystem access")  # ✓ auto-translated
check_ok(f"Python {ver}")           # ✗ f-string evaluated before _() → stays English
check_ok("Host bridge mounted", "(read-write)")           # ✓ both auto-translated
```

**Limitation**: F-string arguments are evaluated BEFORE reaching `_()`, so the interpolated string won't match any translation key. Those call sites still need manual conversion:

```python
# Fix f-string call sites manually:
check_ok(_("Python {ver}").format(ver=ver))  # Template preserved for translation
```

**Impact**: For `doctor.py` (329 output calls), this single edit to 4 helper functions delivered ~80% static string coverage.

**Applicable to**: `check_ok/warn/fail/info` (doctor.py), `_notify/_notify_error` (run_agent.py), `_cprint/_console_print` (cli.py), etc.

## Bulk Injection Strategy

When i18n-izing 50+ files, separate import injection from string wrapping:

1. **Run pipeline Phase 1-3**: Inject imports, resolve `_` conflicts — fully automated
2. **Per-file Phase 4a**: Identify output helper functions, apply auto-translate pattern
3. **Per-file Phase 4b**: Convert remaining f-string call sites to `.format()` (manual)
4. **Run pipeline Phase 4-6**: Extract strings, generate .po, compile — fully automated

This avoids trying to do everything in one pass. Files get `_()` available first, then wrapping happens incrementally. Pipeline can be re-run safely — it skips already-injected files.

## CRLF-Safe File Editing on Windows

NEVER use `patch` tool on Windows Python files — fails with "wrote X chars, read back Y chars". **NEVER** use `content.replace()` in text mode on large files — the CRLF→LF conversion during read corrupts binary-exact replacements on write.

**Safe pattern A — Python binary mode (preserves exact bytes)**:
```python
with open(path, 'rb') as f:
    data = f.read()
data = data.replace(b'old_bytes', b'new_bytes')
with open(path, 'wb') as f:
    f.write(data)
```

**Safe pattern B — Python text mode with newline='' (small files only)**:
```python
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()
# Modify content — all line endings already normalized to \n
with open(path, 'w', encoding='utf-8', newline='') as f:
    f.write(content)  # newline='' preserves original \r\n
```

**Pattern B failure mode**: On files with corrupted `\r\r\n` endings, `content.replace()` can introduce extra blank lines (654→4497 lines seen in model_tools.py). If line count explodes, restore from git and use binary mode instead.

## `_` Conflict Resolution Patterns

Safe regex patterns for automated rename of throwaway `_` variables:

```python
# Pattern 1: for _, var in ...       → for _unused, var in ...
content = re.sub(r'\bfor\s+_\s*,', 'for _unused,', content)

# Pattern 2: _, var = expr           → _unused, var = expr
content = re.sub(r'^(\s*)_\s*,\s*(\w+\s*=)', r'\1_unused, \2', content, flags=re.MULTILINE)

# Pattern 3: _ = expr (NOT def _)    → _unused = expr
content = re.sub(r'^(\s*)_(\s*=\s*)(?!.*def)', r'\1_unused\2', content, flags=re.MULTILINE)
```

**Files requiring manual conflict resolution** (regex patterns insufficient):
- `bwm_cli/gateway.py` — `_` used in complex expressions
- `run_agent.py` — 5 distinct conflict patterns, multi-line import blocks
- `gateway/run.py` — 14 conflicts + Discord italic clash (see below)

## Qualified Import for Discord Italic Conflict

`gateway/run.py` uses `_(text)_` for Discord italic markdown, which clashes with gettext `_()`. **Do NOT** use `from bwm_cli.i18n import _` here.

**Fix**: Use qualified import, rename throwaway `_` variables separately:
```python
from bwm_cli import i18n  # use i18n._() to avoid Discord italic markdown conflict

# Then call translations as:
print(i18n._("Welcome to BookwormPRO"))

# Rename throwaway _ variables:
# for _ in range(30):     → for _i in range(30):
# _, base_msg, count = raw → _ign, base_msg, count = raw
```

## F-String Auto-Conversion — DO NOT ATTEMPT

Attempting to auto-convert `check_ok(f"...{var}...")` to `check_ok(_("...{var}...").format(var=var))` via regex is **too fragile**. Causes syntax errors due to:
- Multi-line f-strings with continuation
- Nested quotes (`f"text '{var}'"`)
- Complex expressions (`f"{var.attr.method():.2f}"`)
- Conditional expressions inside f-strings (`f"{a if b else c}"`)

**One attempt**: 57/60 f-strings converted, but introduced SyntaxError (extra `return` statement). Had to `git checkout` to restore.

**Recommendation**: Convert f-string call sites manually, or accept they display in English (auto-translate helper passes them through `_()` harmlessly).

## Runtime Verification (pip install -e trap)

Source edits to `cli.py`/`run_agent.py` may not take effect if `bookworm` runs from site-packages:
```bash
python -c "import cli; print(cli.__file__)"
# Must show: C:\Users\BOOKWORMPRO_USER\BookwormPRO\cli.py
# If shows site-packages: pip install -e . --user
```

Verify translations at runtime:
```bash
python -c "from bwm_cli.i18n import setup_i18n, _; print(_('Welcome to BookwormPRO'))"
# → 欢迎使用 BookwormPRO
```

Language persistence is automatic — `config.yaml` without `language:` key + empty `LANG` → defaults to `zh_CN`. No `force=True` needed in production.

## 2026-05-02 实战报告

全量汉化 session 成果（~2h, 63 文件修改）：

| 指标 | 数值 |
|------|------|
| i18n 导入注入 | 59/164 文件 (36%) |
| `_` 冲突解决 | 19 个文件 |
| .mo 编译条目 | 361 条 |
| 核心翻译验证 | 8/8 通过 |
| 自动翻译通道覆盖 | ~779 次输出调用/次 |

**自动翻译的包装函数**:
| 文件 | 函数 | 覆盖 |
|------|------|------|
| `cli.py` | `_cprint()` | 243 调用 |
| `run_agent.py` | `_safe_print()` + `_vprint()` | ~190 调用 |
| `doctor.py` | `check_ok/warn/fail/info()` | 329 调用 |
| `model_tools.py` | 直接 `_()` 包裹 | 8 调用 |

**关键工具**: `scripts/i18n_pipeline.py` (6 阶段), `scripts/i18n_resolve_conflicts.py`
