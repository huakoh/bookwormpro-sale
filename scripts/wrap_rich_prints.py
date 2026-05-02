#!/usr/bin/env python3
"""
Wrap c.print() / console.print() Rich markup strings with _().

Handles:
  c.print("text")          → c.print(_("text"))
  c.print(f"text {var}")   → c.print(_("text {var}").format(var=var))
  multiline string concat   → join lines, then wrap

Skips:
  c.print()                  (empty)
  c.print(variable)          (no string literal)
  c.print(Panel(...))        (complex object)
  c.print(_("..."))          (already wrapped)
  Lines with slice patterns  ([:N])
  Lines with !r flags

Usage:
    python scripts/wrap_rich_prints.py <file.py> [--dry-run]
"""
import re
import sys
from pathlib import Path


def sanitize_key(expr: str) -> str:
    """Turn an arbitrary expression into a valid Python identifier for .format() args."""
    # Keep only alphanumeric and underscore, convert everything else to '_'
    key = re.sub(r'[^a-zA-Z0-9]', '_', expr)
    key = re.sub(r'_+', '_', key).strip('_')
    if not key or not re.match(r'^[a-zA-Z_]', key):
        key = 'v_' + key
    return key[:30]


def extract_placeholders(fstring_content: str) -> list[tuple[str, str]]:
    """Return (original_expr, safe_key) for each {placeholder} in an f-string.

    Handles nested braces by tracking depth.
    """
    result = []
    i = 0
    while i < len(fstring_content):
        if fstring_content[i] == '{':
            if i + 1 < len(fstring_content) and fstring_content[i + 1] == '{':
                i += 2  # escaped brace
                continue
            # find matching close brace
            depth = 1
            j = i + 1
            while j < len(fstring_content) and depth > 0:
                if fstring_content[j] == '{':
                    depth += 1
                elif fstring_content[j] == '}':
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            expr = fstring_content[i + 1:j]
            # Separate format spec from expression
            # Find ':' at depth 0 (not inside [] () {})
            colon_pos = -1
            d = 0
            for ci, ch in enumerate(expr):
                if ch in '([{':
                    d += 1
                elif ch in ')]}':
                    d -= 1
                elif ch == ':' and d == 0:
                    colon_pos = ci
                    break
            if colon_pos > 0:
                expr_part = expr[:colon_pos]
                fmt_spec = expr[colon_pos:]  # includes the ':'
            else:
                expr_part = expr
                fmt_spec = ''
            # Determine safe key
            # If expr_part is a simple name or attr.name, we might be able to use it directly
            if re.match(r'^[a-zA-Z_]\w*(\.\w+)?$', expr_part):
                # Simple name or one level of attribute — keep as-is for format key
                # But Python .format() supports attr: "{r.name}".format(r=r) works
                # Use the top-level variable as key
                dot_pos = expr_part.find('.')
                if dot_pos > 0:
                    safe_key = expr_part[:dot_pos]  # just "r" for "r.name"
                    # Keep full attr in template: {r.name} → format(r=r)
                    # format arg is just the base var: r=r (not r=r.name)
                    result.append((expr_part + fmt_spec, safe_key, safe_key))
                else:
                    result.append((expr_part + fmt_spec, expr_part, expr_part))
            else:
                # Complex expression: map to a safe key
                safe_key = sanitize_key(expr_part)
                result.append((expr + fmt_spec if colon_pos < 0 else expr_part + fmt_spec,
                                safe_key, expr_part))
            i = j + 1
        else:
            i += 1
    return result


def convert_fstring(content: str) -> tuple[str, str]:
    """Convert f-string content to (template, format_args_str) pair.

    Template preserves format specs; format_args collects key=expr pairs.
    """
    placeholders = extract_placeholders(content)
    if not placeholders:
        return content, ''

    template = content
    seen_keys: dict[str, str] = {}  # key → expression

    for orig_with_spec, safe_key, orig_expr in placeholders:
        if safe_key not in seen_keys:
            seen_keys[safe_key] = orig_expr
        # Replace {orig_with_spec} in template with {safe_key + fmt_spec if needed}
        # For attr access like r.name → safe_key is 'r', keep {r.name} in template
        # For complex → replace with {safe_key}
        dot_pos = orig_expr.find('.')
        if re.match(r'^[a-zA-Z_]\w*(\.\w+)?$', orig_expr) and dot_pos > 0:
            # attr access: keep {r.name} in template, format(r=r)
            pass  # template stays as {r.name}
        elif re.match(r'^[a-zA-Z_]\w*$', orig_expr):
            # simple var: {name} stays as {name}
            pass
        else:
            # complex: replace {orig_with_spec} with {safe_key}
            # find format spec
            colon_match = re.search(r':[^}]+$', orig_with_spec)
            fmt_spec = colon_match.group(0) if colon_match else ''
            old_token = '{' + orig_with_spec + '}'
            new_token = '{' + safe_key + fmt_spec + '}'
            template = template.replace(old_token, new_token, 1)

    # Build format args
    fmt_args = ', '.join(f'{k}={v}' for k, v in seen_keys.items())
    return template, fmt_args


SKIP_PATTERNS_LINE = [
    r'\bc\.print\(\)',                        # empty
    r'\bc\.print\(_\(',                       # already wrapped
    r'\bc\.print\(format_',                   # function call result
    r'\bconsole\.print\(_\(',                 # already wrapped
    r'\bconsole\.print\(format_',
]

SKIP_CONTENT_PATTERNS = [
    r'\[:\d+\]',    # slice expression
    r'!\w\}',       # !r, !s, !a flags
]

SKIP_ARGS_PATTERNS = [
    r'^table$', r'^result$', r'^info_lines$', r'^preview$',
    r'^progress$', r'^metadata_lines$', r'^panel$',
]

CALL_RE = re.compile(r'^(\s*)(c\.print|console\.print)\(')


def parse_string_arg(arg_text: str) -> tuple[bool, bool, str] | None:
    """Parse a string argument. Returns (is_fstring, has_vars, content) or None."""
    t = arg_text.strip()
    if t.startswith('f"') or t.startswith("f'"):
        quote = t[1]
        content = t[2:-1]
        return True, bool(re.search(r'\{[^{}]+\}', content)), content
    elif t.startswith('"'):
        content = t[1:-1]
        return False, False, content
    elif t.startswith("'"):
        content = t[1:-1]
        return False, False, content
    return None


def collect_call(lines: list[str], start: int) -> tuple[int, str]:
    """Collect a full c.print() call, possibly spanning multiple lines.

    Returns (end_index, full_arg_text_stripped).
    Joins continuation lines into a single string then extracts the argument.
    """
    # Build combined text from start line + enough continuation lines
    # Find the opening paren position in the first line
    first = lines[start].rstrip('\n')
    call_m = CALL_RE.match(first)
    open_pos = call_m.end() - 1  # absolute position of '(' in first line

    # Accumulate lines until parens balance
    combined = first
    end_i = start
    i = start + 1
    while i < len(lines):
        depth = combined.count('(') - combined.count(')')
        if depth <= 0:
            break
        combined += ' ' + lines[i].rstrip('\n').strip()
        end_i = i
        i += 1
    # Also check final balance
    # Now find the matching close paren starting at open_pos
    depth = 0
    for ci in range(open_pos, len(combined)):
        ch = combined[ci]
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                return end_i, combined[open_pos + 1:ci].strip()

    return start, ''


def process_file(path: Path, dry_run: bool = False) -> tuple[int, list[str]]:
    """Process a file. Returns (change_count, po_entries)."""
    with open(path, encoding='utf-8') as f:
        lines = f.readlines()

    new_lines = []
    po_entries = []
    changes = 0
    i = 0

    while i < len(lines):
        line = lines[i]
        m = CALL_RE.match(line)

        if not m:
            new_lines.append(line)
            i += 1
            continue

        # Skip known non-string patterns
        if any(re.search(p, line) for p in SKIP_PATTERNS_LINE):
            new_lines.append(line)
            i += 1
            continue

        indent = m.group(1)
        call_fn = m.group(2)

        # Collect the full call
        end_i, arg_text = collect_call(lines, i)

        # Check if arg is a plain variable (no quotes)
        if not arg_text or any(re.match(p, arg_text) for p in SKIP_ARGS_PATTERNS):
            for li in range(i, end_i + 1):
                new_lines.append(lines[li])
            i = end_i + 1
            continue

        # Check if it's a string literal (or concatenated string literals)
        # Strip all string pieces
        pieces = []
        has_fstring = False
        remaining = arg_text
        is_all_strings = True

        while remaining:
            remaining = remaining.strip()
            if not remaining:
                break
            parsed = None
            for prefix, fstr in [('f"', True), ("f'", True), ('"', False), ("'", False)]:
                if remaining.startswith(prefix):
                    q = prefix[-1]
                    # Find closing quote (not escaped)
                    k = len(prefix)
                    while k < len(remaining):
                        if remaining[k] == '\\':
                            k += 2
                            continue
                        if remaining[k] == q:
                            break
                        k += 1
                    content = remaining[len(prefix):k]
                    pieces.append((fstr, content))
                    remaining = remaining[k + 1:].strip()
                    if fstr:
                        has_fstring = True
                    parsed = True
                    break
            if not parsed:
                is_all_strings = False
                break

        if not is_all_strings or not pieces:
            for li in range(i, end_i + 1):
                new_lines.append(lines[li])
            i = end_i + 1
            continue

        # Join all pieces into one combined string
        combined = ''.join(content for _, content in pieces)

        # Check skip content patterns
        if any(re.search(p, combined) for p in SKIP_CONTENT_PATTERNS):
            for li in range(i, end_i + 1):
                new_lines.append(lines[li])
            i = end_i + 1
            continue

        # Wrap
        if has_fstring and '{' in combined:
            template, fmt_args = convert_fstring(combined)
            if fmt_args:
                new_arg = f'_("{template}").format({fmt_args})'
            else:
                new_arg = f'_("{template}")'
            po_entries.append(template)
        else:
            new_arg = f'_("{combined}")'
            po_entries.append(combined)

        new_line = f'{indent}{call_fn}({new_arg})\n'
        new_lines.append(new_line)
        changes += 1
        i = end_i + 1
        continue

    if not dry_run and changes > 0:
        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

    return changes, po_entries


if __name__ == '__main__':
    args = sys.argv[1:]
    dry_run = '--dry-run' in args
    files = [a for a in args if not a.startswith('--')]

    if not files:
        print('Usage: python scripts/wrap_rich_prints.py <file.py> [--dry-run]')
        sys.exit(1)

    for fp in files:
        path = Path(fp)
        n, entries = process_file(path, dry_run=dry_run)
        print(f'{"[DRY-RUN] " if dry_run else ""}Wrapped {n} c.print() calls in {path.name}',
              file=sys.stderr)
        for entry in entries:
            print(f'\nmsgid "{entry}"\nmsgstr ""')
