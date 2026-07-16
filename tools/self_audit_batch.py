#!/usr/bin/env python3
"""BookwormPRO self-audit batch: stages 1.1, 1.3, 1.4, 2, 3, 4"""
import json, re, os
from pathlib import Path
from datetime import datetime

HOME = Path.home()
NOW = datetime.now().strftime("%Y-%m-%d %H:%M")

print(f"══════ BookwormPRO 全面自检 · {NOW} ══════\n")

# ── 环节1.1: Cron ──
print("  环节1.1 Cron")
try:
    jobs_path = HOME / '.bookwormpro' / 'cron' / 'jobs.json'
    d = json.loads(jobs_path.read_text())
    issues = [j for j in d['jobs'] if not j.get('model')]
    for j in d['jobs']:
        jid = j['id'][:16]
        name = j.get('name', '?')[:30]
        model = j.get('model', 'NULL')
        enabled = j.get('enabled', '?')
        tag = "🟢" if model != 'NULL' and enabled else "🔴"
        print(f"    {tag} {jid} | {name:30s} | model={model} | enabled={enabled}")
    print(f"    Total: {len(d['jobs'])} jobs, ModelNull: {len(issues)}\n")
except Exception as e:
    print(f"    🔴 Error: {e}\n")

# ── 环节1.3: Skills ──
print("  环节1.3 Skills")
try:
    skills_dir = HOME / '.bookwormpro' / 'skills'
    ok = nofm = noname = nodesc = empty = total = 0
    for f in sorted(skills_dir.rglob('SKILL.md')):
        total += 1
        sz = f.stat().st_size
        if sz == 0:
            empty += 1
            continue
        t = f.read_text(encoding='utf-8')
        if not t.startswith('---'):
            nofm += 1
            continue
        parts = t.split('---', 2)
        if len(parts) < 3:
            nofm += 1
            continue
        if not re.search(r'^name:\s*\S', parts[1], re.M):
            noname += 1
        if not re.search(r'^description:\s*\S', parts[1], re.M):
            nodesc += 1
        ok += 1
    status = "🟢" if empty == 0 and nofm == 0 else ("🟡" if noname + nodesc == 0 else "🔴")
    print(f"    {status} Total={total} OK={ok} Empty={empty} NoFM={nofm} NoName={noname} NoDesc={nodesc}\n")
except Exception as e:
    print(f"    🔴 Error: {e}\n")

# ── 环节1.4: Routing ──
print("  环节1.4 Routing")
try:
    df = HOME / '.claude' / 'scripts' / 'disambiguation-rules.json'
    d = json.loads(df.read_text())
    rules = d['_meta']['ruleCount'] if '_meta' in d else '?'
    ver = d['_meta']['version'] if '_meta' in d else '?'
    sz = df.stat().st_size
    print(f"    🟢 Rules: {rules} (v{ver}) | File: {sz:,} bytes\n")
except Exception as e:
    print(f"    🔴 Error: {e}\n")

# ── 环节2: .env 审计 ──
print("  环节2 .env 审计")
try:
    env = HOME / '.bookwormpro' / '.env'
    lines = env.read_text().strip().split('\n')
    active = 0
    issues_found = 0
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            continue
        key, val = line.split('=', 1)
        is_sensitive = len(val) > 40 or any(c in val for c in '$@')
        display_val = '***' if is_sensitive else val[:60]
        problems = []
        if 'qwen-vl-max' in val and 'alibaba/' in val:
            problems.append(f'🔴 OpenRouter命名风格，应改为 qwen-vl-max')
        if 'OPENROUTER' in key.upper() or ('OPENAI' in key.upper() and 'OPENAI' not in key):
            problems.append('⚠ 可能已废弃（当前 deepseek 主provider）')
        if key == 'AUXILIARY_VISION_MODEL' and 'alibaba/' in val:
            problems.append('🔴 模型路径错误')
        if 'bww.letcareme.com' in val and 'API_KEY' not in key:
            problems.append('⚠ BWW 中转站，需确认 API key 可用')
        tag = '🟢' if not problems else '🔴'
        print(f"    {tag} {key}={display_val}")
        for p in problems:
            print(f"        {p}")
        active += 1
        if problems:
            issues_found += 1
    status = "🟢" if issues_found == 0 else "🔴"
    print(f"    {status} {active} 在用 / {issues_found} 需修复\n")
except Exception as e:
    print(f"    🔴 Error: {e}\n")

# ── 环节3: 日志噪音 ──
print("  环节3 日志噪音")
try:
    log = HOME / '.bookwormpro' / 'logs' / 'agent.log'
    if log.exists():
        content = log.read_text(encoding='utf-8', errors='replace')
        warnings = content.count('WARNING')
        errors = content.count('ERROR')
        skipping = content.count('skipping env')
        aux_warn = content.count('auxiliary_client') if 'auxiliary_client' in content else 0
        today = datetime.now().strftime('%Y-%m-%d')
        today_warn = content.count(f'{today}') if today in content else 'N/A'
        # Extract top WARNING patterns
        warn_lines = [l for l in content.split('\n') if 'WARNING' in l]
        patterns = {}
        for wl in warn_lines:
            # Extract agent.module pattern
            m = re.search(r'(agent\.\S+)', wl)
            if m:
                pat = m.group(1)[:40]
                patterns[pat] = patterns.get(pat, 0) + 1
        top = sorted(patterns.items(), key=lambda x: x[1], reverse=True)[:5]

        status = "🟢" if warnings < 50 else ("🟡" if warnings < 200 else "🔴")
        print(f"    {status} WARNING: {warnings} total | ERROR: {errors} total")
        print(f"    skipping env: {skipping} | auxiliary_client WARNING: {aux_warn}")
        print(f"    今日 WARNING: {today_warn}")
        if top:
            print(f"    Top patterns: {' | '.join(f'{p}({c})' for p,c in top)}")
        print()
    else:
        print(f"    ⚪ agent.log 不存在\n")
except Exception as e:
    print(f"    🔴 Error: {e}\n")

# ── 环节4: 凭证冲突 ──
print("  环节4 凭证冲突")
try:
    auth = json.loads((HOME / '.bookwormpro' / 'auth.json').read_text())
    pool = auth.get('credential_pool', {})
    conflicts = []
    for provider, entries in pool.items():
        for e in entries:
            label = e.get('label', '?')
            base = e.get('base_url', 'N/A')
            source = e.get('source', '?')
            print(f"      {provider:15s} | {label:25s} | {base:50s} | {source}")
            if 'RELAY' in label.upper():
                conflicts.append(f'🔴 {provider}: {label} — RELAY条目，与主provider可能冲突')
            if 'OPENROUTER' in label.upper() and 'bww.letcareme.com' in base:
                conflicts.append(f'🔴 {provider}: {label} — BWW URL但标为OpenRouter')
    if conflicts:
        print(f"\n    {len(conflicts)} 冲突:")
        for c in conflicts:
            print(f"      {c}")
        status = "🔴"
    else:
        status = "🟢"
        print(f"\n    ✅ 无凭证冲突")
    # Check backup files
    backups = list(HOME.glob('.bookwormpro/auth.json.*'))
    if backups:
        print(f"    ⚠ {len(backups)} 残留备份文件:")
        for b in backups:
            print(f"      {b.name}")
    # Check .env OPENAI residue
    env_text = (HOME / '.bookwormpro' / '.env').read_text()
    openai_count = sum(1 for l in env_text.split('\n') if 'OPENAI_' in l.upper() and not l.strip().startswith('#'))
    if openai_count:
        print(f"    ⚠ .env 中仍有 OPENAI_ 残留 ({openai_count} 行)")
    else:
        print(f"    ✅ .env 无 OPENAI 残留")
    print(f"\n    {status} 凭证冲突检测完成\n")
except Exception as e:
    print(f"    🔴 Error: {e}\n")

print("══════ 环节1/2/3/4 完成 ══════")
