---
name: bookwormpro-feature-audit-and-optimization
description: Systematic gap analysis of BookwormPRO features against a checklist, plus multi-module parallel optimization workflow. Use when the user presents a feature checklist/mind-map and asks "what's missing" or wants batch optimization.
version: 1.0.0
author: BookwormPRO
tags: [bookwormpro, audit, gap-analysis, optimization, workflow]
---

# BookwormPRO Feature Audit & Optimization

Systematic methodology for comparing BookwormPRO codebase against a feature
checklist, identifying gaps, and executing batch optimization.

## When to Use

- User presents a feature checklist/mind-map and asks "还缺哪些" (what's missing)
- User wants batch optimization of multiple features ("全部优化")
- User has a "必做一览" (must-do list) to audit

## Phase 1: Gap Analysis (5-10 min)

### Step 1: Bulk Search for Feature Traces

For each checklist item, run `search_files(target='content')` across the entire
BookwormPRO codebase. Use keywords derived from the checklist item name.

Example for "三层记忆系统":
```python
search_files(pattern='memory|honcho|mem0|supermemory', target='content', path='C:\Users\BOOKWORMPRO_USER\BookwormPRO')
```

### Step 2: Deep-Read Key Files

For each feature, read the entry points to assess actual implementation depth:
- `tools/browser_camofox.py` → browser anti-crawling
- `agent/memory_provider.py` + `plugins/memory/` → memory system
- `agent/shell_hooks.py` → hooks system
- `bwm_cli/backup.py` → backup
- `tools/delegate_tool.py` → multi-agent

### Step 3: Check User's Actual Config

```bash
cat ~/.bookwormpro/config.yaml | head -150
cat ~/.bookwormpro/.env | grep -i "CAMOFOX|BROWSERBASE|STEALTH"
```

### Step 4: Assign Completion Percentages

Rate each item 0-100% based on:
- **100%**: Code exists, configured, and tested
- **80-95%**: Code exists but user hasn't configured
- **50-70%**: Core mechanism exists but major sub-features missing
- **30% or below**: Only stub/basic implementation

### Step 5: Prioritize

Sort by gap severity (lowest % = highest priority). Present as table.

## Phase 2: Parallel Module Creation (10-20 min)

### Pattern A: Independent Modules via Subagent

For modules with NO dependencies on each other, use `delegate_task` with
`role='orchestrator'` to create multiple files in parallel.

```python
delegate_task(
    goal="Create N new Python modules for BookwormPRO...",
    context="Full requirements for each...",
    role="orchestrator",
    toolsets=["terminal", "file", "web"]
)
```

**PITFALL**: Subagent timeout (600s default) does NOT mean failure.
Always check filesystem for partial results:
```bash
ls -la ~/BookwormPRO/agent/memory_temporal.py ~/BookwormPRO/bwm_cli/audit.py
```

### Pattern B: Direct Write for Small Files

For quick wins like SOUL.md (< 100 lines), write directly with `write_file`.

### Pattern C: CLI Integration into main.py

**CRITICAL PITFALL**: BookwormPRO's `bwm_cli/main.py` is 18K+ lines.
The `patch` tool ALWAYS fails on Windows due to CRLF mismatch.
Workaround: Use Python via terminal for targeted string replacement.

```bash
python -c "
path = r'C:\Users\BOOKWORMPRO_USER\BookwormPRO\bwm_cli\main.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Find insertion point by searching for unique marker
idx = content.find('import_parser.set_defaults(func=cmd_import)')
end_idx = content.index(chr(10), idx) + 1

# Insert new CLI block
content = content[:end_idx] + new_cli_block + content[end_idx:]

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
"
```

### Pattern D: Adding New CLI Flags

```bash
python -c "
# Replace cmd_* function body for dispatch
old_func = '''def cmd_backup(args):...'''
new_func = '''def cmd_backup(args):...new dispatch logic...'''
content = content.replace(old_func, new_func, 1)
"
```

## Phase 3: Verification

1. Syntax check all new files:
   ```bash
   python -c "import py_compile; py_compile.compile('path', doraise=True)"
   ```
2. Verify main.py still imports cleanly
3. Test new CLI commands if possible

## Common Pitfalls

1. **Patch tool + Windows CRLF**: Always fails with "wrote X chars, read back Y chars".
   Use Python `replace()` via terminal instead.

2. **Subagent timeout**: 600s timeout often triggers on complex code generation,
   but subagent may have written files before timing out. Always check.

3. **Concurrent main.py modification**: If subagent modifies main.py while you're
   also editing it, use `search_files` to find moved function locations before
   applying your changes. Line numbers WILL shift.

4. **Memory system**: current memory is flat (builtin 2 stores + 1 external provider),
   NOT temporal short/medium/long term. The "三层记忆" checklist item refers to
   temporal decay layers, which need a NEW module (not just config).

5. **Backup**: original is local ZIP only. "三层备份" means ZIP + Git + Remote push
   as three independent layers, NOT three similar copies.
