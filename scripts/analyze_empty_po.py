#!/usr/bin/env python3
"""Analyze empty PO entries distribution."""
import re
from pathlib import Path

po = Path("locale/zh_CN/LC_MESSAGES/bookwormpro.po").read_text(encoding="utf-8")
pairs = re.findall(r'msgid "(.+?)"\nmsgstr "(.*?)"', po, re.MULTILINE)

empty = [(mid, mstr) for mid, mstr in pairs if not mstr.strip()]
filled = [(mid, mstr) for mid, mstr in pairs if mstr.strip()]

chinese_empty = [m for m, _ in empty if re.search(r"[一-鿿]", m)]
english_empty = [m for m, _ in empty if not re.search(r"[一-鿿]", m)]
mixed_empty = [m for m, _ in empty if re.search(r"[一-鿿]", m) and re.search(r"[A-Za-z]{4,}", m)]

print(f"Total pairs: {len(pairs)}")
print(f"Filled: {len(filled)}")
print(f"Empty: {len(empty)}")
print(f"  Chinese-only empty: {len(chinese_empty) - len(mixed_empty)}")
print(f"  Mixed (CN+EN) empty: {len(mixed_empty)}")
print(f"  English-only empty: {len(english_empty)}")
print()
print("Sample English-only (first 15):")
for m in english_empty[:15]:
    print(f"  {repr(m[:70])}")
print()
print("Sample Chinese-only (first 10):")
for m in chinese_empty[:10]:
    print(f"  {repr(m[:70])}")
