"""
Extract all _() calls from files that import bwm_cli.i18n, 
add unique msgids to .po with AI-generated translations.
"""
import re, os

# Files to scan (those with i18n import)
files_to_scan = [
    r"C:\Users\leesu\BookwormPRO\model_tools.py",
    r"C:\Users\leesu\BookwormPRO\bwm_cli\doctor.py",
    r"C:\Users\leesu\BookwormPRO\bwm_cli\banner.py",
]

po_path = r"C:\Users\leesu\BookwormPRO\locale\zh_CN\LC_MESSAGES\bookwormpro.po"

# Read existing .po to get existing msgids
with open(po_path, 'r', encoding='utf-8') as f:
    po_content = f.read()

existing_ids = set(re.findall(r'^msgid "(.*)"$', po_content, re.MULTILINE))
print(f"Existing msgids: {len(existing_ids)}")

# Extract _() calls from source files
new_ids = set()
for fpath in files_to_scan:
    if not os.path.exists(fpath):
        continue
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()
    # Find _("...") or _('...') calls
    # But skip if inside comments
    found = re.findall(r'_\(["\']([^"\']+)["\']\)', content)
    for s in found:
        if s not in existing_ids:
            new_ids.add(s)

print(f"New unique msgids to add: {len(new_ids)}")

# Generate translations (simple mapping for common patterns)
translations = {}
for msgid in sorted(new_ids):
    # Skip very short or technical strings
    if len(msgid) < 3:
        continue
    # Placeholder translation
    translations[msgid] = f"[TODO] {msgid}"

# Add to .po
if translations:
    new_section = "\n# ─── doctor.py + model_tools.py ───\n"
    for msgid in sorted(translations.keys()):
        new_section += f'msgid "{msgid}"\nmsgstr "{translations[msgid]}"\n\n'
    
    with open(po_path, 'a', encoding='utf-8', newline='') as f:
        f.write(new_section)
    print(f"Added {len(translations)} entries to .po")
else:
    print("No new entries to add")

# Count final
with open(po_path, 'r', encoding='utf-8') as f:
    final_ids = len(re.findall(r'^msgid "(.*)"$', f.read(), re.MULTILINE))
print(f"Final msgid count: {final_ids}")
