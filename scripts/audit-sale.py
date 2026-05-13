"""Sale 版脱敏完整性审查 — 检测是否有非预期的文件丢失"""
import subprocess

def git_files(ref):
    r = subprocess.run(f"git ls-tree -r --name-only {ref}", shell=True, capture_output=True, text=True)
    return set(r.stdout.strip().split("\n"))

origin = git_files("HEAD")
sale = git_files("sale/master")

COMPILE_TARGETS = {
    "agent/prompt_builder.py", "agent/skill_preprocessing.py",
    "agent/context_compressor.py", "agent/prompt_caching.py",
    "agent/redact.py", "agent/skill_crypto.py",
}
INTERNAL_FILES = {
    ".bookworm-progress.md", "findings.md", "apply_audit_fixes.py",
    "bookworm-already-has-routines.md",
    "docs/audit-sprint-2026-05-06.md",
    "docs/BookwormPRO_v7_Architecture_Comparison.html",
    "docs/gateway-hardening.md", "docs/gateway-hardening-rollback.md",
    "docs/p2-1-god-class-split-plan.md", "docs/p2-2-layer-violation-plan.md",
    "scripts/generate_license.py", "scripts/build_sale.py",
    "scripts/publish-sale.ps1", "scripts/publish-sale.sh",
    "scripts/encrypt_skills.py", "scripts/trial_server.py",
    "scripts/contributor_audit.py", "scripts/hermes_audit.py",
    "scripts/release.py", "scripts/rebrand_hermes_to_bookworm.py",
    "scripts/rebrand_docs.py", "scripts/rebrand_p0_p1.py",
    "scripts/discord-voice-doctor.py", "scripts/provider_health_probe.py",
    "scripts/sample_and_compress.py", "scripts/patches/patch_enc_support.py",
}

only_origin = origin - sale
only_sale = sale - origin

expected_gone = set()
unexpected_gone = set()
for f in only_origin:
    if f in COMPILE_TARGETS:
        expected_gone.add(f"[COMPILE] {f}")
    elif f in INTERNAL_FILES:
        expected_gone.add(f"[INTERNAL] {f}")
    elif f.endswith("/SKILL.md"):
        expected_gone.add(f"[ENCRYPT] {f}")
    else:
        unexpected_gone.add(f)

expected_new = set()
unexpected_new = set()
for f in only_sale:
    if f.endswith(".pyd") or f.endswith(".so"):
        expected_new.add(f"[PYD] {f}")
    elif f.endswith(".skill.enc"):
        expected_new.add(f"[ENC] {f}")
    else:
        unexpected_new.add(f)

print("=" * 60)
print("  Sale 版脱敏完整性审查")
print("=" * 60)
print(f"\n  原版文件: {len(origin)}")
print(f"  Sale 文件: {len(sale)}")
print(f"  差异: {len(only_origin)} 删除 / {len(only_sale)} 新增")

print(f"\n--- 预期删除 ({len(expected_gone)}) ---")
for f in sorted(expected_gone)[:5]:
    print(f"  OK  {f}")
print(f"  ... 共 {len(expected_gone)} 项")

print(f"\n--- 预期新增 ({len(expected_new)}) ---")
pyd_count = sum(1 for f in expected_new if "[PYD]" in f)
enc_count = sum(1 for f in expected_new if "[ENC]" in f)
print(f"  OK  {pyd_count} 个 .pyd 编译产物")
print(f"  OK  {enc_count} 个 .skill.enc 加密技能")

print(f"\n{'=' * 60}")
if unexpected_gone:
    print(f"  !! 非预期丢失 ({len(unexpected_gone)}):")
    for f in sorted(unexpected_gone):
        print(f"  WARN  {f}")
else:
    print("  PASS  无非预期丢失文件")

if unexpected_new:
    print(f"  !! 非预期新增 ({len(unexpected_new)}):")
    for f in sorted(unexpected_new):
        print(f"  WARN  {f}")
else:
    print("  PASS  无非预期新增文件")

verdict = "PASS" if not unexpected_gone and not unexpected_new else "WARN"
print(f"\n  结论: {verdict}")
print("=" * 60)
