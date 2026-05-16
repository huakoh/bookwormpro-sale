"""
BookwormPRO Sale 仓构建脚本 (跨平台: Windows/Linux/macOS)
==========================================================
自动完成: 脱敏 → Cython 编译核心模块 → 加密 Skills → 删源码 → 推送到 sale 仓

用法:
    python scripts/build_sale.py --license-key <key>              # 构建但不推送
    python scripts/build_sale.py --license-key <key> --push       # 构建并推送
    python scripts/build_sale.py --license-key <key> --dry-run    # 仅预览，不执行

前置依赖:
    - Python 3.12+, pip install cython cryptography
    - Windows: MSVC Build Tools (或 MinGW-w64)
    - Linux:   gcc / build-essential
    - macOS:   Xcode Command Line Tools (xcode-select --install)
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SALE_REMOTE = "sale"
IS_WINDOWS = platform.system() == "Windows"
DEV_NULL = "nul" if IS_WINDOWS else "/dev/null"

# 需要 Cython 编译的核心模块 (相对于 PROJECT_ROOT)
COMPILE_TARGETS = [
    "agent/prompt_builder.py",
    "agent/skill_preprocessing.py",
    "agent/context_compressor.py",
    "agent/prompt_caching.py",
    "agent/redact.py",
    "agent/skill_crypto.py",
]

# 需要删除的内部文档
INTERNAL_FILES = [
    ".bookworm-progress.md",
    "findings.md",
    "apply_audit_fixes.py",
    "bookworm-already-has-routines.md",
    "docs/audit-sprint-2026-05-06.md",
    "docs/BookwormPRO_v7_Architecture_Comparison.html",
    "docs/gateway-hardening.md",
    "docs/gateway-hardening-rollback.md",
    "docs/p2-1-god-class-split-plan.md",
    "docs/p2-2-layer-violation-plan.md",
    "scripts/generate_license.py",
    "scripts/build_sale.py",
    "scripts/publish-sale.ps1",
    "scripts/publish-sale.sh",
    "scripts/encrypt_skills.py",
    "scripts/trial_server.py",
    "scripts/contributor_audit.py",
    "scripts/hermes_audit.py",
    "scripts/release.py",
    "scripts/rebrand_hermes_to_bookworm.py",
    "scripts/rebrand_docs.py",
    "scripts/rebrand_p0_p1.py",
    "scripts/discord-voice-doctor.py",
    "scripts/provider_health_probe.py",
    "scripts/sample_and_compress.py",
    "scripts/patches/patch_enc_support.py",
    ".plans",
    "plans",
    "docs/business-plan.html",
    "docs/sale-distribution-guide.md",
    "task_plan.md",
    "progress.md",
    ".envrc",
    "tests",
    "hermes_agent.egg-info",
]

# 源码中需要脱敏的替换对 (relay 域名保留, 客户需要通过 relay 访问多模型)
SANITIZE_PAIRS = [
    ("docker-compose.yml", "C:\\Users\\leesu\\Desktop", "C:\\Users\\<username>\\Desktop"),
    ("README.md", "huakoh/BookwormPRO.git", "huakoh/bookwormpro-sale.git"),
    ("README.md", "huakoh/BookwormPRO/main", "huakoh/bookwormpro-sale/master"),
]

# golden-set.json 中需要脱敏的 PII 模式
GOLDEN_SET_PII_REPLACEMENTS = [
    ("梁雄新", "user-001"),
    ("E:\\\\test资料", "E:\\\\sample-data"),
]

# install 脚本中仓库 URL 替换
INSTALL_REPO_REPLACE = ("huakoh/BookwormPRO", "huakoh/bookwormpro-sale")

# install 脚本中 Python 版本替换 (Cython .pyd 绑定构建时的 Python 版本)
INSTALL_PYTHON_REPLACE_PS1 = ('$PythonVersion = "3.11"', '$PythonVersion = "3.12"')
INSTALL_PYTHON_REPLACE_SH = ('PYTHON_VERSION="3.11"', 'PYTHON_VERSION="3.12"')
# install 脚本默认分支替换 (sale 仓默认 master)
INSTALL_BRANCH_REPLACE_PS1 = ('$Branch = "main"', '$Branch = "master"')
INSTALL_BRANCH_REPLACE_SH = ('BRANCH="main"', 'BRANCH="master"')
# install 脚本注释中 raw URL 分支替换
INSTALL_URL_BRANCH_REPLACE = ("BookwormPRO/main/scripts", "bookwormpro-sale/master/scripts")


def run(cmd, **kwargs):
    print(f"  $ {cmd}")
    return subprocess.run(cmd, shell=True, check=True, **kwargs)


def step(msg):
    print(f"\n{'='*60}\n  {msg}\n{'='*60}")


def _check_c_compiler():
    """Verify a C compiler is available for Cython compilation."""
    if IS_WINDOWS:
        # MSVC cl.exe (loaded via vcvars) or gcc from MinGW
        for cmd in ["cl", "gcc"]:
            try:
                subprocess.run(
                    [cmd], capture_output=True, timeout=5,
                )
                print(f"  C compiler: {cmd} ✓")
                return
            except FileNotFoundError:
                continue
        print("  [WARN] C compiler not found in PATH.")
        print("         Windows: load vcvars64.bat first, or install MinGW-w64")
        print("         publish-sale.ps1 handles this automatically")
    else:
        # Linux: gcc, macOS: clang (via cc symlink)
        for cmd in ["cc", "gcc", "clang"]:
            if shutil.which(cmd):
                try:
                    result = subprocess.run(
                        [cmd, "--version"], capture_output=True, text=True, timeout=5,
                    )
                    first_line = result.stdout.splitlines()[0] if result.stdout else cmd
                    print(f"  C compiler: {first_line}")
                    return
                except Exception:
                    print(f"  C compiler: {cmd} ✓")
                    return
        print("  [ERROR] No C compiler found (cc/gcc/clang)")
        if platform.system() == "Darwin":
            print("         macOS: xcode-select --install")
        else:
            print("         Linux: apt install build-essential  (or yum install gcc)")
        sys.exit(1)


def cython_compile(workdir: Path, targets: list[str], dry_run: bool = False):
    """Cython 编译指定 .py 文件为 .pyd/.so"""
    compiled = []
    for rel_path in targets:
        src = workdir / rel_path
        if not src.exists():
            print(f"  [skip] {rel_path} (不存在)")
            continue

        if dry_run:
            print(f"  [dry-run] 会编译: {rel_path}")
            compiled.append(rel_path)
            continue

        print(f"  [compile] {rel_path}")
        module_name = src.stem

        setup_content = f'''
from setuptools import setup, Extension
from Cython.Build import cythonize
setup(ext_modules=cythonize(
    Extension("{rel_path.replace('/', '.').replace(chr(92), '.').removesuffix('.py')}",
              ["{rel_path.replace(chr(92), '/')}"]),
    language_level="3",
))
'''
        setup_file = workdir / "_cython_setup.py"
        setup_file.write_text(setup_content)

        try:
            result = subprocess.run(
                [sys.executable, str(setup_file), "build_ext", "--inplace"],
                cwd=str(workdir),
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                print(f"  [FAIL] {rel_path}: {result.stderr[-300:]}")
                continue

            module_dir = src.parent
            pyd = list(module_dir.glob(f"{module_name}*.pyd")) + list(module_dir.glob(f"{module_name}*.so"))
            if pyd:
                print(f"  [OK] {pyd[0].name}")
                src.unlink()
                c_file = module_dir / f"{module_name}.c"
                if c_file.exists():
                    c_file.unlink()
                compiled.append(rel_path)
            else:
                print(f"  [FAIL] 编译产物未找到: {module_name}*.pyd/so")
        finally:
            setup_file.unlink(missing_ok=True)
            build_dir = workdir / "build"
            if build_dir.exists():
                shutil.rmtree(build_dir, ignore_errors=True)

    return compiled


def sanitize_files(workdir: Path, dry_run: bool = False):
    """删除内部文件 + 文本脱敏"""
    for rel_path in INTERNAL_FILES:
        f = workdir / rel_path
        if f.exists():
            if dry_run:
                print(f"  [dry-run] 会删除: {rel_path}")
            elif f.is_dir():
                shutil.rmtree(f)
                print(f"  [del-dir] {rel_path}")
            else:
                f.unlink()
                print(f"  [del] {rel_path}")

    for filename, old, new in SANITIZE_PAIRS:
        f = workdir / filename
        if f.exists():
            content = f.read_text(encoding="utf-8")
            if old in content:
                if dry_run:
                    print(f"  [dry-run] 会脱敏: {filename}")
                else:
                    f.write_text(content.replace(old, new), encoding="utf-8")
                    print(f"  [sanitize] {filename}")

    for script_name in ["scripts/install.ps1", "scripts/install.sh"]:
        f = workdir / script_name
        if f.exists():
            content = f.read_text(encoding="utf-8")
            replacements = [
                (INSTALL_REPO_REPLACE, "repo-url"),
            ]
            replacements.append((INSTALL_URL_BRANCH_REPLACE, "url-branch"))
            if script_name.endswith(".ps1"):
                replacements.append((INSTALL_PYTHON_REPLACE_PS1, "python-ver"))
                replacements.append((INSTALL_BRANCH_REPLACE_PS1, "branch"))
            else:
                replacements.append((INSTALL_PYTHON_REPLACE_SH, "python-ver"))
                replacements.append((INSTALL_BRANCH_REPLACE_SH, "branch"))

            changed = False
            for (old_val, new_val), label in replacements:
                if old_val in content:
                    if dry_run:
                        print(f"  [dry-run] 会替换 {label}: {script_name}")
                    else:
                        content = content.replace(old_val, new_val)
                        changed = True
                        print(f"  [{label}] {script_name}")
            if changed and not dry_run:
                f.write_text(content, encoding="utf-8")

    # golden-set.json PII 脱敏
    gs = workdir / "routing" / "golden-set.json"
    if gs.exists() and GOLDEN_SET_PII_REPLACEMENTS:
        content = gs.read_text(encoding="utf-8")
        changed = False
        for old_pii, new_pii in GOLDEN_SET_PII_REPLACEMENTS:
            if old_pii in content:
                content = content.replace(old_pii, new_pii)
                changed = True
                if not dry_run:
                    print(f"  [pii] golden-set.json: {old_pii[:4]}*** -> {new_pii}")
        if changed and not dry_run:
            gs.write_text(content, encoding="utf-8")

    # GitHub Actions workflow 仓库名替换
    wf_dir = workdir / ".github" / "workflows"
    if wf_dir.exists():
        for wf in wf_dir.glob("*.yml"):
            content = wf.read_text(encoding="utf-8")
            if "huakoh/BookwormPRO'" in content or 'huakoh/BookwormPRO"' in content:
                new_content = content.replace("huakoh/BookwormPRO", "huakoh/bookwormpro-sale")
                if new_content != content and not dry_run:
                    wf.write_text(new_content, encoding="utf-8")
                    print(f"  [sanitize] .github/workflows/{wf.name}")


def _find_all_skill_files(root: Path) -> list[Path]:
    """Find all SKILL.md files under skills/ and optional-skills/."""
    results = []
    for subdir in ["skills", "optional-skills"]:
        base = root / subdir
        if not base.exists():
            continue
        for skill_md in base.rglob("SKILL.md"):
            results.append(skill_md)
    return sorted(results)


def encrypt_skills(workdir: Path, license_key: str, dry_run: bool = False) -> int:
    """Encrypt all SKILL.md → SKILL.skill.enc, delete originals."""
    sys.path.insert(0, str(workdir))
    from agent.skill_crypto import encrypt_skill

    skill_files = _find_all_skill_files(workdir)
    encrypted = 0
    batch_salt = os.urandom(16)

    for skill_md in skill_files:
        rel = skill_md.relative_to(workdir)
        try:
            plaintext = skill_md.read_text(encoding="utf-8")
            if not plaintext.strip():
                continue

            if dry_run:
                print(f"  [dry-run] 会加密: {rel}")
                encrypted += 1
                continue

            enc_data = encrypt_skill(plaintext, license_key, salt=batch_salt)
            enc_path = skill_md.parent / "SKILL.skill.enc"
            enc_path.write_bytes(enc_data)
            skill_md.unlink()
            print(f"  [enc] {rel} ({len(plaintext)} → {len(enc_data)} bytes)")
            encrypted += 1
        except Exception as e:
            print(f"  [FAIL] {rel}: {e}")

    return encrypted


def main():
    parser = argparse.ArgumentParser(description="BookwormPRO Sale 仓构建")
    parser.add_argument("--push", action="store_true", help="构建后推送到 sale 仓")
    parser.add_argument("--dry-run", action="store_true", help="仅预览不执行")
    parser.add_argument("--license-key", help="License key for skill encryption (or BOOKWORMPRO_LICENSE_KEY env)")
    args = parser.parse_args()

    license_key = args.license_key or os.environ.get("BOOKWORMPRO_LICENSE_KEY", "")
    if not license_key:
        print("  [ERROR] --license-key 或 BOOKWORMPRO_LICENSE_KEY 环境变量必须提供")
        sys.exit(1)
    if len(license_key) < 16:
        print("  [ERROR] License key 必须至少 16 字符")
        sys.exit(1)

    os.chdir(PROJECT_ROOT)

    step("1/6 检查环境")
    print(f"  Platform: {platform.system()} {platform.machine()}")
    run("git status --short", capture_output=True)
    try:
        import Cython
        print(f"  Cython {Cython.__version__}")
    except ImportError:
        print("  [ERROR] Cython 未安装: pip install cython")
        sys.exit(1)
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: F401
        print("  cryptography ✓")
    except ImportError:
        print("  [ERROR] cryptography 未安装: pip install cryptography")
        sys.exit(1)
    _check_c_compiler()

    step("2/6 创建 sale 分支")
    if not args.dry_run:
        subprocess.run(f"git branch -D sale-build 2>{DEV_NULL}", shell=True, capture_output=True)
        run("git checkout -b sale-build")

    compiled = []
    enc_count = 0
    try:
        step("3/6 脱敏")
        sanitize_files(PROJECT_ROOT, args.dry_run)

        step("4/6 Cython 编译核心模块")
        compiled = cython_compile(PROJECT_ROOT, COMPILE_TARGETS, args.dry_run)
        print(f"\n  编译完成: {len(compiled)}/{len(COMPILE_TARGETS)} 个模块")

        step("5/6 加密 SKILL.md 文件")
        enc_count = encrypt_skills(PROJECT_ROOT, license_key, args.dry_run)
        print(f"\n  加密完成: {enc_count} 个技能文件")

        if not args.dry_run:
            step("6/6 提交")
            run("git add agent/ bwm_constants.py scripts/install.ps1 scripts/install.sh")
            run("git add skills/ optional-skills/")
            for f in INTERNAL_FILES:
                if not (PROJECT_ROOT / f).exists():
                    subprocess.run(["git", "rm", "--cached", "-rf", f], capture_output=True)
            run("git add -u")
            run('git commit -m "chore: sale build — sanitized + compiled + encrypted"')

            if args.push:
                print("\n  推送到 sale 仓...")
                run(f"git push {SALE_REMOTE} sale-build:master --force")
                print("  [OK] sale 仓已更新")
        else:
            print("\n  [dry-run] 完成预览，未执行任何修改")
    finally:
        if not args.dry_run:
            subprocess.run("git checkout main", shell=True, capture_output=True)
            subprocess.run("git branch -D sale-build", shell=True, capture_output=True)

    step("完成")
    print(f"  脱敏: {len(INTERNAL_FILES)} 文件 + {len(SANITIZE_PAIRS)} 处文本")
    print(f"  编译: {len(compiled)} 个 .pyd/.so")
    print(f"  加密: {enc_count} 个 SKILL.md → .skill.enc")
    if args.push:
        print("  推送: sale/master ✓")

    if args.push and not args.dry_run:
        step("7/7 后置审查")
        print("  获取 sale/master 最新状态...")
        subprocess.run(f"git fetch {SALE_REMOTE}", shell=True, capture_output=True)
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "audit_sale", PROJECT_ROOT / "scripts" / "audit-sale.py",
            )
            audit = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(audit)
            verdict, lines, ug, un = audit.run_audit("HEAD", f"{SALE_REMOTE}/master")
            for line in lines:
                print(line)
            if verdict != "PASS":
                print(f"\n  [WARN] 审查未通过 — {len(ug)} 非预期丢失, {len(un)} 非预期新增")
        except Exception as e:
            print(f"  [skip] 审查模块加载失败: {e}")


if __name__ == "__main__":
    main()
