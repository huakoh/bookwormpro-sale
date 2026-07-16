import re

po_path = r"C:\Users\leesu\BookwormPRO\locale\zh_CN\LC_MESSAGES\bookwormpro.po"
with open(po_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Translations to add (before the last existing entry or at the end of sections)
new_entries = '''
# ─── model_tools.py ───
msgid "no tools"
msgstr "无工具"

msgid "[成功] Enabled toolset '{toolset}': {tools}"
msgstr "[成功] 已启用工具集 '{toolset}'：{tools}"

msgid "[成功] Enabled legacy toolset '{toolset}': {tools}"
msgstr "[成功] 已启用旧版工具集 '{toolset}'：{tools}"

msgid "[警告] Unknown toolset: {toolset}"
msgstr "[警告] 未知工具集：{toolset}"

msgid "🚫 Disabled toolset '{toolset}': {tools}"
msgstr "🚫 已禁用工具集 '{toolset}'：{tools}"

msgid "🚫 Disabled legacy toolset '{toolset}': {tools}"
msgstr "🚫 已禁用旧版工具集 '{toolset}'：{tools}"

msgid "[工具] Final tool selection ({count} tools): {tools}"
msgstr "[工具] 最终工具选择（{count} 个工具）：{tools}"

msgid "[工具] No tools selected (all filtered out or unavailable)"
msgstr "[工具] 未选择工具（全部被过滤或不可用）"
'''

# Insert before the last blank-line-terminated section
# Find a good insertion point - before a known section header or at end
insert_marker = '# ─── 通用 ───'
if insert_marker in content:
    content = content.replace(insert_marker, new_entries + '\n' + insert_marker)
else:
    content += '\n' + new_entries

with open(po_path, 'w', encoding='utf-8', newline='') as f:
    f.write(content)

print("Entries added. Counting...")

# Count entries
msgid_count = content.count('\nmsgid "')
print(f"Total msgid entries: {msgid_count}")
