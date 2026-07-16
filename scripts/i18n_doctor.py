"""
Transform doctor.py for i18n: add import, modify helpers, convert f-strings.
"""
import re

path = r"C:\Users\leesu\BookwormPRO\bwm_cli\doctor.py"
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# === Step 1: Add i18n import ===
old_import = "from bwm_cli.models import _HERMES_USER_AGENT"
new_import = "from bwm_cli.i18n import _\nfrom bwm_cli.models import _HERMES_USER_AGENT"
if "from bwm_cli.i18n import _" not in content:
    content = content.replace(old_import, new_import)

# === Step 2: Modify helper functions to auto-translate ===
# check_ok
old = '''def check_ok(text: str, detail: str = ""):
    print(f"  {color('[成功]', Colors.GREEN)} {text}" + (f" {color(detail, Colors.DIM)}" if detail else ""))'''
new = '''def check_ok(text: str, detail: str = ""):
    print(f"  {color('[成功]', Colors.GREEN)} {_(text)}" + (f" {color(_(detail), Colors.DIM)}" if detail else ""))'''
content = content.replace(old, new)

# check_warn
old = '''def check_warn(text: str, detail: str = ""):
    print(f"  {color('[警告]', Colors.YELLOW)} {text}" + (f" {color(detail, Colors.DIM)}" if detail else ""))'''
new = '''def check_warn(text: str, detail: str = ""):
    print(f"  {color('[警告]', Colors.YELLOW)} {_(text)}" + (f" {color(_(detail), Colors.DIM)}" if detail else ""))'''
content = content.replace(old, new)

# check_fail
old = '''def check_fail(text: str, detail: str = ""):
    print(f"  {color('[失败]', Colors.RED)} {text}" + (f" {color(detail, Colors.DIM)}" if detail else ""))'''
new = '''def check_fail(text: str, detail: str = ""):
    print(f"  {color('[失败]', Colors.RED)} {_(text)}" + (f" {color(_(detail), Colors.DIM)}" if detail else ""))'''
content = content.replace(old, new)

# check_info
old = '''def check_info(text: str):
    print(f"    {color('→', Colors.CYAN)} {text}")'''
new = '''def check_info(text: str):
    print(f"    {color('→', Colors.CYAN)} {_(text)}")'''
content = content.replace(old, new)

# === Step 3: Convert f-string check_* calls to .format() ===
# Pattern: check_xxx(f"...{var}...") or check_xxx(f"...{var}...", f"...{var2}...")
# This is complex. We'll do key patterns manually.

replacements = [
    # Section headers (color() calls)
    ('print(color("◆ Gateway Service"', 'print(color(_("◆ Gateway Service")'),
    ('print(color("◆ Runtime Filesystem Capability"', 'print(color(_("◆ Runtime Filesystem Capability")'),
    ('print(color("◆ Persistent Memory"', 'print(color(_("◆ Persistent Memory")'),
    ('print(color("◆ Prompt Cache Freshness"', 'print(color(_("◆ Prompt Cache Freshness")'),
    ('print(color("◆ Python Environment"', 'print(color(_("◆ Python Environment")'),
    ('print(color("◆ Required Packages"', 'print(color(_("◆ Required Packages")'),
    ('print(color("◆ Configuration Files"', 'print(color(_("◆ Configuration Files")'),
    ('print(color("◆ Config Structure"', 'print(color(_("◆ Config Structure")'),
    ('print(color("◆ Auth Providers"', 'print(color(_("◆ Auth Providers")'),
    ('print(color("◆ Directory Structure"', 'print(color(_("◆ Directory Structure")'),
    ('print(color("◆ Command Installation"', 'print(color(_("◆ Command Installation")'),
    ('print(color("◆ External Tools"', 'print(color(_("◆ External Tools")'),
    ('print(color("◆ API Connectivity"', 'print(color(_("◆ API Connectivity")'),
    ('print(color("◆ Plugin System"', 'print(color(_("◆ Plugin System")'),
    
    # Doctor header
    ('[体检] BookwormPRO Doctor', '[体检] BookwormPRO Doctor'),  # already Chinese, keep
    
    # Static check calls
    ('check_ok("Systemd linger enabled", "(gateway service survives logout)")', 
     'check_ok("Systemd linger enabled", "(gateway service survives logout)")'),
    ('check_warn("Systemd linger disabled", "(gateway may stop after logout)")',
     'check_warn("Systemd linger disabled", "(gateway may stop after logout)")'),
    ('check_info("Run: sudo loginctl enable-linger $USER")',
     'check_info("Run: sudo loginctl enable-linger $USER")'),  # command, keep as-is
    ('check_warn("Could not verify systemd linger"',
     'check_warn("Could not verify systemd linger"'),
    ('check_warn("Could not import runtime detectors"',
     'check_warn("Could not import runtime detectors"'),
    ('check_ok("Native install — full host filesystem access",\n                 "(no sandbox; tools run as your user)")',
     'check_ok("Native install — full host filesystem access",\n                 "(no sandbox; tools run as your user)")'),
    ('check_ok("Host bridge mounted",\n                 "(/host/desktop and /host/workspace are read-write)")',
     'check_ok("Host bridge mounted",\n                 "(/host/desktop and /host/workspace are read-write)")'),
    ('check_warn("Container runtime without host bridge",\n                   "(only /opt/data is writable)")',
     'check_warn("Container runtime without host bridge",\n                   "(only /opt/data is writable)")'),
    ('check_info("To allow Desktop access: see docs/host-bridge.md")',
     'check_info("To allow Desktop access: see docs/host-bridge.md")'),
    ('check_info("Runtime: unknown environment shape")',
     'check_info("Runtime: unknown environment shape")'),
    ('check_info("WSL detected — Windows host visible at /mnt/c/")',
     'check_info("WSL detected — Windows host visible at /mnt/c/")'),
    ('check_warn("Could not resolve BOOKWORMPRO_HOME"',
     'check_warn("Could not resolve BOOKWORMPRO_HOME"'),
    
    # API connectivity
    ('print("  Checking OpenRouter API...", end=""',
     'print("  " + _("Checking OpenRouter API..."), end=""'),
    ('print("  Checking Anthropic API...", end=""',
     'print("  " + _("Checking Anthropic API..."), end=""'),
]

for old_str, new_str in replacements:
    if old_str != new_str:  # Skip identity replacements
        content = content.replace(old_str, new_str)

# === Step 4: Handle f-string check_* calls (batch conversion) ===
# Convert pattern: check_xxx(f"text {var} more") 
# → check_xxx(_("text {var} more").format(var=var))
# This regex-based approach handles simple cases

def convert_fstring_check(match):
    """Convert a f-string check_* call to .format() + _()"""
    func = match.group(1)  # check_ok, check_warn, etc.
    indent = match.group(2) or ''
    fstring = match.group(3)  # the f-string content
    
    # Extract variable names from {var} patterns
    # Simple case: {var_name} or {var.attr}
    vars_used = re.findall(r'\{([a-zA-Z_][a-zA-Z0-9_.]*)(?::[^}]*)?\}', fstring)
    
    # Build the template (replace {var} with {var})
    template = re.sub(r'\{([a-zA-Z_][a-zA-Z0-9_.]*)', r'{\1}', fstring)
    
    if vars_used:
        format_args = ', '.join(f'{v}={v}' for v in set(vars_used))
        return f'{indent}{func}(_("""{template}""").format({format_args}))'
    else:
        return f'{indent}{func}(_("""{template}"""))'

# Actually, regex-based f-string conversion is too fragile. 
# Let's just report what needs manual conversion.

print("=== doctor.py transformation complete ===")
print("Helper functions modified to auto-translate.")
print("Static strings and section headers wrapped.")
print("MANUAL REVIEW NEEDED for f-string check_* calls (see below):")
print()

# List remaining f-string calls
for i, line in enumerate(content.split('\n'), 1):
    if re.search(r'check_\w+\(f"', line):
        print(f"  L{i}: {line.strip()[:100]}")

with open(path, 'w', encoding='utf-8', newline='') as f:
    f.write(content)

print("\nFile written. Checking syntax...")
import py_compile
try:
    py_compile.compile(path, doraise=True)
    print("Syntax OK")
except py_compile.PyCompileError as e:
    print(f"SYNTAX ERROR: {e}")
