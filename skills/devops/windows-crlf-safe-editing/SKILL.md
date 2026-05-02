---
name: windows-crlf-safe-editing
description: >
  Safely edit Windows Python files with CRLF line endings. Use when patch tool
  fails, content.replace() corrupts line counts, or imports break after insertion.
  Binary-mode byte replacement is the only reliable method for large files.
category: devops
---

# Windows CRLF-Safe File Editing

## Trigger
- `patch` tool fails: "wrote X chars, read back Y chars"
- `content.replace()` corrupts file (line count explodes: 654→4497)
- Import insertion breaks syntax (inserted inside multi-line parentheses)
- Editing Python files on Windows Git Bash

## The Only Reliable Pattern

```python
with open(path, 'rb') as f:
    data = f.read()
data = data.replace(b'old_bytes\r\n', b'new_bytes\r\n')
with open(path, 'wb') as f:
    f.write(data)
import py_compile; py_compile.compile(path, doraise=True)
```

## Why Text Mode Fails

Python text mode converts `\r\n` → `\n` on read. `content.replace("old\n", "new\n")` works but on write, `newline=''` tries to preserve original endings. If the file had corrupted `\r\r\n` or mixed endings, the rewrite corrupts it further.

## Import Insertion Rule

Never insert after `from bwm_cli.xxx import (` — that's a multi-line import. Insert after the closing `)`:

```python
# WRONG — inserted inside parenthesized block
from bwm_cli.timeouts import (
    get_provider_request_timeout,
from bwm_cli.i18n import _      # ← SYNTAX ERROR
    get_provider_stale_timeout,
)

# RIGHT — after closing paren
from bwm_cli.timeouts import (
    get_provider_request_timeout,
    get_provider_stale_timeout,
)
from bwm_cli.i18n import _
```

## Hex Debugging

When `replace()` doesn't match, dump exact bytes:
```python
with open(path, 'rb') as f: data = f.read()
idx = data.find(b'target_text')
print(data[idx-20:idx+80])        # surrounding bytes
print(' '.join(f'{b:02x}' for b in data[idx:idx+40]))  # hex dump
```

## Recovery

```bash
git checkout <file>   # Always works, file is safe in git
```

## Known Corruption Cases (2026-05-02 i18n session)

| File | Symptom | Cause | Fix |
|------|---------|-------|-----|
| `model_tools.py` | 654→4,497 lines, blank line explosion | `content.replace()` text mode on inconsistent `\r\r\n` endings | Binary mode rewrite |
| `cli.py` | Import inside multi-line `from bwm_cli.timeouts import (...)` | Pipeline `from bwm_cli` match picked parens line | Insert after closing `)` |
| `run_agent.py` | Same as cli.py | Same cause | Same fix |
| `gateway.py` | `_p()` helper corrupted line 1 | `\r\n` byte mismatch in helper block | `git checkout`, skip risky files

## 2026-05-02 Session: This pattern was used 7 times across cli.py, run_agent.py, model_tools.py, gateway.py
