---
name: windows-large-file-batch-editing
description: >
  Safe pattern for batch-editing large Python files (>5000 lines) on Windows.
  Use when applying 3+ integration points to run_agent.py, config.py, or
  similar large files. Prevents f-string destruction, indentation drift,
  and patch verification failures caused by Windows CRLF handling.
trigger: >
  editing run_agent.py or config.py with 3+ changes; batch-applying feature
  flags across multiple code paths; replacing multiple integration points
  with a single atomic script.
category: devops
---

# Windows Large File Batch Editing

When you need to apply multiple changes (3+ integration points) to a large Python
file (>5000 lines, like run_agent.py at 13K LOC or config.py at 4K LOC),
do NOT do incremental edits via `patch` or ad-hoc Python one-liners.

## Why incremental edits fail on Windows

1. **f-string destruction**: `\n` escape sequences in replacement strings get
   converted to literal newlines, breaking f-strings.
2. **Indentation drift**: Each incremental edit can shift indentation. After
   3+ edits, functions end up at wrong nesting levels.
3. **patch tool fails on large files**: Post-write verification diffs exceed
   threshold, patch reverts.

## Correct pattern

### Step 1: Write a SINGLE comprehensive fixup script

```python
"""Apply ALL changes to file in one atomic pass."""
path = r'absolute\path\to\file.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

changes = 0
def apply(old, new, label):
    global content, changes
    if old not in content:
        print(f'  SKIP: {label}')
        return False
    content = content.replace(old, new, 1)
    changes += 1
    print(f'  OK: {label}')
    return True

apply('old_string_1', 'new_string_1', 'change 1')
apply('old_string_2', 'new_string_2', 'change 2')

with open(path, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)

import py_compile
py_compile.compile(path, doraise=True)
print(f'{changes} changes applied - syntax OK')
```

### Step 2: NEVER embed `\n` in replacement strings

Instead of `"line1\nline2"`, use `"line1" + chr(10) + "line2"`.

### Step 3: Auto-revert on failure

```python
except py_compile.PyCompileError:
    import subprocess
    subprocess.run(['git', 'checkout', '--', path])
    raise
```

### Step 4: Clean up

Delete temporary scripts after success: `rm rebuild_*.py fix_*.py patch_*.py`

## Verification

Always run: `python -c "import py_compile; py_compile.compile('file', doraise=True)"`
