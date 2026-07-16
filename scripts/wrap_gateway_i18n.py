#!/usr/bin/env python3
"""
Wrap user-facing strings in gateway/run.py with i18n._().

Handles:
1. return "..." → return i18n._("...")
2. return f"...{var}..." → return i18n._("...{var}...").format(var=var)
3. Strings in adapter.send() calls (simple single-line cases)

Does NOT handle:
- Multi-line strings (those need manual work)
- Strings already wrapped with i18n._()
- Logger messages
- Dict keys, config values, internal strings
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GATEWAY = ROOT / "gateway" / "run.py"


def extract_fstring_vars(s: str) -> list[str]:
    """Extract variable names from f-string placeholders like {var}, {var.attr}, {var[:20]}."""
    # Match {expr} but not {{ or }}
    placeholders = re.findall(r'\{([^{}]+)\}', s)
    vars_list = []
    for ph in placeholders:
        # Get the base variable name (before ., [, :, !, etc.)
        base = re.match(r'([a-zA-Z_]\w*)', ph)
        if base:
            vars_list.append((ph, base.group(1)))
    return vars_list


def convert_fstring_to_format(fstring_content: str, var_expressions: list[tuple[str, str]]) -> tuple[str, str]:
    """Convert f-string to i18n._("template").format(key=expr) pattern.

    Returns (template_string, format_args_string).
    For simple variables like {var}, keeps {var} in template.
    For complex expressions like {var[:20]}, replaces with {var_short} and maps.
    """
    template = fstring_content
    format_parts = []
    seen_bases = {}

    for expr, base in var_expressions:
        if expr == base:
            # Simple variable reference — keep as is, add to format
            if base not in seen_bases:
                format_parts.append(f"{base}={base}")
                seen_bases[base] = True
        elif re.match(r'^[a-zA-Z_]\w*\.\w+$', expr):
            # Attribute access like obj.attr — use as format key
            safe_key = expr.replace('.', '_')
            template = template.replace('{' + expr + '}', '{' + safe_key + '}')
            if safe_key not in seen_bases:
                format_parts.append(f"{safe_key}={expr}")
                seen_bases[safe_key] = True
        else:
            # Complex expression — simplify to base name with suffix
            # Check if base is already used
            key = base
            suffix = 0
            while key in seen_bases and seen_bases[key] != expr:
                suffix += 1
                key = f"{base}_{suffix}"
            template = template.replace('{' + expr + '}', '{' + key + '}')
            if key not in seen_bases:
                format_parts.append(f"{key}={expr}")
                seen_bases[key] = expr

    return template, ', '.join(format_parts)


# Lines that should NOT be wrapped (already i18n, logger, internal, etc.)
SKIP_PATTERNS = [
    r'i18n\._\(',
    r'logger\.',
    r'^\s*#',
    r'raise\s',
    r'\.format\(',  # already has format, might be wrapped
]


def should_skip_line(line: str) -> bool:
    return any(re.search(pat, line) for pat in SKIP_PATTERNS)


def process_file():
    lines = GATEWAY.read_text(encoding="utf-8").splitlines()
    changes = 0
    new_lines = []

    # Track which line ranges are user-facing (around adapter.send, return statements)
    for i, line in enumerate(lines):
        stripped = line.strip()

        if should_skip_line(line):
            new_lines.append(line)
            continue

        # Pattern 1: return "string literal"
        m = re.match(r'^(\s*)return\s+"([^"]*)"$', line)
        if m:
            indent, string = m.groups()
            # Skip very short or internal strings
            if len(string) < 5 or string.startswith(('_', '{')):
                new_lines.append(line)
                continue
            # Check if it looks user-facing (has letter content, not just symbols)
            if not re.search(r'[A-Za-z一-鿿]', string):
                new_lines.append(line)
                continue
            new_lines.append(f'{indent}return i18n._("{string}")')
            changes += 1
            continue

        # Pattern 2: return f"string with {vars}"
        m = re.match(r'^(\s*)return\s+f"([^"]*)"$', line)
        if m:
            indent, fstring = m.groups()
            if len(fstring) < 5:
                new_lines.append(line)
                continue
            if not re.search(r'[A-Za-z一-鿿]', fstring):
                new_lines.append(line)
                continue
            vars_list = extract_fstring_vars(fstring)
            if not vars_list:
                # No variables — just plain string that happens to be f-string
                new_lines.append(f'{indent}return i18n._("{fstring}")')
                changes += 1
                continue
            template, format_args = convert_fstring_to_format(fstring, vars_list)
            new_lines.append(f'{indent}return i18n._("{template}").format({format_args})')
            changes += 1
            continue

        # Pattern 3: return f'string with {vars}' (single quotes)
        m = re.match(r"^(\s*)return\s+f'([^']*)'$", line)
        if m:
            indent, fstring = m.groups()
            if len(fstring) < 5:
                new_lines.append(line)
                continue
            if not re.search(r'[A-Za-z一-鿿]', fstring):
                new_lines.append(line)
                continue
            # Escape double quotes for the i18n string
            fstring_escaped = fstring.replace('"', '\\"')
            vars_list = extract_fstring_vars(fstring)
            if not vars_list:
                new_lines.append(f'{indent}return i18n._("{fstring_escaped}")')
                changes += 1
                continue
            template, format_args = convert_fstring_to_format(fstring_escaped, vars_list)
            new_lines.append(f'{indent}return i18n._("{template}").format({format_args})')
            changes += 1
            continue

        # No match — keep original
        new_lines.append(line)

    if changes:
        GATEWAY.write_text('\n'.join(new_lines) + '\n', encoding='utf-8')

    print(f"Wrapped {changes} return statements with i18n._()")
    return changes


if __name__ == "__main__":
    process_file()
