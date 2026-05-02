---
name: windows-python-subprocess-encoding
description: >
  Fix Python subprocess encoding crashes on Windows. When subprocess.run()
  with text=True fails with UnicodeDecodeError, or result.stdout is None
  causing AttributeError on .split(). Covers wmic→PowerShell migration for
  Win11 24H2 compatibility.
allowed-tools: Read, Write, Bash, Glob, Grep
maturity: stable
last-reviewed: 2026-04-30
---

# Windows Python Subprocess Encoding Fix

## Trigger
- `subprocess.run(capture_output=True, text=True)` crashes with `UnicodeDecodeError` on Windows
- `result.stdout` is `None` causing `AttributeError: 'NoneType' object has no attribute 'split'`
- `wmic` command not found (removed in Windows 11 24H2)

## Root Cause
1. **Encoding mismatch**: Windows system commands (wmic, PowerShell) output in the system code page (GBK/CP936 on Chinese Windows), not UTF-8. `text=True` defaults to UTF-8 decoding which fails on non-ASCII chars.
2. **wmic deprecated**: Removed in Windows 11 24H2. Use PowerShell `Get-CimInstance`.

## Fix Pattern

### A. Replace wmic with PowerShell
```python
# OLD (broken):
result = subprocess.run(
    ["wmic", "process", "get", "ProcessId,CommandLine", "/FORMAT:LIST"],
    capture_output=True, text=True, timeout=10,
)

# NEW:
result = subprocess.run(
    ["powershell", "-NoProfile", "-Command",
     "Get-CimInstance Win32_Process | "
     "Select-Object ProcessId,CommandLine | "
     "ForEach-Object { "
     '  Write-Output ("CommandLine=" + $_.CommandLine); '
     '  Write-Output ("ProcessId=" + $_.ProcessId) '
     "}"],
    capture_output=True, timeout=15,
)
```

### B. Capture bytes + errors='replace' (always use with A)
```python
# Instead of text=True:
result = subprocess.run(cmd, capture_output=True, timeout=15)
if result.returncode != 0:
    return []
stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""

# Then use `stdout` (not `result.stdout`):
for line in stdout.split("\n"):
    ...
```

## CRLF Patch Pitfall on Windows
The `patch` tool fails on Windows CRLF files — verification detects byte-count mismatch (tool writes LF, disk has CRLF). **Never use `patch` for Windows CRLF files.** Instead write a temp Python script doing binary replacement:

```python
with open(filepath, "rb") as f:
    content = f.read()
old_block = b'...exact bytes including \\r\\n...'
new_block = b'...replacement bytes with \\r\\n...'
assert old_block in content, "old block not found!"
content = content.replace(old_block, new_block, 1)
with open(filepath, "wb") as f:
    f.write(content)
```

## Post-Fix Checklist
1. Delete `__pycache__/*.pyc` to clear stale bytecode
2. Run the failing command to confirm fix
3. Grep for `result.stdout.split` — should only remain in Linux/macOS branches

## BookwormPRO Instance
- File: `bwm_cli/gateway.py`, function `_scan_gateway_pids()` (~line 277)
- Broke because Chinese Windows process names contain GBK chars
- Fixed by: wmic→Get-CimInstance + bytes capture + errors='replace'
