"""
Resolve _ conflicts in 4 remaining files + inject i18n import.
"""
import re, py_compile
from pathlib import Path

PROJECT = Path(r"C:\Users\leesu\BookwormPRO")

files_to_fix = [
    {
        'path': PROJECT / 'bwm_cli' / 'profiles.py',
        'replacements': [
            ('for _ in range(20):', 'for _i in range(20):'),
        ],
    },
    {
        'path': PROJECT / 'bwm_cli' / 'gateway.py',
        'replacements': [
            ('for _ in range(20):', 'for _i in range(20):'),
            ('linger_enabled, _ = get_systemd_linger_status()', 'linger_enabled, _ign = get_systemd_linger_status()'),
        ],
    },
    {
        'path': PROJECT / 'run_agent.py',
        'replacements': [
            ('for _ in range(50):', 'for _i in range(50):'),
            ('_routed_client, _ = resolve_provider_client(', '_routed_client, _ign = resolve_provider_client('),
            ('for _ in range(2):', 'for _i in range(2):'),
            ('header, _, data = str(image_url or "").partition(",")', 'header, _ign, data = str(image_url or "").partition(",")'),
            ('embedded_call_id, _ = self._split_responses_tool_id(raw_id)', 'embedded_call_id, _ign = self._split_responses_tool_id(raw_id)'),
        ],
    },
    {
        'path': PROJECT / 'gateway' / 'run.py',
        # Use qualified import (i18n._()) to avoid Discord italic conflict
        'use_qualified_import': True,
        'replacements': [
            ('for _ in range(interval):', 'for _i in range(interval):'),
            ('for _ in range(30):', 'for _i in range(30):'),
            ('for _ in range(10):', 'for _i in range(10):'),
            ('guessed, _ = _mimetypes.guess_type(path)', 'guessed, _ign = _mimetypes.guess_type(path)'),
            ('_compressed, _ = await loop.run_in_executor(', '_compressed, _ign = await loop.run_in_executor('),
            ('media_files, _ = adapter.extract_media(response)', 'media_files, _ign = adapter.extract_media(response)'),
            ('local_files, _ = adapter.extract_local_files(cleaned)', 'local_files, _ign = adapter.extract_local_files(cleaned)'),
            ('compressed, _ = await loop.run_in_executor(', 'compressed, _ign = await loop.run_in_executor('),
            # _, base_msg, count = raw -- careful, only match the exact pattern
            ('                        _, base_msg, count = raw', '                        _ign, base_msg, count = raw'),
            # for _ in range(200):
            ('for _ in range(200):', 'for _i in range(200):'),
            # done, _ = await asyncio.wait(
            ('done, _ = await asyncio.wait(', 'done, _ign = await asyncio.wait('),
            # for _ in range(20):
            ('for _ in range(20):', 'for _i in range(20):'),
        ],
    },
]

for cfg in files_to_fix:
    filepath = cfg['path']
    if not filepath.exists():
        print(f"NOT FOUND: {filepath}")
        continue
    
    print(f"\n{'='*60}")
    print(f"Processing: {filepath.name}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    changes = 0
    
    # Apply replacements
    for old, new in cfg['replacements']:
        if old in content:
            content = content.replace(old, new)
            changes += 1
            print(f"  ✓ {old[:60]}...")
    
    # Add i18n import
    if cfg.get('use_qualified_import'):
        # gateway/run.py: use qualified import to avoid Discord italic conflict
        import_line = 'from bwm_cli import i18n  # use i18n._() to avoid Discord italic markdown conflict'
        
        # Find good insertion point
        if 'from bwm_cli' in content:
            # Insert after last bwm_cli import
            lines = content.split('\n')
            last_bwm_import = 0
            for i, line in enumerate(lines):
                if line.startswith('from bwm_cli') or line.startswith('from bwm_constants'):
                    last_bwm_import = i
            lines.insert(last_bwm_import + 1, import_line)
            content = '\n'.join(lines)
            print(f"  ✓ Added qualified import: {import_line}")
            changes += 1
        else:
            print(f"  ⚠ Could not find import location")
    else:
        # Standard import
        if 'from bwm_cli.i18n import _' not in content:
            # Find last import from bwm_cli
            lines = content.split('\n')
            last_import = 0
            for i, line in enumerate(lines):
                if line.startswith('from bwm_cli') or line.startswith('from bwm_constants'):
                    last_import = i
            if last_import > 0:
                lines.insert(last_import + 1, 'from bwm_cli.i18n import _')
                content = '\n'.join(lines)
                print(f"  ✓ Added i18n import")
                changes += 1
    
    if changes > 0:
        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            f.write(content)
        
        # Verify syntax
        try:
            py_compile.compile(str(filepath), doraise=True)
            print(f"  ✅ Syntax OK ({changes} changes)")
        except py_compile.PyCompileError as e:
            print(f"  ❌ SYNTAX ERROR: {e}")
            print(f"  Restoring from git...")
            import subprocess
            subprocess.run(['git', 'checkout', str(filepath.relative_to(PROJECT))], 
                          cwd=str(PROJECT), capture_output=True)
    else:
        print(f"  - No changes needed")

print(f"\n{'='*60}")
print("All conflict files processed.")
