"""Smoke tests for the new doctor checks.

These checks are output-side-effect heavy (they print colored status lines)
so the contract we test is narrow: they must
  (a) not raise when called with default env,
  (b) populate the *issues* list correctly when something is wrong, and
  (c) leave the issues list empty on a healthy runtime.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import bwm_constants
from bwm_cli import doctor as _doctor


# ---------------------------------------------------------------------------
# _check_runtime_fs_capability
# ---------------------------------------------------------------------------

class TestRuntimeFsCheck:
    def test_native_does_not_raise_or_add_issues(self, monkeypatch, capsys):
        monkeypatch.setattr(bwm_constants, "is_native_install", lambda: True)
        monkeypatch.setattr(bwm_constants, "is_host_bridge_active", lambda: False)
        monkeypatch.setattr(bwm_constants, "is_container", lambda: False)
        monkeypatch.setattr(bwm_constants, "is_wsl", lambda: False)

        issues: list[str] = []
        _doctor._check_runtime_fs_capability(issues)
        assert issues == []
        out = capsys.readouterr().out
        assert "Native install" in out

    def test_host_bridge_does_not_add_issue(self, monkeypatch):
        monkeypatch.setattr(bwm_constants, "is_native_install", lambda: False)
        monkeypatch.setattr(bwm_constants, "is_host_bridge_active", lambda: True)
        monkeypatch.setattr(bwm_constants, "is_container", lambda: True)
        monkeypatch.setattr(bwm_constants, "is_wsl", lambda: False)

        issues: list[str] = []
        _doctor._check_runtime_fs_capability(issues)
        assert issues == []  # bridge is healthy, no issue

    def test_container_without_bridge_records_issue(self, monkeypatch):
        monkeypatch.setattr(bwm_constants, "is_native_install", lambda: False)
        monkeypatch.setattr(bwm_constants, "is_host_bridge_active", lambda: False)
        monkeypatch.setattr(bwm_constants, "is_container", lambda: True)
        monkeypatch.setattr(bwm_constants, "is_wsl", lambda: False)

        issues: list[str] = []
        _doctor._check_runtime_fs_capability(issues)
        assert len(issues) == 1
        assert "host bridge" in issues[0].lower()


# ---------------------------------------------------------------------------
# _check_memory_health
# ---------------------------------------------------------------------------

class TestMemoryHealth:
    def test_records_issue_when_both_files_missing(self, monkeypatch, tmp_path):
        # Point hermes_home at an empty tmp dir (no memories/ at all).
        monkeypatch.setattr(bwm_constants, "get_hermes_home", lambda: tmp_path)
        # Re-bind doctor's local import path: the function uses a local import
        # so we patch on bwm_constants only — that's where the function reads from.

        issues: list[str] = []
        _doctor._check_memory_health(issues)
        assert len(issues) == 1
        assert "missing" in issues[0].lower()

    def test_no_issue_when_files_have_entries(self, monkeypatch, tmp_path):
        mem_dir = tmp_path / "memories"
        mem_dir.mkdir()
        (mem_dir / "USER.md").write_text("§\nLanguage: English\n", encoding="utf-8")
        (mem_dir / "MEMORY.md").write_text("§\nFact about repo\n", encoding="utf-8")
        monkeypatch.setattr(bwm_constants, "get_hermes_home", lambda: tmp_path)

        issues: list[str] = []
        _doctor._check_memory_health(issues)
        assert issues == []


# ---------------------------------------------------------------------------
# _check_prompt_cache_freshness
# ---------------------------------------------------------------------------

class TestPromptCacheFreshness:
    def test_no_snapshot_does_not_add_issue(self, monkeypatch, tmp_path):
        snap_path = tmp_path / "snap.json"  # never created
        from agent import prompt_builder as _pb
        monkeypatch.setattr(_pb, "_skills_prompt_snapshot_path", lambda: snap_path)

        issues: list[str] = []
        _doctor._check_prompt_cache_freshness(issues)
        assert issues == []  # info, not an issue

    def test_fresh_snapshot_does_not_add_issue(self, monkeypatch, tmp_path, capsys):
        snap_path = tmp_path / "snap.json"
        snap_path.write_text(json.dumps({
            "version": 1,
            "code_dep_mtime_ns": 1_000_000_000_000_000,
        }), encoding="utf-8")
        from agent import prompt_builder as _pb
        monkeypatch.setattr(_pb, "_skills_prompt_snapshot_path", lambda: snap_path)
        monkeypatch.setattr(_pb, "_max_code_dep_mtime", lambda: 1_000_000_000_000_000)

        issues: list[str] = []
        _doctor._check_prompt_cache_freshness(issues)
        assert issues == []
        out = capsys.readouterr().out
        assert "current" in out.lower() or "成功" in out

    def test_stale_snapshot_warns_but_no_issue(self, monkeypatch, tmp_path):
        # A stale snapshot self-heals automatically next session — so it's a
        # warning surfaced to the user but not a hard issue requiring action.
        snap_path = tmp_path / "snap.json"
        snap_path.write_text(json.dumps({
            "version": 1,
            "code_dep_mtime_ns": 1_000_000_000_000_000,
        }), encoding="utf-8")
        from agent import prompt_builder as _pb
        monkeypatch.setattr(_pb, "_skills_prompt_snapshot_path", lambda: snap_path)
        monkeypatch.setattr(_pb, "_max_code_dep_mtime", lambda: 2_000_000_000_000_000)

        issues: list[str] = []
        _doctor._check_prompt_cache_freshness(issues)
        assert issues == []  # warn-only; auto-heal handles it
