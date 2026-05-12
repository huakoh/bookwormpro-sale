"""Patch: Add .skill.enc transparent decryption to all skill discovery paths.

Idempotent — safe to run multiple times.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

patches = [
    # 1. prompt_builder.py — import
    {
        "file": ROOT / "agent" / "prompt_builder.py",
        "sentinel": "from agent.skill_crypto import",
        "old": "from agent.skill_utils import (",
        "new": "from agent.skill_crypto import is_encrypted_skill, read_skill_content\nfrom agent.skill_utils import (",
    },
    # 2. prompt_builder.py — _parse_skill_file
    {
        "file": ROOT / "agent" / "prompt_builder.py",
        "sentinel": "is_encrypted_skill(skill_file)",
        "old": '        raw = skill_file.read_text(encoding="utf-8")\n        frontmatter, _ = parse_frontmatter(raw)',
        "new": (
            '        if is_encrypted_skill(skill_file):\n'
            '            raw = read_skill_content(skill_file.parent)\n'
            '            if raw is None:\n'
            '                logger.debug("Could not decrypt skill %s", skill_file)\n'
            '                return True, {}, ""\n'
            '        else:\n'
            '            raw = skill_file.read_text(encoding="utf-8")\n'
            '        frontmatter, _ = parse_frontmatter(raw)'
        ),
    },
    # 3. skill_commands.py — import
    {
        "file": ROOT / "agent" / "skill_commands.py",
        "sentinel": "from agent.skill_crypto import",
        "old": "from bwm_constants import display_hermes_home\n",
        "new": "from bwm_constants import display_hermes_home\nfrom agent.skill_crypto import is_encrypted_skill, read_skill_content\n",
    },
    # 4. skill_commands.py — read_text
    {
        "file": ROOT / "agent" / "skill_commands.py",
        "sentinel": "is_encrypted_skill(skill_md)",
        "old": "                    content = skill_md.read_text(encoding='utf-8')\n                    frontmatter, body = _parse_frontmatter(content)",
        "new": (
            "                    if is_encrypted_skill(skill_md):\n"
            "                        content = read_skill_content(skill_md.parent)\n"
            "                        if content is None:\n"
            "                            continue\n"
            "                    else:\n"
            "                        content = skill_md.read_text(encoding='utf-8')\n"
            "                    frontmatter, body = _parse_frontmatter(content)"
        ),
    },
    # 5. skill_utils.py — discover_all_skill_config_vars
    {
        "file": ROOT / "agent" / "skill_utils.py",
        "sentinel": "is_encrypted_skill(skill_file)",
        "old": '            try:\n                raw = skill_file.read_text(encoding="utf-8")\n                frontmatter, _ = parse_frontmatter(raw)\n            except Exception:\n                continue',
        "new": (
            '            try:\n'
            '                from agent.skill_crypto import is_encrypted_skill, read_skill_content\n'
            '                if is_encrypted_skill(skill_file):\n'
            '                    raw = read_skill_content(skill_file.parent)\n'
            '                    if raw is None:\n'
            '                        continue\n'
            '                else:\n'
            '                    raw = skill_file.read_text(encoding="utf-8")\n'
            '                frontmatter, _ = parse_frontmatter(raw)\n'
            '            except Exception:\n'
            '                continue'
        ),
    },
    # 6. dump.py — _count_skills
    {
        "file": ROOT / "bwm_cli" / "dump.py",
        "sentinel": "SKILL.skill.enc",
        "old": '    for item in skills_dir.rglob("SKILL.md"):\n        count += 1\n    return count',
        "new": (
            '    for item in skills_dir.rglob("SKILL.md"):\n'
            '        count += 1\n'
            '    for item in skills_dir.rglob("SKILL.skill.enc"):\n'
            '        if not (item.parent / "SKILL.md").exists():\n'
            '            count += 1\n'
            '    return count'
        ),
    },
    # 7. profiles.py — _count_skills
    {
        "file": ROOT / "bwm_cli" / "profiles.py",
        "sentinel": "SKILL.skill.enc",
        "old": '    for md in skills_dir.rglob("SKILL.md"):\n        if "/.hub/" not in str(md) and "/.git/" not in str(md):\n            count += 1\n    return count',
        "new": (
            '    for md in skills_dir.rglob("SKILL.md"):\n'
            '        if "/.hub/" not in str(md) and "/.git/" not in str(md):\n'
            '            count += 1\n'
            '    for enc in skills_dir.rglob("SKILL.skill.enc"):\n'
            '        if not (enc.parent / "SKILL.md").exists():\n'
            '            if "/.hub/" not in str(enc) and "/.git/" not in str(enc):\n'
            '                count += 1\n'
            '    return count'
        ),
    },
    # 8. main.py — guardian scan
    {
        "file": ROOT / "bwm_cli" / "main.py",
        "sentinel": 'SKILL.skill.enc',
        "old": '                if d.is_dir() and (d / "SKILL.md").exists():',
        "new": '                if d.is_dir() and ((d / "SKILL.md").exists() or (d / "SKILL.skill.enc").exists()):',
    },
]

applied = 0
skipped = 0
for i, p in enumerate(patches, 1):
    path = p["file"]
    content = path.read_text(encoding="utf-8")
    if p["sentinel"] in content:
        print(f"  [{i}/8] SKIP (already applied): {path.name}")
        skipped += 1
        continue
    if p["old"] not in content:
        print(f"  [{i}/8] WARN: old string not found in {path.name}")
        continue
    content = content.replace(p["old"], p["new"], 1)
    path.write_text(content, encoding="utf-8")
    print(f"  [{i}/8] APPLIED: {path.name}")
    applied += 1

print(f"\nDone: {applied} applied, {skipped} skipped")
