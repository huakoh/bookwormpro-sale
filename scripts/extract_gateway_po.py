#!/usr/bin/env python3
"""Extract i18n._() msgids from gateway/run.py and find missing ones in PO file."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GW = ROOT / "gateway" / "run.py"
PO = ROOT / "locale" / "zh_CN" / "LC_MESSAGES" / "bookwormpro.po"

existing = set()
with open(PO, encoding="utf-8") as f:
    for line in f:
        m = re.match(r'^msgid "(.*)"$', line)
        if m:
            existing.add(m.group(1))

source = GW.read_text(encoding="utf-8")

# Match i18n._("..." possibly with implicit concatenation "...")
pattern = re.compile(r'i18n\._\(\s*("(?:[^"\\]|\\.)*"(?:\s*"(?:[^"\\]|\\.)*")*)\s*\)')
matches = pattern.findall(source)

msgids = set()
for match in matches:
    parts = re.findall(r'"((?:[^"\\]|\\.)*)"', match)
    full = "".join(parts)
    msgids.add(full)

missing = sorted(msgids - existing)
print(f"Total i18n._() msgids in gateway/run.py: {len(msgids)}")
print(f"Already in PO: {len(msgids) - len(missing)}")
print(f"Missing from PO: {len(missing)}")
print()
for m in missing:
    print(f'  "{m}"')
