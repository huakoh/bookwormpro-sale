#!/usr/bin/env python3
"""
Bulk i18n wrapper for print()/input() calls in bwm_cli .py files.

Handles:
1. print("text") → print(_("text"))
2. print(f"text {var}") → print(_("text {var}").format(var=var))
3. print(f"...", file=sys.stderr) → print(_("...").format(...), file=sys.stderr)
4. input("prompt") → input(_("prompt"))
5. input(f"prompt {var}") → input(_("prompt {var}").format(var=var))

Adds `from bwm_cli.i18n import _` if not present.
Outputs PO entries to stdout.

Usage:
    python scripts/i18n_wrap_prints.py <file.py> [--dry-run]
"""
import re
import sys
from pathlib import Path


def extract_fstring_vars(s: str) -> list[tuple[str, str, str]]:
    """Extract (full_expr, base_name, format_spec) from f-string {placeholders}.

    For {var:fmt}, full_expr='var:fmt', base_name='var', format_spec=':fmt'.
    For {var}, full_expr='var', base_name='var', format_spec=''.
    """
    placeholders = re.findall(r'\{([^{}]+)\}', s)
    result = []
    for ph in placeholders:
        # Split on first ':' that's a format spec — skip ':' inside [] or ()
        colon_pos = -1
        depth = 0
        for ci, ch in enumerate(ph):
            if ch in '([':
                depth += 1
            elif ch in ')]':
                depth -= 1
            elif ch == ':' and depth == 0:
                colon_pos = ci
                break
        if colon_pos > 0:
            expr_part = ph[:colon_pos]
            fmt_spec = ph[colon_pos:]
        else:
            expr_part = ph
            fmt_spec = ''
        base = re.match(r'([a-zA-Z_]\w*)', expr_part)
        if base:
            result.append((ph, base.group(1), fmt_spec))
    return result


def convert_fstring_to_format(fstring_content: str, var_expressions: list[tuple[str, str, str]]) -> tuple[str, str]:
    """Convert f-string to _("template").format(key=expr) pattern.

    Format specs (like :<34s) are preserved in the template placeholder,
    only the variable name goes into .format() args.
    """
    template = fstring_content
    format_parts = []
    seen = {}

    for expr, base, fmt_spec in var_expressions:
        # The expression without format spec for the .format() argument
        expr_no_fmt = expr[:len(expr) - len(fmt_spec)] if fmt_spec else expr

        if expr_no_fmt == base:
            # Simple variable — keep {var:fmt} in template, add var=var to format
            if base not in seen:
                format_parts.append(f"{base}={base}")
                seen[base] = True
        elif re.match(r'^[a-zA-Z_]\w*\.\w+$', expr_no_fmt):
            safe_key = expr_no_fmt.replace('.', '_')
            template = template.replace('{' + expr + '}', '{' + safe_key + fmt_spec + '}')
            if safe_key not in seen:
                format_parts.append(f"{safe_key}={expr_no_fmt}")
                seen[safe_key] = True
        else:
            key = base
            suffix = 0
            while key in seen and seen[key] != expr_no_fmt:
                suffix += 1
                key = f"{base}_{suffix}"
            template = template.replace('{' + expr + '}', '{' + key + fmt_spec + '}')
            if key not in seen:
                format_parts.append(f"{key}={expr_no_fmt}")
                seen[key] = expr_no_fmt

    return template, ', '.join(format_parts)


SKIP_PATTERNS = [
    r'\b_\(',               # already wrapped
    r'i18n\._\(',           # already wrapped (gateway style)
    r'logger\.',            # logger calls
    r'logging\.',           # logging calls
    r'^\s*#',              # comments
    r'^\s*"""',            # docstrings
    r"^\s*'''",            # docstrings
    r'\.write\(',          # file.write
    r'subprocess\.',       # subprocess calls
    r'os\.environ',        # env var access
    r'\.set_description\(', # tqdm
    r'argparse\.',         # argparse
    r'parser\.',           # argparse
    r'add_argument\(',     # argparse
    r'add_subparsers\(',   # argparse
    r'set_defaults\(',     # argparse
    r'help=',              # argparse help strings (handled by commands.py)
    r'metavar=',           # argparse
    r'\\"',                # escaped quotes — regex can't parse correctly
    r"\\'",                # escaped single quotes
    r'\[:\d+\]',           # slice expressions in f-strings
    r'!\w\}',              # conversion flags like !r, !s in f-strings
]


def should_skip(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    return any(re.search(pat, stripped) for pat in SKIP_PATTERNS)


def is_user_facing(s: str) -> bool:
    """Check if string content is user-facing (has readable text, not just symbols)."""
    if len(s) < 2:
        return False
    # Must contain letters (ASCII or CJK)
    if not re.search(r'[A-Za-z一-鿿]', s):
        return False
    # Skip private/internal Python identifiers
    if s.startswith('_'):
        return False
    # Strip {var} placeholders — after stripping, must still have user-visible text
    stripped = re.sub(r'\{[^}]*\}', '', s).strip()
    if len(stripped) < 2 or not re.search(r'[A-Za-z一-鿿]', stripped):
        return False
    # Skip pure technical paths/URLs
    if stripped.startswith(('/', 'http', '%')):
        return False
    return True


def wrap_string_in_line(line: str) -> tuple[str, str | None]:
    """Try to wrap a user-facing string in a line. Returns (new_line, msgid_or_None)."""

    # Pattern: print("text") or print("text", file=...)
    m = re.match(r'^(\s*)(print|input)\(("([^"]*)")(.*)\)(\s*)$', line)
    if m:
        indent, func, full_str, content, rest, trailing = m.groups()
        if not is_user_facing(content):
            return line, None
        new_line = f'{indent}{func}(_("{content}"){rest}){trailing}'
        return new_line, content

    # Pattern: print('text') or print('text', file=...)
    m = re.match(r"^(\s*)(print|input)\('([^']*)'(.*)\)(\s*)$", line)
    if m:
        indent, func, content, rest, trailing = m.groups()
        if not is_user_facing(content):
            return line, None
        escaped = content.replace('"', '\\"')
        new_line = f'{indent}{func}(_("{escaped}"){rest}){trailing}'
        return new_line, escaped

    # Pattern: print(f"text {var}") or print(f"text {var}", file=...)
    m = re.match(r'^(\s*)(print|input)\(f"([^"]*)"(.*)\)(\s*)$', line)
    if m:
        indent, func, fstring, rest, trailing = m.groups()
        if not is_user_facing(fstring):
            return line, None
        var_list = extract_fstring_vars(fstring)
        if not var_list:
            new_line = f'{indent}{func}(_("{fstring}"){rest}){trailing}'
            return new_line, fstring
        template, format_args = convert_fstring_to_format(fstring, var_list)
        new_line = f'{indent}{func}(_("{template}").format({format_args}){rest}){trailing}'
        return new_line, template

    # Pattern: print(f'text {var}') or print(f'text {var}', file=...)
    m = re.match(r"^(\s*)(print|input)\(f'([^']*)'(.*)\)(\s*)$", line)
    if m:
        indent, func, fstring, rest, trailing = m.groups()
        if not is_user_facing(fstring):
            return line, None
        escaped = fstring.replace('"', '\\"')
        var_list = extract_fstring_vars(fstring)
        if not var_list:
            new_line = f'{indent}{func}(_("{escaped}"){rest}){trailing}'
            return new_line, escaped
        template, format_args = convert_fstring_to_format(escaped, var_list)
        new_line = f'{indent}{func}(_("{template}").format({format_args}){rest}){trailing}'
        return new_line, template

    # Pattern: print(color("text", Colors.XXX))
    m = re.match(r'^(\s*)print\(color\("([^"]*)",\s*(Colors\.\w+(?:,\s*Colors\.\w+)*)\)\)(\s*)$', line)
    if m:
        indent, content, colors, trailing = m.groups()
        if not is_user_facing(content):
            return line, None
        new_line = f'{indent}print(color(_("{content}"), {colors})){trailing}'
        return new_line, content

    # Pattern: print(color(f"text {var}", Colors.XXX))
    m = re.match(r'^(\s*)print\(color\(f"([^"]*)",\s*(Colors\.\w+(?:,\s*Colors\.\w+)*)\)\)(\s*)$', line)
    if m:
        indent, fstring, colors, trailing = m.groups()
        if not is_user_facing(fstring):
            return line, None
        var_list = extract_fstring_vars(fstring)
        if not var_list:
            new_line = f'{indent}print(color(_("{fstring}"), {colors})){trailing}'
            return new_line, fstring
        template, format_args = convert_fstring_to_format(fstring, var_list)
        new_line = f'{indent}print(color(_("{template}").format({format_args}), {colors})){trailing}'
        return new_line, template

    # Pattern: var = input("text").method_chain() — assignment prefix + method chain
    m = re.match(r'^(\s*)(.*?)(input)\("([^"]*)"\)((?:\.\w+\(\))*)\s*$', line)
    if m:
        indent, prefix, func, content, suffix = m.groups()
        if not is_user_facing(content):
            return line, None
        new_line = f'{indent}{prefix}{func}(_("{content}")){suffix}'
        return new_line, content

    # Pattern: var = input(f"text {var}").method_chain() — assignment + f-string + method chain
    m = re.match(r'^(\s*)(.*?)(input)\(f"([^"]*)"\)((?:\.\w+\(\))*)\s*$', line)
    if m:
        indent, prefix, func, fstring, suffix = m.groups()
        if not is_user_facing(fstring):
            return line, None
        var_list = extract_fstring_vars(fstring)
        if not var_list:
            new_line = f'{indent}{prefix}{func}(_("{fstring}")){suffix}'
            return new_line, fstring
        template, format_args = convert_fstring_to_format(fstring, var_list)
        new_line = f'{indent}{prefix}{func}(_("{template}").format({format_args})){suffix}'
        return new_line, template

    return line, None


def add_import(lines: list[str]) -> list[str]:
    """Add `from bwm_cli.i18n import _` after the last top-level import."""
    import_line = "from bwm_cli.i18n import _"

    for line in lines:
        if import_line in line:
            return lines

    # Find last TOP-LEVEL import (no indentation)
    last_import_idx = 0
    in_multiline = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if in_multiline:
            if ')' in stripped:
                in_multiline = False
                last_import_idx = i
            continue
        if not line or line[0] in (' ', '\t'):
            continue
        if stripped.startswith(('import ', 'from ')):
            last_import_idx = i
            if '(' in stripped and ')' not in stripped:
                in_multiline = True

    new_lines = lines[:last_import_idx + 1]
    new_lines.append(import_line)
    new_lines.extend(lines[last_import_idx + 1:])
    return new_lines


def process_file(filepath: Path, dry_run: bool = False) -> tuple[int, list[str]]:
    """Process a file, wrapping user-facing strings. Returns (change_count, msgid_list)."""
    content = filepath.read_text(encoding="utf-8")
    lines = content.splitlines()

    changes = 0
    msgids = []
    new_lines = []

    for line in lines:
        if should_skip(line):
            new_lines.append(line)
            continue

        new_line, msgid = wrap_string_in_line(line)
        if msgid:
            changes += 1
            msgids.append(msgid)
        new_lines.append(new_line)

    if changes > 0:
        new_lines = add_import(new_lines)
        if not dry_run:
            filepath.write_text('\n'.join(new_lines) + '\n', encoding='utf-8')

    return changes, msgids


def generate_po_entries(msgids: list[str]) -> str:
    """Generate PO file entries for the collected msgids."""
    seen = set()
    entries = []
    for msgid in msgids:
        if msgid in seen:
            continue
        seen.add(msgid)
        escaped = msgid.replace('\\', '\\\\').replace('"', '\\"')
        entries.append(f'msgid "{escaped}"\nmsgstr ""\n')
    return '\n'.join(entries)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <file.py> [--dry-run]")
        sys.exit(1)

    filepath = Path(sys.argv[1])
    dry_run = "--dry-run" in sys.argv

    if not filepath.exists():
        print(f"File not found: {filepath}")
        sys.exit(1)

    changes, msgids = process_file(filepath, dry_run=dry_run)

    mode = "DRY-RUN" if dry_run else "APPLIED"
    print(f"[{mode}] Wrapped {changes} strings in {filepath.name}")
    print(f"Unique msgids: {len(set(msgids))}")

    if msgids:
        print("\n--- PO ENTRIES ---")
        print(generate_po_entries(msgids))
