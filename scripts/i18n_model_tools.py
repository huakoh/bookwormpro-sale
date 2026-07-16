import re

path = r"C:\Users\leesu\BookwormPRO\model_tools.py"
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add import after toolsets import
old_import = "from toolsets import resolve_toolset, validate_toolset\n\nlogger"
new_import = "from toolsets import resolve_toolset, validate_toolset\nfrom bwm_cli.i18n import _\n\nlogger"
content = content.replace(old_import, new_import)

# 2. L229: f-string with conditional → .format()
old = """                    print(f"[成功] Enabled toolset '{toolset_name}': {', '.join(resolved) if resolved else 'no tools'}")"""
new = """                    tools_str = ', '.join(resolved) if resolved else _('no tools')
                    print(_("[成功] Enabled toolset '{toolset}': {tools}").format(toolset=toolset_name, tools=tools_str))"""
content = content.replace(old, new)

# 3. L234
old = """                    print(f"[成功] Enabled legacy toolset '{toolset_name}': {', '.join(legacy_tools)}")"""
new = """                    print(_("[成功] Enabled legacy toolset '{toolset}': {tools}").format(toolset=toolset_name, tools=', '.join(legacy_tools)))"""
content = content.replace(old, new)

# 4. L237
old = """                    print(f"[警告]  Unknown toolset: {toolset_name}")"""
new = """                    print(_("[警告] Unknown toolset: {toolset}").format(toolset=toolset_name))"""
# This appears twice - use replace with count check
count = content.count(old)
content = content.replace(old, new)
print(f"L237 pattern replaced {count} times")

# 5. L249: f-string with conditional
old = """                    print(f"\U0001f6ab Disabled toolset '{toolset_name}': {', '.join(resolved) if resolved else 'no tools'}")"""
new = """                    tools_str = ', '.join(resolved) if resolved else _('no tools')
                    print(_("\U0001f6ab Disabled toolset '{toolset}': {tools}").format(toolset=toolset_name, tools=tools_str))"""
content = content.replace(old, new)

# 6. L254
old = """                    print(f"\U0001f6ab Disabled legacy toolset '{toolset_name}': {', '.join(legacy_tools)}")"""
new = """                    print(_("\U0001f6ab Disabled legacy toolset '{toolset}': {tools}").format(toolset=toolset_name, tools=', '.join(legacy_tools)))"""
content = content.replace(old, new)

# 7. L339
old = """            print(f"[工具]  Final tool selection ({len(filtered_tools)} tools): {', '.join(tool_names)}")"""
new = """            print(_("[工具] Final tool selection ({count} tools): {tools}").format(count=len(filtered_tools), tools=', '.join(tool_names)))"""
content = content.replace(old, new)

# 8. L341
old = """            print("[工具]  No tools selected (all filtered out or unavailable)")"""
new = """            print(_("[工具] No tools selected (all filtered out or unavailable)"))"""
content = content.replace(old, new)

with open(path, 'w', encoding='utf-8', newline='') as f:
    f.write(content)

print("Done. Verifying...")

# Verify syntax
import py_compile
try:
    py_compile.compile(path, doraise=True)
    print("Syntax OK")
except py_compile.PyCompileError as e:
    print(f"SYNTAX ERROR: {e}")
