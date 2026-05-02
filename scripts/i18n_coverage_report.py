#!/usr/bin/env python3
"""Generate i18n coverage report for bwm_cli directory."""
import re
import glob
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
files = sorted(glob.glob(str(ROOT / "bwm_cli" / "*.py")))

total_wrapped = 0
total_unwrapped = 0
unwrapped_files = []

for f in files:
    text = Path(f).read_text(encoding="utf-8")
    lines = text.splitlines()
    wrapped = 0
    unwrapped = 0
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith('"""') or s.startswith("'''"):
            continue
        if "logger." in s or "logging." in s:
            continue
        if "parser." in s or "add_argument" in s or "help=" in s:
            continue

        has_i18n = bool(re.search(r'\b_\(', s) or re.search(r'i18n\.\s*_\(', s))
        has_raw_print = bool(re.search(r'(print|input)\(f?["\']', s))
        # Exclude separator/box-drawing lines (no translatable text)
        is_separator = bool(re.search(r'^(print|c\.print)\(f?["\'][─━═│┌┐└┘├┤┬┴┼╔╗╚╝\-=*#~\s]*["\'](\s*\*\s*\d+)?\)', s))
        if is_separator:
            has_raw_print = False

        if has_i18n:
            wrapped += 1
        if has_raw_print and not has_i18n:
            unwrapped += 1

    total_wrapped += wrapped
    total_unwrapped += unwrapped
    if unwrapped > 0:
        name = Path(f).name
        unwrapped_files.append((name, unwrapped))

print(f"=== bwm_cli i18n Coverage Report ===")
print(f"Total wrapped _() lines: {total_wrapped}")
print(f"Remaining unwrapped print/input: {total_unwrapped}")
coverage = total_wrapped / (total_wrapped + total_unwrapped) * 100 if (total_wrapped + total_unwrapped) > 0 else 100
print(f"Coverage: {coverage:.1f}%")
print()
if unwrapped_files:
    print("Files with remaining unwrapped strings:")
    for name, count in sorted(unwrapped_files, key=lambda x: -x[1]):
        print(f"  {name}: {count}")
else:
    print("All files fully covered!")
