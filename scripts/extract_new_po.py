#!/usr/bin/env python3
"""Extract new msgids from wrapped files and append to PO file."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PO_PATH = ROOT / "locale" / "zh_CN" / "LC_MESSAGES" / "bookwormpro.po"

# Load existing msgids
po_text = PO_PATH.read_text(encoding="utf-8")
existing = set(re.findall(r'^msgid "(.+?)"$', po_text, re.MULTILINE))
print(f"Existing PO entries: {len(existing)}")

# Scan all bwm_cli .py files
import glob
FILES = glob.glob(str(ROOT / "bwm_cli" / "*.py"))

new_msgids = []
seen = set()

for f in FILES:
    fp = ROOT / f
    if not fp.exists():
        continue
    text = fp.read_text(encoding="utf-8")

    # Match _("...") patterns
    for m in re.finditer(r'_\("((?:[^"\\]|\\.)*)"\)', text):
        msgid = m.group(1)
        if msgid not in existing and msgid not in seen and len(msgid) > 1:
            new_msgids.append(msgid)
            seen.add(msgid)

    # Match _('...') patterns
    for m in re.finditer(r"_\('((?:[^'\\]|\\.)*)'\)", text):
        msgid = m.group(1).replace('"', '\\"')
        if msgid not in existing and msgid not in seen and len(msgid) > 1:
            new_msgids.append(msgid)
            seen.add(msgid)

print(f"New msgids to add: {len(new_msgids)}")

if new_msgids:
    # Generate PO entries
    entries = []
    for msgid in new_msgids:
        entries.append(f'\nmsgid "{msgid}"\nmsgstr ""\n')

    po_addition = "\n".join(entries)

    # Append to PO file
    with open(PO_PATH, "a", encoding="utf-8") as fh:
        fh.write("\n# ── Session 8: bwm_cli full coverage ──\n")
        fh.write(po_addition)

    print(f"Appended {len(new_msgids)} new entries to PO file")
