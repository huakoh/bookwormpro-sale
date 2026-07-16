"""
Safe i18n for doctor.py: add import + auto-translate helpers only.
F-strings pass through _(...) as-is (display in English until manually converted).
"""
import re

path = r"C:\Users\leesu\BookwormPRO\bwm_cli\doctor.py"
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Step 1: Add import
old = "from bwm_cli.models import _HERMES_USER_AGENT"
new = "from bwm_cli.i18n import _\nfrom bwm_cli.models import _HERMES_USER_AGENT"
if "from bwm_cli.i18n import _" not in content:
    content = content.replace(old, new, 1)
    print("Import added.")

# Step 2: Modify helpers to auto-translate text param
# check_ok
old = 'def check_ok(text: str, detail: str = ""):\n    print(f"  {color(\'[成功]\', Colors.GREEN)} {text}" + (f" {color(detail, Colors.DIM)}" if detail else ""))'
new = 'def check_ok(text: str, detail: str = ""):\n    print(f"  {color(\'[成功]\', Colors.GREEN)} {_(text)}" + (f" {color(_(detail), Colors.DIM)}" if detail else ""))'
cnt = content.count(old)
content = content.replace(old, new)
print(f"check_ok: {cnt} occurrence(s) modified")

# check_warn
old = 'def check_warn(text: str, detail: str = ""):\n    print(f"  {color(\'[警告]\', Colors.YELLOW)} {text}" + (f" {color(detail, Colors.DIM)}" if detail else ""))'
new = 'def check_warn(text: str, detail: str = ""):\n    print(f"  {color(\'[警告]\', Colors.YELLOW)} {_(text)}" + (f" {color(_(detail), Colors.DIM)}" if detail else ""))'
cnt = content.count(old)
content = content.replace(old, new)
print(f"check_warn: {cnt} occurrence(s) modified")

# check_fail
old = 'def check_fail(text: str, detail: str = ""):\n    print(f"  {color(\'[失败]\', Colors.RED)} {text}" + (f" {color(detail, Colors.DIM)}" if detail else ""))'
new = 'def check_fail(text: str, detail: str = ""):\n    print(f"  {color(\'[失败]\', Colors.RED)} {_(text)}" + (f" {color(_(detail), Colors.DIM)}" if detail else ""))'
cnt = content.count(old)
content = content.replace(old, new)
print(f"check_fail: {cnt} occurrence(s) modified")

# check_info
old = 'def check_info(text: str):\n    print(f"    {color(\'→\', Colors.CYAN)} {text}")'
new = 'def check_info(text: str):\n    print(f"    {color(\'→\', Colors.CYAN)} {_(text)}")'
cnt = content.count(old)
content = content.replace(old, new)
print(f"check_info: {cnt} occurrence(s) modified")

with open(path, 'w', encoding='utf-8', newline='') as f:
    f.write(content)

print("\nChecking syntax...")
import py_compile
try:
    py_compile.compile(path, doraise=True)
    print("Syntax OK ✓")
except py_compile.PyCompileError as e:
    print(f"SYNTAX ERROR: {e}")
