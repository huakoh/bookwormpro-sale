#!/usr/bin/env python3
"""Extract _() msgids from run_agent.py and find missing ones in PO file."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RA = ROOT / "run_agent.py"
PO = ROOT / "locale" / "zh_CN" / "LC_MESSAGES" / "bookwormpro.po"

# Parse existing msgids from PO
existing = set()
with open(PO, encoding="utf-8") as f:
    for line in f:
        m = re.match(r'^msgid "(.*)"$', line)
        if m:
            existing.add(m.group(1))

# Extract _("...") from run_agent.py, handling multiline concatenation
source = RA.read_text(encoding="utf-8")

# Pattern: _("string literal") possibly with implicit concatenation
# We need to handle: _("part1" \n "part2" \n "part3")
pattern = re.compile(r'_\(\s*("(?:[^"\\]|\\.)*"(?:\s*"(?:[^"\\]|\\.)*")*)\s*\)')
matches = pattern.findall(source)

msgids = set()
for match in matches:
    # Join concatenated string parts: "a" "b" -> "ab"
    parts = re.findall(r'"((?:[^"\\]|\\.)*)"', match)
    full = "".join(parts)
    msgids.add(full)

missing = sorted(msgids - existing)
print(f"Total _() msgids in run_agent.py: {len(msgids)}")
print(f"Already in PO: {len(msgids) - len(missing)}")
print(f"Missing from PO: {len(missing)}")
print()
for m in missing:
    print(f'  "{m}"')
