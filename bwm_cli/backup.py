"""

Backup and import commands for bookworm CLI.



`bookworm backup` creates a zip archive of the entire ~/.bookwormpro/ directory

(excluding the bookwormpro repo and transient files).



`bookworm import` restores from a backup zip, overlaying onto the current

BOOKWORMPRO_HOME root.

"""



import json

import logging

import os

import shutil

import sqlite3

import sys

import tempfile

import time

import zipfile

from datetime import datetime, timezone

from pathlib import Path

from typing import Any, Dict, List, Optional



from bwm_constants import get_default_hermes_root, get_hermes_home, display_hermes_home
from bwm_cli.i18n import _




logger = logging.getLogger(__name__)





# ---------------------------------------------------------------------------

# Exclusion rules

# ---------------------------------------------------------------------------



# Directory names to skip entirely (matched against each path component)

_EXCLUDED_DIRS = {

    "bookwormpro",     # the codebase repo — re-clone instead

    "__pycache__",      # bytecode caches — regenerated on import

    ".git",             # nested git dirs (profiles shouldn't have these, but safety)

    "node_modules",     # js deps if website/ somehow leaks in

}



# File-name suffixes to skip

_EXCLUDED_SUFFIXES = (

    ".pyc",

    ".pyo",

)



# File names to skip (runtime state that's meaningless on another machine)

_EXCLUDED_NAMES = {

    "gateway.pid",

    "cron.pid",

}





def _should_exclude(rel_path: Path) -> bool:

    """Return True if *rel_path* (relative to bookworm root) should be skipped."""

    parts = rel_path.parts



    # Any path component matches an excluded dir name

    for part in parts:

        if part in _EXCLUDED_DIRS:

            return True



    name = rel_path.name



    if name in _EXCLUDED_NAMES:

        return True



    if name.endswith(_EXCLUDED_SUFFIXES):

        return True



    return False





# ---------------------------------------------------------------------------

# SQLite safe copy

# ---------------------------------------------------------------------------



def _safe_copy_db(src: Path, dst: Path) -> bool:

    """Copy a SQLite database safely using the backup() API.



    Handles WAL mode — produces a consistent snapshot even while

    the DB is being written to.  Falls back to raw copy on failure.

    """

    try:

        conn = sqlite3.connect(f"file:{src}?mode=ro", uri=True)

        backup_conn = sqlite3.connect(str(dst))

        conn.backup(backup_conn)

        backup_conn.close()

        conn.close()

        return True

    except Exception as exc:

        logger.warning("SQLite safe copy failed for %s: %s", src, exc)

        try:

            shutil.copy2(src, dst)

            return True

        except Exception as exc2:

            logger.error("Raw copy also failed for %s: %s", src, exc2)

            return False





# ---------------------------------------------------------------------------

# Backup

# ---------------------------------------------------------------------------



def _format_size(nbytes: int) -> str:

    """Human-readable file size."""

    for unit in ("B", "KB", "MB", "GB"):

        if nbytes < 1024:

            return f"{nbytes:.1f} {unit}" if unit != "B" else f"{nbytes} {unit}"

        nbytes /= 1024

    return f"{nbytes:.1f} TB"





def run_backup(args) -> None:

    """Create a zip backup of the BookwormPRO home directory."""

    hermes_root = get_default_hermes_root()



    if not hermes_root.is_dir():

        print(_("Error: BookwormPRO home directory not found at {hermes_root}").format(hermes_root=hermes_root))

        sys.exit(1)



    # Determine output path

    if args.output:

        out_path = Path(args.output).expanduser().resolve()

        # If user gave a directory, put the zip inside it

        if out_path.is_dir():

            stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")

            out_path = out_path / f"bookworm-backup-{stamp}.zip"

    else:

        stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")

        out_path = Path.home() / f"bookworm-backup-{stamp}.zip"



    # Ensure the suffix is .zip

    if out_path.suffix.lower() != ".zip":

        out_path = out_path.with_suffix(out_path.suffix + ".zip")



    # Ensure parent directory exists

    out_path.parent.mkdir(parents=True, exist_ok=True)



    # Collect files

    print(_("Scanning {home} ...").format(home=display_hermes_home()))

    files_to_add: list[tuple[Path, Path]] = []  # (absolute, relative)

    skipped_dirs = set()



    for dirpath, dirnames, filenames in os.walk(hermes_root, followlinks=False):

        dp = Path(dirpath)

        rel_dir = dp.relative_to(hermes_root)



        # Prune excluded directories in-place so os.walk doesn't descend

        orig_dirnames = dirnames[:]

        dirnames[:] = [

            d for d in dirnames

            if d not in _EXCLUDED_DIRS

        ]

        for removed in set(orig_dirnames) - set(dirnames):

            skipped_dirs.add(str(rel_dir / removed))



        for fname in filenames:

            fpath = dp / fname

            rel = fpath.relative_to(hermes_root)



            if _should_exclude(rel):

                continue



            # Skip the output zip itself if it happens to be inside bookworm root

            try:

                if fpath.resolve() == out_path.resolve():

                    continue

            except (OSError, ValueError):

                pass



            files_to_add.append((fpath, rel))



    if not files_to_add:

        print(_("No files to back up."))

        return



    # Create the zip

    file_count = len(files_to_add)

    print(_("Backing up {file_count} files ...").format(file_count=file_count))



    total_bytes = 0

    errors = []

    t0 = time.monotonic()



    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:

        for i, (abs_path, rel_path) in enumerate(files_to_add, 1):

            try:

                # Safe copy for SQLite databases (handles WAL mode)

                if abs_path.suffix == ".db":

                    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:

                        tmp_db = Path(tmp.name)

                    if _safe_copy_db(abs_path, tmp_db):

                        zf.write(tmp_db, arcname=str(rel_path))

                        total_bytes += tmp_db.stat().st_size

                        tmp_db.unlink(missing_ok=True)

                    else:

                        tmp_db.unlink(missing_ok=True)

                        errors.append(f"  {rel_path}: " + _("SQLite safe copy failed"))

                        continue

                else:

                    zf.write(abs_path, arcname=str(rel_path))

                    total_bytes += abs_path.stat().st_size

            except (PermissionError, OSError, ValueError) as exc:

                errors.append(f"  {rel_path}: {exc}")

                continue



            # Progress every 500 files

            if i % 500 == 0:

                print(_("  {i}/{file_count} files ...").format(i=i, file_count=file_count))



    elapsed = time.monotonic() - t0

    zip_size = out_path.stat().st_size



    # Summary

    print()

    print(_("Backup complete: {out_path}").format(out_path=out_path))

    print(_("  Files:       {file_count}").format(file_count=file_count))

    print(_("  Original:    {_format_size}").format(_format_size=_format_size(total_bytes)))

    print(_("  Compressed:  {_format_size}").format(_format_size=_format_size(zip_size)))

    print(_("  Time:        {elapsed:.1f}s").format(elapsed=elapsed))



    if skipped_dirs:

        print(_("\n  Excluded directories:"))

        for d in sorted(skipped_dirs):

            print(f"    {d}/")



    if errors:

        print(_("\n  Warnings ({len} files skipped):").format(len=len(errors)))

        for e in errors[:10]:

            print(e)

        if len(errors) > 10:

            print(_("  ... and {len} more").format(len=len(errors) - 10))



    print(_("\nRestore with: bookworm import {out_path_name}").format(out_path_name=out_path.name))





# ---------------------------------------------------------------------------

# Import

# ---------------------------------------------------------------------------



def _validate_backup_zip(zf: zipfile.ZipFile) -> tuple[bool, str]:

    """Check that a zip looks like a BookwormPRO backup.



    Returns (ok, reason).

    """

    names = zf.namelist()

    if not names:

        return False, "zip archive is empty"



    # Look for telltale files that a bookworm home would have

    markers = {"config.yaml", ".env", "state.db"}

    found = set()

    for n in names:

        # Could be at the root or one level deep (if someone zipped the directory)

        basename = Path(n).name

        if basename in markers:

            found.add(basename)



    if not found:

        return False, (

            "zip does not appear to be a BookwormPRO backup "

            "(no config.yaml, .env, or state databases found)"

        )



    return True, ""





def _detect_prefix(zf: zipfile.ZipFile) -> str:

    """Detect if the zip has a common directory prefix wrapping all entries.



    Some tools zip as `.bookwormpro/config.yaml` instead of `config.yaml`.

    Returns the prefix to strip (empty string if none).

    """

    names = [n for n in zf.namelist() if not n.endswith("/")]

    if not names:

        return ""



    # Find common prefix

    parts_list = [Path(n).parts for n in names]



    # Check if all entries share a common first directory

    first_parts = {p[0] for p in parts_list if len(p) > 1}

    if len(first_parts) == 1:

        prefix = first_parts.pop()

        # Only strip if it looks like a bookworm dir name

        if prefix in (".bookwormpro", "bookworm"):

            return prefix + "/"



    return ""





def run_import(args) -> None:

    """Restore a BookwormPRO backup from a zip file."""

    zip_path = Path(args.zipfile).expanduser().resolve()



    if not zip_path.is_file():

        print(_("Error: File not found: {zip_path}").format(zip_path=zip_path))

        sys.exit(1)



    if not zipfile.is_zipfile(zip_path):

        print(_("Error: Not a valid zip file: {zip_path}").format(zip_path=zip_path))

        sys.exit(1)



    hermes_root = get_default_hermes_root()



    with zipfile.ZipFile(zip_path, "r") as zf:

        # Validate

        ok, reason = _validate_backup_zip(zf)

        if not ok:

            print(_("Error: {reason}").format(reason=reason))

            sys.exit(1)



        prefix = _detect_prefix(zf)

        members = [n for n in zf.namelist() if not n.endswith("/")]

        file_count = len(members)



        print(_("Backup contains {file_count} files").format(file_count=file_count))

        print(_("Target: {display_hermes_home}").format(display_hermes_home=display_hermes_home()))



        if prefix:

            print(f"Detected archive prefix: {prefix!r} (will be stripped)")



        # Check for existing installation

        has_config = (hermes_root / "config.yaml").exists()

        has_env = (hermes_root / ".env").exists()



        if (has_config or has_env) and not args.force:

            print()

            print(_("Warning: Target directory already has BookwormPRO configuration."))

            print(_("Importing will overwrite existing files with backup contents."))

            print()

            try:

                answer = input(_("Continue? [y/N] ")).strip().lower()

            except (EOFError, KeyboardInterrupt):

                print(_("\nAborted."))

                sys.exit(1)

            if answer not in ("y", "yes"):

                print(_("Aborted."))

                return



        # Extract

        print(_("\nImporting {file_count} files ...").format(file_count=file_count))

        hermes_root.mkdir(parents=True, exist_ok=True)



        errors = []

        restored = 0

        t0 = time.monotonic()



        for member in members:

            # Strip prefix if detected

            if prefix and member.startswith(prefix):

                rel = member[len(prefix):]

            else:

                rel = member



            if not rel:

                continue



            target = hermes_root / rel



            # Security: reject absolute paths and traversals

            try:

                target.resolve().relative_to(hermes_root.resolve())

            except ValueError:

                errors.append(f"  {rel}: path traversal blocked")

                continue



            try:

                target.parent.mkdir(parents=True, exist_ok=True)

                with zf.open(member) as src, open(target, "wb") as dst:

                    dst.write(src.read())

                restored += 1

            except (PermissionError, OSError) as exc:

                errors.append(f"  {rel}: {exc}")



            if restored % 500 == 0:

                print(_("  {restored}/{file_count} files ...").format(restored=restored, file_count=file_count))



        elapsed = time.monotonic() - t0



        # Summary

        print()

        print(_("Import complete: {restored} files restored in {elapsed:.1f}s").format(restored=restored, elapsed=elapsed))

        print(_("  Target: {display_hermes_home}").format(display_hermes_home=display_hermes_home()))



        if errors:

            print(_("\n  Warnings ({len} files skipped):").format(len=len(errors)))

            for e in errors[:10]:

                print(e)

            if len(errors) > 10:

                print(_("  ... and {len} more").format(len=len(errors) - 10))



        # Post-import: restore profile wrapper scripts

        profiles_dir = hermes_root / "profiles"

        restored_profiles = []

        if profiles_dir.is_dir():

            try:

                from bwm_cli.profiles import (

                    create_wrapper_script, check_alias_collision,

                    _is_wrapper_dir_in_path, _get_wrapper_dir,

                )

                for entry in sorted(profiles_dir.iterdir()):

                    if not entry.is_dir():

                        continue

                    profile_name = entry.name

                    # Only create wrappers for directories with config

                    if not (entry / "config.yaml").exists() and not (entry / ".env").exists():

                        continue

                    collision = check_alias_collision(profile_name)

                    if collision:

                        print(_("  Skipped alias '{profile_name}': {collision}").format(profile_name=profile_name, collision=collision))

                        restored_profiles.append((profile_name, False))

                    else:

                        wrapper = create_wrapper_script(profile_name)

                        restored_profiles.append((profile_name, wrapper is not None))



                if restored_profiles:

                    created = [n for n, ok in restored_profiles if ok]

                    skipped = [n for n, ok in restored_profiles if not ok]

                    if created:

                        print(_("\n  Profile aliases restored: {join_created}").format(join_created=', '.join(created)))

                    if skipped:

                        print(_("  Profile aliases skipped:  {join_skipped}").format(join_skipped=', '.join(skipped)))

                    if not _is_wrapper_dir_in_path():

                        print(_("\n  Note: {_get_wrapper_dir} is not in your PATH.").format(_get_wrapper_dir=_get_wrapper_dir()))

                        print(_("  Add to your shell config (~/.bashrc or ~/.zshrc):"))

                        print(_("    export PATH=\"$HOME/.local/bin:$PATH\""))

            except ImportError:

                # bwm_cli.profiles might not be available (fresh install)

                if any(profiles_dir.iterdir()):

                    print(_("\n  Profiles detected but aliases could not be created."))

                    print(_("  Run: bookworm profile list  (after installing bookworm)"))



        # Guidance

        print()

        if not (hermes_root / "bookwormpro").is_dir():

            print(_("Note: The bookwormpro codebase was not included in the backup."))

            print(_("  If this is a fresh install, run: bookworm update"))



        if restored_profiles:

            gw_profiles = [n for n, _ in restored_profiles]

            print(_("\nTo re-enable gateway services for profiles:"))

            for pname in gw_profiles:

                print(_("  bookworm -p {pname} gateway install").format(pname=pname))



        print(_("Done. Your BookwormPRO configuration has been restored."))





# ---------------------------------------------------------------------------

# Quick state snapshots (used by /snapshot slash command and bookworm backup --quick)

# ---------------------------------------------------------------------------



# Critical state files to include in quick snapshots (relative to BOOKWORMPRO_HOME).

# Everything else is either regeneratable (logs, cache) or managed separately

# (skills, repo, sessions/).

_QUICK_STATE_FILES = (

    "state.db",

    "config.yaml",

    ".env",

    "auth.json",

    "cron/jobs.json",

    "gateway_state.json",

    "channel_directory.json",

    "processes.json",

)



_QUICK_SNAPSHOTS_DIR = "state-snapshots"

_QUICK_DEFAULT_KEEP = 20





def _quick_snapshot_root(hermes_home: Optional[Path] = None) -> Path:

    home = hermes_home or get_hermes_home()

    return home / _QUICK_SNAPSHOTS_DIR





def create_quick_snapshot(

    label: Optional[str] = None,

    hermes_home: Optional[Path] = None,

) -> Optional[str]:

    """Create a quick state snapshot of critical files.



    Copies STATE_FILES to a timestamped directory under state-snapshots/.

    Auto-prunes old snapshots beyond the keep limit.



    Returns:

        Snapshot ID (timestamp-based), or None if no files found.

    """

    home = hermes_home or get_hermes_home()

    root = _quick_snapshot_root(home)



    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    snap_id = f"{ts}-{label}" if label else ts

    snap_dir = root / snap_id

    snap_dir.mkdir(parents=True, exist_ok=True)



    manifest: Dict[str, int] = {}  # rel_path -> file size



    for rel in _QUICK_STATE_FILES:

        src = home / rel

        if not src.exists() or not src.is_file():

            continue



        dst = snap_dir / rel

        dst.parent.mkdir(parents=True, exist_ok=True)



        try:

            if src.suffix == ".db":

                if not _safe_copy_db(src, dst):

                    continue

            else:

                shutil.copy2(src, dst)

            manifest[rel] = dst.stat().st_size

        except (OSError, PermissionError) as exc:

            logger.warning("Could not snapshot %s: %s", rel, exc)



    if not manifest:

        shutil.rmtree(snap_dir, ignore_errors=True)

        return None



    # Write manifest

    meta = {

        "id": snap_id,

        "timestamp": ts,

        "label": label,

        "file_count": len(manifest),

        "total_size": sum(manifest.values()),

        "files": manifest,

    }

    with open(snap_dir / "manifest.json", "w") as f:

        json.dump(meta, f, indent=2)



    # Auto-prune

    _prune_quick_snapshots(root, keep=_QUICK_DEFAULT_KEEP)



    logger.info("State snapshot created: %s (%d files)", snap_id, len(manifest))

    return snap_id





def list_quick_snapshots(

    limit: int = 20,

    hermes_home: Optional[Path] = None,

) -> List[Dict[str, Any]]:

    """List existing quick state snapshots, most recent first."""

    root = _quick_snapshot_root(hermes_home)

    if not root.exists():

        return []



    results = []

    for d in sorted(root.iterdir(), reverse=True):

        if not d.is_dir():

            continue

        manifest_path = d / "manifest.json"

        if manifest_path.exists():

            try:

                with open(manifest_path) as f:

                    results.append(json.load(f))

            except (json.JSONDecodeError, OSError):

                results.append({"id": d.name, "file_count": 0, "total_size": 0})

        if len(results) >= limit:

            break



    return results





def restore_quick_snapshot(

    snapshot_id: str,

    hermes_home: Optional[Path] = None,

) -> bool:

    """Restore state from a quick snapshot.



    Overwrites current state files with the snapshot's copies.

    Returns True if at least one file was restored.

    """

    home = hermes_home or get_hermes_home()

    root = _quick_snapshot_root(home)

    snap_dir = root / snapshot_id



    if not snap_dir.is_dir():

        return False



    manifest_path = snap_dir / "manifest.json"

    if not manifest_path.exists():

        return False



    with open(manifest_path) as f:

        meta = json.load(f)



    restored = 0

    for rel in meta.get("files", {}):

        src = snap_dir / rel

        if not src.exists():

            continue



        dst = home / rel

        dst.parent.mkdir(parents=True, exist_ok=True)



        try:

            if dst.suffix == ".db":

                # Atomic-ish replace for databases

                tmp = dst.parent / f".{dst.name}.snap_restore"

                shutil.copy2(src, tmp)

                dst.unlink(missing_ok=True)

                shutil.move(str(tmp), str(dst))

            else:

                shutil.copy2(src, dst)

            restored += 1

        except (OSError, PermissionError) as exc:

            logger.error("Failed to restore %s: %s", rel, exc)



    logger.info("Restored %d files from snapshot %s", restored, snapshot_id)

    return restored > 0





def _prune_quick_snapshots(root: Path, keep: int = _QUICK_DEFAULT_KEEP) -> int:

    """Remove oldest quick snapshots beyond the keep limit. Returns count deleted."""

    if not root.exists():

        return 0



    dirs = sorted(

        (d for d in root.iterdir() if d.is_dir()),

        key=lambda d: d.name,

        reverse=True,

    )



    deleted = 0

    for d in dirs[keep:]:

        try:

            shutil.rmtree(d)

            deleted += 1

        except OSError as exc:

            logger.warning("Failed to prune snapshot %s: %s", d.name, exc)



    return deleted





def prune_quick_snapshots(

    keep: int = _QUICK_DEFAULT_KEEP,

    hermes_home: Optional[Path] = None,

) -> int:

    """Manually prune quick snapshots. Returns count deleted."""

    return _prune_quick_snapshots(_quick_snapshot_root(hermes_home), keep=keep)





def run_quick_backup(args) -> None:
    """CLI entry point for bookworm backup --quick."""
    label = getattr(args, "label", None)
    snap_id = create_quick_snapshot(label=label)
    if snap_id:
        print(_("State snapshot created: {snap_id}").format(snap_id=snap_id))
        snaps = list_quick_snapshots()
        print(_("  {len} snapshot(s) stored in {display_hermes_home}/state-snapshots/").format(len=len(snaps), display_hermes_home=display_hermes_home()))
        print(_("  Restore with: /snapshot restore {snap_id}").format(snap_id=snap_id))
    else:
        print(_("No state files found to snapshot."))


# ===========================================================================
# 三层备份策略 (Three-Layer Backup: ZIP + Git + Remote)
# ===========================================================================

def run_backup_git(args) -> None:
    """第一层 + 第二层: 本地 ZIP + Git auto-commit。

    ``bookworm backup --git``
    1. 在 ~/.bookwormpro/ 下完成 git init (如果尚未初始化)
    2. 创建 .gitignore (排除日志/缓存/transient 文件)
    3. auto-commit 所有配置文件、会话数据库、技能、记忆
    """
    from bwm_constants import get_hermes_home, display_hermes_home
    hermes_root = get_hermes_home()

    if not hermes_root.is_dir():
        print(_("Error: BookwormPRO home directory not found at {hermes_root}").format(hermes_root=hermes_root))
        sys.exit(1)

    import subprocess

    git_dir = hermes_root / ".git"

    # Step 1: Git init if needed
    if not git_dir.is_dir():
        print(_(">>> 第一层: Git 初始化 {display_hermes_home}").format(display_hermes_home=display_hermes_home()))
        result = subprocess.run(
            ["git", "init"],
            cwd=str(hermes_root),
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(_("Error: git init failed: {result_stderr}").format(result_stderr=result.stderr))
            return
        # Write .gitignore
        gitignore = hermes_root / ".gitignore"
        gitignore.write_text("""# BookwormPRO Git Backup — .gitignore
# 排除 transient/regeneratable 文件
logs/
__pycache__/
*.pyc
*.pyo
*.pid
*.log
bookwormpro/          # 代码仓库，从 GitHub clone
node_modules/
*.tmp
audio_cache/
state-snapshots/      # quick snapshots 另存 zip
checkpoints/          # 文件变更快照太大
cron/cron.pid
gateway.pid
interrupt_debug.log
""")
        print(_("   [创建] .gitignore (排除 transient 文件)"))
        # Initial commit
        subprocess.run(
            ["git", "add", "-A"],
            cwd=str(hermes_root),
            capture_output=True,
        )
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        result = subprocess.run(
            ["git", "commit", "-m", f"Initial BookwormPRO backup — {stamp}"],
            cwd=str(hermes_root),
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            print(_("   [完成] 初始提交"))
        else:
            print(_("   [信息] {result}").format(result=result.stdout.strip()))

    # Step 2: Auto-commit
    print(_(">>> 第二层: Git 自动提交"))
    subprocess.run(
        ["git", "add", "-A"],
        cwd=str(hermes_root),
        capture_output=True,
    )

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result = subprocess.run(
        ["git", "commit", "-m", f"BookwormPRO auto-backup — {stamp}"],
        cwd=str(hermes_root),
        capture_output=True, text=True,
    )

    if result.returncode == 0:
        # Get commit stats
        log = subprocess.run(
            ["git", "log", "-1", "--oneline"],
            cwd=str(hermes_root),
            capture_output=True, text=True,
        )
        print(_("   [提交] {log}").format(log=log.stdout.strip()))
    elif "nothing to commit" in result.stdout or "nothing to commit" in result.stderr:
        print(_("   [跳过] 无变更，工作区干净"))
    else:
        print(_("   [信息] {result}").format(result=result.stdout.strip()))


def run_backup_push(args) -> None:
    """第三层: 推送到远程仓库 (GitHub)。

    ``bookworm backup --push``
    先执行 git commit (同 --git)，然后 git push 到远程。
    需要先配置 remote: git remote add origin <url>
    """
    from bwm_constants import get_hermes_home, display_hermes_home
    hermes_root = get_hermes_home()

    import subprocess

    # First, do git backup
    run_backup_git(args)

    # Then push to remote
    print(_(">>> 第三层: 推送远程"))

    # Check if remote is configured
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=str(hermes_root),
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(_("   [警告] 未配置远程仓库 (git remote)"))
        print(_("   配置命令: cd ~/.bookwormpro && git remote add origin <你的GitHub仓库URL>"))
        return

    remote_url = result.stdout.strip()
    print(_("   Remote: {remote_url}").format(remote_url=remote_url))

    # Check current branch
    branch_result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=str(hermes_root),
        capture_output=True, text=True,
    )
    branch = branch_result.stdout.strip() or "master"

    result = subprocess.run(
        ["git", "push", "-u", "origin", branch],
        cwd=str(hermes_root),
        capture_output=True, text=True,
        timeout=60,
    )

    if result.returncode == 0:
        print(_("   [完成] 已推送到 {remote_url}").format(remote_url=remote_url))
    else:
        print(_("   [错误] 推送失败:\n{result_stderr}").format(result_stderr=result.stderr))


def run_backup_full(args) -> None:
    """完整的 三层备份策略: ZIP + Git + Remote Push。

    ``bookworm backup --full``
    1. 本地 ZIP 打包 (完整快照)
    2. Git auto-commit (增量版本控制)
    3. Remote push (异地容灾)
    """
    from bwm_constants import get_hermes_home, display_hermes_home

    print("=" * 60)
    print(_("  BookwormPRO 三层备份策略"))
    print("=" * 60)

    # Layer 1: ZIP
    print(_("\n[1/3] 本地 ZIP 完整备份"))
    run_backup(args)

    # Layer 2: Git
    print(_("\n[2/3] Git 版本控制"))
    run_backup_git(args)

    # Layer 3: Remote
    print(_("\n[3/3] 远程同步"))
    run_backup_push(args)

    print(_("\n") + "=" * 60)
    print(_("  三层备份完成！"))
    print("=" * 60)
    print(_("  1. ZIP:  本地完整快照"))
    print(_("  2. Git:  增量版本控制"))
    print(_("  3. Push: 异地容灾备份"))
    print(_("\n  恢复: bookworm import <zipfile>"))
    print(_("        OR: git clone <remote> ~/.bookwormpro/"))
