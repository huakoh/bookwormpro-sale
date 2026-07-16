#!/usr/bin/env python3
"""Scan gateway/ and agent/ for i18n-relevant user-facing strings."""
import os, re, sys

def scan_file(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    lines = content.split('\n')
    
    r = {
        'file': filepath, 'lines': len(lines),
        'has_i18n_import': False, 'i18n_import_line': None,
        'underscore_used': False, '_conflict': False,
        'fstring_count': 0, 'user_patterns': [], 'str_est': 0, 'priority': 'low'
    }
    
    for i, line in enumerate(lines, 1):
        if 'bwm_cli.i18n' in line:
            r['has_i18n_import'] = True
            r['i18n_import_line'] = i
        if re.search(r'\b_\(', line) and not line.strip().startswith('#'):
            if '_ =' not in line and 'def _(' not in line:
                r['underscore_used'] = True
    
    for line in lines:
        stripped = line.strip()
        if re.search(r'\b_\s*=\s*', stripped) and not stripped.startswith('#'):
            if 'for _ in' not in stripped:
                r['_conflict'] = True
                break
    
    r['fstring_count'] = len(re.findall(r'f["\']', content))
    
    pat_cfg = [
        ('send_message', r'\.send_message\('),
        ('reply', r'\.reply\('),
        ('respond', r'\.respond\('),
        ('send_text', r'\.send_text\('),
        ('Embed', r'Embed\('),
        ('print_str', r'print\(f?["\']'),
        ('return_str', r'return\s+f?["\']'),
        ('raise_msg', r'raise\s+\w+\(f?["\']'),
        ('button', r'(?:InlineKeyboard)?Button\('),
        ('markdown', r'markdown'),
        ('notify', r'\.notify\('),
        ('format_msg', r'format_message\('),
        ('msg_var', r'(?:message|msg|content|text|body)\s*=\s*f?["\']'),
        ('error_var', r'error_msg\s*=\s*f?["\']'),
        ('help_var', r'help_text\s*=\s*f?["\']'),
        ('description', r'description\s*=\s*f?["\']'),
        ('title_var', r'title\s*=\s*f?["\']'),
        ('TextNotification', r'TextNotification\('),
        ('stream_update', r'stream_update\('),
        ('status_msg', r'status_msg'),
        ('/slash_cmd', r'(?:"|\')/(?:start|help|config|status|stop|restart)'),
        ('error_log', r'logger\.(?:error|warning)\(f?["\']'),
        ('info_log', r'logger\.info\(f?["\']'),
    ]
    for name, pat in pat_cfg:
        c = len(re.findall(pat, content))
        if c > 0:
            r['user_patterns'].append(f'{name}:{c}')
    
    r['str_est'] = len(re.findall(
        r'(?:send_message|reply|respond|send_text|update|notify|say)\(',
        content
    ))
    
    total = len(r['user_patterns'])
    if r['str_est'] > 20 or total > 15:
        r['priority'] = 'high'
    elif r['str_est'] > 5 or total > 8:
        r['priority'] = 'medium'
    return r

def walk_dir(d):
    files = []
    for root, dirs, filenames in os.walk(d):
        for fn in filenames:
            if fn.endswith('.py') and fn != '__init__.py':
                fp = os.path.join(root, fn)
                try:
                    with open(fp, 'r') as fh:
                        if sum(1 for _ in fh) >= 50:
                            files.append(fp)
                except:
                    pass
    return sorted(files)

out_lines = []
out_lines.append("=" * 80)
out_lines.append("I18N SCAN REPORT: gateway/ and agent/ user-facing strings")
out_lines.append("=" * 80)

for label, d in [("GATEWAY", "gateway"), ("AGENT", "agent")]:
    out_lines.append(f"\n{'#'*60}")
    out_lines.append(f"# {label} FILES")
    out_lines.append(f"{'#'*60}")
    summary = []
    for fp in walk_dir(d):
        r = scan_file(fp)
        summary.append(r)
        i18n = "YES" if r['has_i18n_import'] else "NO"
        u = "Y" if r['underscore_used'] else "N"
        c = "CONFLICT" if r['_conflict'] else "-"
        short = os.path.relpath(fp, d)
        pats = "; ".join(r['user_patterns'][:7]) if r['user_patterns'] else "(none visible)"
        
        out_lines.append(f"\n[{r['priority'].upper():6}] {short} ({r['lines']}L)")
        out_lines.append(f"  i18n={i18n}  _()={u}  _conflict={c}  f-str={r['fstring_count']}  est_usermsg={r['str_est']}")
        out_lines.append(f"  patterns: {pats}")
    
    # Summary stats
    high = [r for r in summary if r['priority'] == 'high']
    med = [r for r in summary if r['priority'] == 'medium']
    low = [r for r in summary if r['priority'] == 'low']
    has_i18n = [r for r in summary if r['has_i18n_import']]
    has_underscore = [r for r in summary if r['underscore_used']]
    has_conflict = [r for r in summary if r['_conflict']]
    total_strs = sum(r['str_est'] for r in summary)
    total_fstrings = sum(r['fstring_count'] for r in summary)
    
    out_lines.append(f"\n--- {label} SUMMARY ---")
    out_lines.append(f"  Total files scanned: {len(summary)}")
    out_lines.append(f"  HIGH priority: {len(high)}  MEDIUM: {len(med)}  LOW: {len(low)}")
    out_lines.append(f"  Already imports bwm_cli.i18n: {len(has_i18n)}")
    out_lines.append(f"  Already uses _() gettext: {len(has_underscore)}")
    out_lines.append(f"  _ variable conflict risk: {len(has_conflict)}")
    out_lines.append(f"  Total est send_message/reply calls: {total_strs}")
    out_lines.append(f"  Total f-strings: {total_fstrings}")
    if high:
        out_lines.append(f"  HIGH priority files: {', '.join(os.path.basename(r['file']) for r in high)}")
    if has_i18n:
        out_lines.append(f"  Files with i18n: {', '.join(os.path.basename(r['file']) for r in has_i18n)}")
    if has_conflict:
        out_lines.append(f"  _ conflict files: {', '.join(os.path.basename(r['file']) for r in has_conflict)}")

out_lines.append("\n" + "=" * 80)
out_lines.append("SCAN COMPLETE")
out_lines.append("=" * 80)

output = '\n'.join(out_lines)
with open('i18n_scan_report.txt', 'w', encoding='utf-8') as f:
    f.write(output)
print(f"Report written to i18n_scan_report.txt ({len(output)} chars, {len(out_lines)} lines)")
print(output[:300])
