"""
Encrypt all SKILL.md files for Sale distribution.

Usage:
    python scripts/encrypt_skills.py --key <license-key>
    python scripts/encrypt_skills.py --key <license-key> --dry-run
    python scripts/encrypt_skills.py --key <license-key> --output-dir /tmp/encrypted

Scans skills/ and optional-skills/ for SKILL.md files, encrypts each to
SKILL.skill.enc in the same directory (or --output-dir mirror), then
deletes the original SKILL.md.
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(PROJECT_ROOT))


def find_all_skill_files(root: Path) -> list[Path]:
    """Find all SKILL.md files under skills/ and optional-skills/."""
    results = []
    for subdir in ["skills", "optional-skills"]:
        base = root / subdir
        if not base.exists():
            continue
        for skill_md in base.rglob("SKILL.md"):
            results.append(skill_md)
    return sorted(results)


def encrypt_all(
    license_key: str,
    dry_run: bool = False,
    output_dir: Path | None = None,
) -> tuple[int, int]:
    """Encrypt all SKILL.md files. Returns (success_count, fail_count)."""
    from agent.skill_crypto import encrypt_skill

    skill_files = find_all_skill_files(PROJECT_ROOT)
    if not skill_files:
        print("[WARN] No SKILL.md files found")
        return 0, 0

    print(f"Found {len(skill_files)} SKILL.md files to encrypt")

    ok = 0
    fail = 0

    for skill_md in skill_files:
        rel = skill_md.relative_to(PROJECT_ROOT)
        try:
            plaintext = skill_md.read_text(encoding="utf-8")
            if not plaintext.strip():
                print(f"  [skip] {rel} (empty)")
                continue

            if dry_run:
                print(f"  [dry-run] {rel} ({len(plaintext)} bytes)")
                ok += 1
                continue

            encrypted = encrypt_skill(plaintext, license_key)

            if output_dir:
                out_path = output_dir / rel.parent / "SKILL.skill.enc"
                out_path.parent.mkdir(parents=True, exist_ok=True)
            else:
                out_path = skill_md.parent / "SKILL.skill.enc"

            out_path.write_bytes(encrypted)

            if not output_dir:
                skill_md.unlink()

            print(f"  [OK] {rel} → .skill.enc ({len(plaintext)} → {len(encrypted)} bytes)")
            ok += 1

        except Exception as e:
            print(f"  [FAIL] {rel}: {e}")
            fail += 1

    return ok, fail


def main():
    parser = argparse.ArgumentParser(description="Encrypt SKILL.md files for Sale")
    parser.add_argument("--key", required=True, help="License key for AES-256 encryption")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--output-dir", type=Path, help="Write .enc files to separate dir")
    args = parser.parse_args()

    if len(args.key) < 16:
        print("[ERROR] License key must be at least 16 characters")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  Encrypt Skills for Sale Distribution")
    print(f"  Key length: {len(args.key)} chars")
    print(f"  Mode: {'dry-run' if args.dry_run else 'ENCRYPT'}")
    print(f"{'='*60}\n")

    ok, fail = encrypt_all(args.key, args.dry_run, args.output_dir)

    print(f"\n{'='*60}")
    print(f"  Results: {ok} encrypted, {fail} failed")
    print(f"{'='*60}\n")

    if fail > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
