---
name: windows-python-file-editing
description: >
  Safely edit files on Windows (Git Bash) using Python scripts instead of
  the `patch` tool or inline `python -c "..."` commands. Handles CRLF line
  endings, shell escaping problems, and multi-edit verification.
category: devops
---

# Windows Python File Editing

When editing text files on Windows with Git Bash, avoid two common failure modes:

1. **`patch` tool** — CRLF conversions cause "Post-write verification failed"
2. **Inline `python -c "..."`** — Bash interprets backslashes and quotes, mangling
   the Python code before it runs

## Workflow

### 1. Write a fix script to a temp `.py` file

```python
"""Apply targeted edits with CRLF-safe I/O."""
from pathlib import Path

target = Path(r'C:\path\to\file.py')

with open(target, 'r', encoding='utf-8', newline='') as f:
    content = f.read()

# Apply changes one by one with assert/print for each
old = 'exact old string'
new = 'replacement string'
if old in content:
    content = content.replace(old, new)
    print('[1/N] Change applied')
else:
    print('[1/N] Pattern NOT found — may already be applied')

with open(target, 'w', encoding='utf-8', newline='') as f:
    f.write(content)
```

**Critical:** `newline=''` on both `open()` calls preserves the original line endings
(CRLF stays CRLF, LF stays LF). Without it, `read_text()` converts CRLF→LF and
`write_text()` writes LF-only, corrupting the file.

### 2. Execute the script

```bash
cd /c/path/to/project && python _fix_temp.py
```

Check the output — every change should report whether it was applied or skipped.

### 3. Verify with read_file

Use `read_file` tool at each modified location to confirm the change took effect.

### 4. Syntax check + cleanup

```bash
python -m py_compile path/to/file.py && echo "OK"
rm _fix_temp.py
```

## Pitfalls

### Shell escaping in `python -c`

```bash
# BROKEN: bash interprets \" and \\n before Python sees them
python -c "content.replace('old', 'new\n')"

# FIX: write to a .py file instead
```

### Identifying unique strings for replace

When a pattern appears multiple times (e.g., `left_lines.append("")`), include
enough surrounding context to match only the intended location:

```python
# Matches only the append() immediately before left_content assignment
old = '    left_lines.append("")\n    left_content ='
new = '    left_content ='
```

### CRLF vs LF detection

If a pattern with `\n` doesn't match, try `\r\n`:

```python
if old not in content:
    old_crlf = old.replace('\n', '\r\n')
    if old_crlf in content:
        content = content.replace(old_crlf, new)
```

### Stale bytecode cache

After editing `.py` files, if the user gets an IndentationError on a line that
looks correct, the `__pycache__` may be stale. Clear it:

```bash
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
```

### Recovery from corruption

If a script corrupts the file (double line endings, missing content):

```bash
git checkout -- path/to/file.py
```

Then fix the script and re-run.

### Patch tool false-positive verification

When editing CRLF files (especially `banner.py`), the `patch` tool often reports
"Post-write verification failed" but the change **actually persisted on disk**.
The verification counts written vs read-back bytes differently due to CRLF→LF
conversion in the read-back path.

**Workflow**: patch → read back the modified lines → if change is there, proceed
to syntax check → skip re-applying. Only retry if the read-back shows the old
code.

### Patch tool silent corruption (`\r\r\n`)

**Critical**: In some cases, the patch tool writes the change BUT corrupts the
file with double-CRLF (`\r\r\n`) instead of `\r\n`. The read-back will SHOW the
new code (so the "false-positive" check passes), but `python -m py_compile`
will fail with `SyntaxError: invalid syntax` on an apparently blank line.

This is NOT a false-positive — it's silent corruption. The file has been
damaged and CANNOT be recovered by re-patching or by a Python fix script
(because the `\r\r\n` line endings won't match either `\n` or `\r\n` patterns).

**Recovery workflow**:
1. After ANY patch tool "verification failed" error, run `py_compile` FIRST
2. If syntax error → `git checkout -- path/to/file.py`
3. Use a Python script with **explicit `\r\n`** in the match strings
4. Write the script as a `.py` file (NOT inline `python -c`)

```python
# CRLF-safe pattern: use explicit \r\n
old = ('    line one\r\n'
       '    line two\r\n'
       '    line three')

# Run: syntax check after write
# python -m py_compile target.py && echo "OK"
```

**Why Python scripts after `git checkout` also fail**: If you write a script
with `\n` patterns and the file has CRLF, `content.replace()` won't match.
If you use `\r\n` patterns but the file was already corrupted with `\r\r\n`,
the patterns also won't match. The ONLY safe path is: `git checkout` first,
then use explicit `\r\n` in the script's search strings.

### Dangerous: python -c with string.find() + substring slicing

Avoid `content.index('unique_string')` followed by `content[old_start:old_end]`
for replacement on CRLF files. If the end-marker string is too generic (e.g.,
`extend(_bl)`), it can match a different occurrence and corrupt the file. Instead:

- Use `content.replace(old_block, new_block)` with unique full blocks, OR
- Write a `.py` script with `newline=''` as described above

### Never use python -c oneliner without newline=''

When using `python -c "..."` to modify files inline, forgetting `newline=''`
in `open(path, 'w')` causes catastrophic corruption: the file's line count
explodes (e.g., 581→1716 lines) because `\r\n` gets double-converted to
`\r\r\n`. **Always** use `newline=''` when writing back to any file that may
have CRLF endings. Prefer writing a temp `.py` file over inline `-c` for
multi-step edits — easier to verify and recover.

### F-string corruption in python -c AND .py scripts

When the target file contains f-strings (e.g., `f'text {var}\n\n'`), using
`python -c` to modify it is EXTREMELY error-prone. The outer Python script's
string processing interprets `\n` as a literal newline, which then breaks the
target file's f-string into multiple lines:

```python
# INTENDED target output:
#     f'[break] {msg}\n\n'
#
# ACTUAL output from python -c (BROKEN):
#     f'[break] {msg}
#
# '

# FIX: Use explicit \\n in the replacement string of a .py script,
# NOT inline python -c.  The .py file preserves the literal \n characters.
```

**CRITICAL: Even .py scripts need QUADRUPLE-escaping for f-string `\n`.**

When writing a `.py` script that modifies another `.py` file containing
f-strings, the escaping chain is:

```
.py script source:    "f'text {var}\\\\n\\\\n'"    (\\\\n in source)
Python interprets:    "f'text {var}\\n\\n'"       (two chars: \\ and n)
Written to target:    f'text {var}\n\n'           (f-string escape works)
```

If you write just `\\n` (double backslash) in the .py script:
```
.py script source:    "f'text {var}\\n\\n'"       (\\n in source)
Python interprets:    "f'text {var}\n\n'"         (actual newline chars!)
Written to target:    f'text {var}                (BROKEN f-string split across lines)
                     '
```

The chain: **4 backslashes in source → 2 chars in memory → 2 chars on disk → valid f-string**.

```python
# CORRECT .py fix script:
old = "f'text {var}\\\\\\\\n\\\\\\\\n'"   # or use raw strings
new = "f'text {var}\\\\\\\\\\\\\\\\n\\\\\\\\n'"  # quad-escaped!
# Simpler: use repr-verified patterns
old = "f'text {msg}\\n\\n'"   # put LITERALLY \\n in the .py file source
new = "f'text {msg}\\n\\n'"
```

**Verification**: After the fix, run `py_compile`. The error message will say
"unterminated f-string literal (detected at line N)" if the escaping was wrong.
Then use `read_file` at that line and check with `repr()` to see the actual
characters.

**Rule**: If the target file contains ANY f-strings with escape sequences,
write a temp `.py` file. Triple-escape in `python -c` is never worth debugging.
For f-string `\n` specifically, use QUADRUPLE backslashes in the .py script.

**Simpler alternative — `chr(10)` for newlines**: When the ONLY escape you need
in a target f-string is `\n`, avoid the escaping headache entirely by using
`chr(10)` in the replacement string:

```python
# INSTEAD of escaping \\n across multiple levels:
new_block = "f'text {var}\\\\n\\\\n'"  # fragile quad-escaping

# USE chr(10) which survives all levels of string processing:
new_block = "f'text {var}' + chr(10) + chr(10)"
```

And in the target file itself, for `return "\n".join(lines)` that keeps getting
split across lines during edits:
```python
# Before (breaks on Windows edits):  return "\n".join(lines)
# After (immune to escaping issues): return chr(10).join(lines)
```

This is especially useful for `return` statements, `f'...'` format strings,
and `final_response` blocks where newlines are the only special characters.

### F-string `\n` corruption: `chr(10)` alternative

When the target file contains f-strings with `\n`, Python scripts that write
other Python files will ALWAYS mangle the `\n`. The script's own string processing
interprets `\n` as a literal newline character, splitting the f-string across
multiple lines in the target file. Quad-escaping (`\\\\n`) is fragile.

**Simplest fix**: replace `\n` in target file strings with `chr(10)`:

```python
# BROKEN target (will split during edits):
#     return "\n".join(lines)

# FIXED target (immune to escaping):
#     return chr(10).join(lines)

# FIXED in Python script:
old = [']    return \"[/']
new = [']    return chr(10).join(lines)[/']

# FIXED for f-string in target:
# Before:  f'[text] {msg}\n\n'
# After:   f'[text] {msg}' + chr(10) + chr(10)
```

This is the **only reliable method** for newlines in strings that will be
re-embedded by other Python scripts. Quad-escaping works sometimes but fails
when the chain involves `read()` → `replace()` → `write()` with different newline modes.

### Module-level constants near class methods

When inserting constants like `_CONFIG = {...}` before a `@staticmethod` inside
a class body, the constant MUST be at the correct indentation level. If it's
at column 0 (module level) but physically sits inside a `class Foo:` body, Python
raises `IndentationError: unexpected indent` on the following `@staticmethod`.

**Fix**: insert constants ABOVE the `class Foo:` line (true module level), not
inside the class body. Use `content.find('class AIAgent')` to locate the insertion
point and splice before it.

### Git revert + single-script rebuild for large files

When a large file (10K+ lines) accumulates indentation errors from multiple
edits, do NOT try to fix them one by one. The cascading errors make each fix
potentially create new issues. Instead:

1. **Revert to clean state**: `git checkout -- path/to/file.py`
2. **Write a single comprehensive rebuild script** that applies ALL intended
   changes in one pass
3. **Verify syntax once** at the end

```python
"""Re-apply ALL modifications to a file from scratch."""
path = r'C:\path\to\file.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

changes = 0
def apply(old, new, label):
    global content, changes
    assert old in content, f'Pattern not found: {label}'
    content = content.replace(old, new, 1)
    changes += 1
    print(f'  [{changes}] {label} OK')

# Apply all changes in dependency order (imports first, then methods, then
# integration points in the call flow)
apply('old_import_line', 'new_import_line', 'imports')
apply('old_method_def', 'new_method_def', 'new method')
# ... more applies ...

with open(path, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)

import py_compile
py_compile.compile(path, doraise=True)
print(f'All {changes} changes applied - syntax OK')
```

This pattern was proven on `run_agent.py` (13K lines, 19 accumulated modifications)
after a batch feature-flag edit introduced cascading indentation errors. Reverting
and rebuilding took one script execution vs. hours of debugging individual fixes.

### Feature flag guard clause pattern

When adding env-var-controlled feature flags to existing code blocks, avoid
wrapping the entire block with `if not _disabled:` — this requires re-indenting
every line inside the block and often breaks try/except pairings. Instead, use
a **guard clause** at the TOP of the block:

```python
# BROKEN: wrapping causes indentation hell
if not _dns_disabled:
    try:
        _base_url = getattr(self, 'base_url', '')
        if _base_url:
            # ... 15 lines of deeply nested code ...
    except Exception:
        pass

# CORRECT: guard clause at top, no indentation changes below
try:
    if _dns_disabled:
        pass  # DNS cache disabled via env var
    elif not getattr(self, '_probe_checked', False):
        _dead = _check_provider_health(self.provider, ...)
        # ... existing code unchanged ...
except Exception:
    pass
```

The guard clause (`pass` on disabled, `elif` for the real logic) keeps all
existing indentation intact and avoids breaking nested try/except blocks.

```python
with open(target, 'r') as f:
    content = f.read()

# Patch 1: import
content = content.replace(old_import, new_import, 1)

# Patch 2: pre-call guard
content = content.replace(old_guard, new_guard, 1)

# Patch 3: post-success recording
content = content.replace(old_success, new_success, 1)

# Patch 4: post-failure recording  
content = content.replace(old_failure, new_failure, 1)

# Patch 5: cleanup in close()
content = content.replace(old_cleanup, new_cleanup, 1)

with open(target, 'w', newline='\n') as f:
    f.write(content)

import py_compile
py_compile.compile(target, doraise=True)
```

This avoids multiple `patch` tool attempts (each likely to fail on large files)
and provides an all-or-nothing atomic update.

```python
# BROKEN: _CONFIG at module level, but physically inside class body
class Foo:
    _CONFIG = {...}

    @staticmethod   # ← IndentationError here
    def bar(): ...

# FIX: Either indent _CONFIG as a class attribute, or move it ABOVE the
# `class Foo:` line to true module level.
```

To verify: after inserting constants, always run `py_compile` and check the
line number of the error — it points to the FIRST token after the mis-indented
block, not the block itself.

### Extremely large files (10K+ lines)

For files over ~10K lines (especially `run_agent.py` at 13K+), the `patch` tool
will ALWAYS fail with "Post-write verification failed" — even for single-line
changes. The byte counting verification is unreliable at this scale.

**Rule**: For files >5000 lines, skip `patch` entirely. Always write a `.py`
script with `content.replace()`. This applies to `run_agent.py` particularly.

### Debugging failed content.replace() with repr()

When `content.replace(old, new)` silently fails (pattern not found), print the
target area with `repr()` to see hidden characters:

```python
idx = content.find('expected unique string')
if idx >= 0:
    # Show 200 chars around the match with repr for debugging
    print(repr(content[idx:idx+200]))
else:
    # Scan broader area
    for i, line in enumerate(lines):
        if 'keyword' in line:
            print(f'{i+1}: {repr(line)}')
```

This reveals CRLF vs LF mismatches, double-escaped characters, and extra
whitespace that plain `print()` hides.

### Python `import` inside conditionals: UnboundLocalError trap

When adding `import X` inside a method body (not module level), Python's compiler
scans the ENTIRE function for assignments to `X`. If `X.method()` appears anywhere
in the function, Python treats `X` as a local variable. If the `import X` is inside
an `if` block that doesn't execute, `X` is never bound → `UnboundLocalError` (or
`cannot access local variable 'X' where it is not associated with a value`).

```python
# BROKEN: Python sees threading.Lock() below → threading is local
# But import is inside if-block that may not execute
def __init__(self):
    if not hasattr(self, '_pool'):
        import threading          # ← never runs if hasattr is True
        self._lock = threading.Lock()  # ← UnboundLocalError!
    ...
    # Later in same method:
    with self._lock:  # ← also UnboundLocalError if import skipped
        ...

# FIX A: Use __import__() which doesn't trigger local-variable treatment
def __init__(self):
    import threading  # at module level in method, always executes
    if not hasattr(self, '_pool'):
        self._lock = threading.Lock()

# FIX B: Alias inside the conditional, never reference the alias outside
def __init__(self):
    if not hasattr(self, '_pool'):
        import threading as _thr  # aliased, only used inside this block
        self._lock = _thr.Lock()

# FIX C: Initialize unconditionally at the top of __init__
def __init__(self):
    import threading
    self._lock = threading.Lock()  # always set, no conditional
```

**Migration pattern**: When adding connection pool / lock attributes to a large
class (`run_agent.py` ~13K lines), initialize them at the TOP of `__init__`, before
any method that might access them. Use `git checkout` to revert if the file gets
corrupted by a failed edit.

### Precise line-index insertion (avoiding content.replace() ambiguity)

When inserting code at a specific line number in a large file, use `readlines()` +
`insert()` instead of `content.replace()`. This avoids matching the wrong occurrence
when the pattern appears multiple times:

```python
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Insert after line N (0-indexed)
insert_at = 1261
pool_init = [
    '        self._http_client_pool = {}\n',
    '        self._http_client_pool_last_use = {}\n',
    '        import threading as _thr\n',
    '        self._http_pool_lock = _thr.Lock()\n',
]
for i, line in enumerate(pool_init):
    lines.insert(insert_at + 1 + i, line)

with open(path, 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(lines)

# Always verify
import py_compile
py_compile.compile(path, doraise=True)
```

## When to use this

- Editing Python files on Windows (especially with Git Bash)
- The `patch` tool fails with "Post-write verification failed"
- Inline `python -c` produces garbled backslashes or missing quotes
- Multi-step edits where each change needs independent verification
