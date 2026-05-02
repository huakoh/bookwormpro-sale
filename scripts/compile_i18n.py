#!/usr/bin/env python3
"""
BookwormPRO i18n -- Compile .po to .mo binary file.

Usage: python scripts/compile_i18n.py
"""

import struct
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOCALE_DIR = PROJECT_ROOT / "locale"


def _decode_po(s: str) -> str:
    """Decode PO escape sequences: \\n→newline, \\t→tab, \\\\→backslash, \\"→quote."""
    return s.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"').replace("\\\\", "\\")


def compile_po(po_path: Path, mo_path: Path) -> int:
    """Compile a .po file to .mo binary. Returns entry count."""
    content = po_path.read_text(encoding="utf-8")

    entries: dict[str, str] = {}
    lines = content.split("\n")
    msgid: str | None = None
    msgstr: str | None = None
    in_msgid = False
    in_msgstr = False

    for line in lines:
        if line.startswith('msgid "'):
            if msgid is not None and msgid:
                entries[_decode_po(msgid)] = _decode_po(msgstr or "")
            msgid = line[7:-1]
            msgstr = ""
            in_msgid = True
            in_msgstr = False
        elif line.startswith('msgstr "'):
            msgstr = line[8:-1]
            in_msgid = False
            in_msgstr = True
        elif line.startswith('"') and in_msgid:
            msgid += line[1:-1]
        elif line.startswith('"') and in_msgstr:
            msgstr += line[1:-1]

    if msgid is not None and msgid:
        entries[_decode_po(msgid)] = _decode_po(msgstr or "")

    # Remove empty header entry
    non_empty = {k: v for k, v in entries.items() if k}
    if not non_empty:
        return 0

    keys = sorted(non_empty.keys())
    N = len(keys) + 1  # +1 for empty header entry

    # Calculate offsets
    HEADER = 28
    O_TABLE = HEADER                          # original strings table
    T_TABLE = HEADER + N * 8                  # translation strings table
    HASH_SIZE = 0
    STRING_START = HEADER + 2 * N * 8         # string data begins here

    # Build string data area
    data = bytearray()
    orig_pos = []   # (offset_in_data, length)
    trans_pos = []  # (offset_in_data, length)

    # Header entry (empty string)
    orig_pos.append((len(data), 1))
    data.extend(b"\x00")
    trans_pos.append((len(data), 1))
    data.extend(b"\x00")

    for key in keys:
        val = non_empty[key]
        key_bytes = key.encode("utf-8") + b"\x00"
        val_bytes = val.encode("utf-8") + b"\x00"

        orig_pos.append((len(data), len(key_bytes)))
        data.extend(key_bytes)

        trans_pos.append((len(data), len(val_bytes)))
        data.extend(val_bytes)

    # Build .mo binary
    result = bytearray()
    result.extend(struct.pack("<I", 0x950412DE))  # magic
    result.extend(struct.pack("<I", 0))            # version
    result.extend(struct.pack("<I", N))            # count
    result.extend(struct.pack("<I", O_TABLE))      # original table offset
    result.extend(struct.pack("<I", T_TABLE))      # translation table offset
    result.extend(struct.pack("<I", HASH_SIZE))    # hash table size
    result.extend(struct.pack("<I", STRING_START)) # hash table offset (=string_start)

    for off, length in orig_pos:
        result.extend(struct.pack("<I", length))
        result.extend(struct.pack("<I", STRING_START + off))

    for off, length in trans_pos:
        result.extend(struct.pack("<I", length))
        result.extend(struct.pack("<I", STRING_START + off))

    result.extend(data)

    mo_path.parent.mkdir(parents=True, exist_ok=True)
    mo_path.write_bytes(bytes(result))
    return len(non_empty)


def main():
    po_path = LOCALE_DIR / "zh_CN" / "LC_MESSAGES" / "bookwormpro.po"
    mo_path = LOCALE_DIR / "zh_CN" / "LC_MESSAGES" / "bookwormpro.mo"

    if not po_path.exists():
        print(f"[i18n] ERROR: {po_path} not found")
        sys.exit(1)

    count = compile_po(po_path, mo_path)
    print(f"[i18n] Compiled {count} entries -> {mo_path}")


if __name__ == "__main__":
    main()
