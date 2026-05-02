---
name: python-import-corruption-fix
description: >
  Detect and fix syntax errors where a single-line import statement
  (e.g. `from bwm_cli.i18n import _`) has been incorrectly inserted
  inside the parenthesized body of a multi-line import block.
  Fix: pop the stray line, then re-insert it AFTER the closing `)`.
  Run py_compile on all *.py files first to find all affected files,
  then apply the fix script to each. Always verify with py_compile
  after fixing.
trigger_keywords:
  - multi-line import broken
  - SyntaxError inside import (
  - stray import inside parens
  - from X import _ broken
  - import statement corrupted
---

# Python Import Corruption Fix

## Problem

A systematic corruption pattern where a single-line import like:
```python
from bwm_cli.i18n import _
```
gets inserted inside a multi-line parenthesized import block:
```python
from .whatsapp_identity import (
from bwm_cli.i18n import _         # ← STRAY — inside parens
    canonical_whatsapp_identifier,
    normalize_whatsapp_identifier,
)
```

This produces `SyntaxError: invalid syntax` because the stray import is syntactically inside the parenthesized expression.

## Detection

```bash
# Full scan to find ALL broken files
cd /path/to/project
python -c "
import py_compile, glob
for f in glob.glob('**/*.py', recursive=True):
    if any(x in f for x in ['__pycache__','.venv','node_modules']):
        continue
    try:
        py_compile.compile(f, doraise=True)
    except py_compile.PyCompileError as e:
        print(f'BROKEN: {f} — {e}')
"
```

## Fix Script (batch)

```python
import py_compile

FILES = [
    # List paths from detection step above
]

for path in FILES:
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    for i, line in enumerate(lines):
        if line.strip().startswith('from ') and 'import _' in line:
            # Check if inside parenthesized block
            paren_depth = 0
            for j in range(i):
                paren_depth += lines[j].count('(') - lines[j].count(')')
            
            if paren_depth > 0:
                # Pop the stray line
                stray = lines.pop(i)
                # Find the closing ')' of current block
                for k in range(i, len(lines)):
                    if lines[k].strip() == ')':
                        # Insert after ')'
                        lines.insert(k + 1, '\n')
                        lines.insert(k + 2, stray)
                        break
                # Remove trailing blank left by removal
                if i < len(lines) and lines[i].strip() == '':
                    lines.pop(i)
                break
    
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.writelines(lines)
    py_compile.compile(path, doraise=True)
```

## Pitfalls

- **Don't fix blindly**: Only move the stray line if `paren_depth > 0` (inside a multi-line import). If it's at module level, leave it alone.
- **Verify after fix**: Always re-run `py_compile` on every fixed file.
- **Commit separately**: These are pre-existing corruptions, not part of feature work. Commit them in their own commit: `fix: repair stray import statements in multi-line blocks`
- **Root cause unknown**: The corruption may have been caused by a broken find-and-replace tool or editor macro. If it recurs, investigate the toolchain.
