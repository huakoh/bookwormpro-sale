#!/usr/bin/env python3
"""Debug: show what the 538 skipped entries look like."""
import re
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from fill_po_translations import get_translation

po = Path("locale/zh_CN/LC_MESSAGES/bookwormpro.po").read_text(encoding="utf-8")
lines = po.splitlines()

skipped = []
filled_auto = []
filled_table = []

i = 0
while i < len(lines):
    line = lines[i]
    msgid_m = re.match(r'^msgid "(.+)"$', line)
    if msgid_m and i + 1 < len(lines):
        next_line = lines[i + 1]
        if re.match(r'^msgstr ""$', next_line):
            msgid = msgid_m.group(1)
            t = get_translation(msgid)
            if t is None:
                skipped.append(msgid)
            elif t == msgid:
                filled_auto.append(msgid)
            else:
                filled_table.append((msgid, t))
    i += 1

print(f"Table translations: {len(filled_table)}")
print(f"Auto-fill (CN passthrough): {len(filled_auto)}")
print(f"Skipped (English, left empty): {len(skipped)}")
print()
print("=== First 20 SKIPPED (English strings left empty) ===")
for m in skipped[:20]:
    print(f"  {repr(m[:70])}")
print()
print("=== First 10 AUTO-FILL (CN passthrough) ===")
for m in filled_auto[:10]:
    print(f"  {repr(m[:70])}")
