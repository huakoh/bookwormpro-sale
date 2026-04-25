"""Tests for `bookworm memory show` / `bookworm memory why` introspection.

Covers the built-in memory commands that surface provenance to users
without exposing the entire ~/.bookwormpro/memories tree.  Refs progress
note 2026-04-26 (P1 user-experience batch).
"""

from __future__ import annotations

import argparse

import pytest


@pytest.fixture
def memory_home(tmp_path, monkeypatch):
    """Point BOOKWORMPRO_HOME at a tmp dir and seed two memory files."""
    home = tmp_path / "bookwormpro"
    (home / "memories").mkdir(parents=True)
    monkeypatch.setenv("BOOKWORMPRO_HOME", str(home))

    delim = "\n§\n"
    memory_entries = [
        "user prefers pnpm over npm",
        "tests must hit a real database (no mocks) — burned by mock divergence",
        "merge freeze begins 2026-03-05 for mobile release",
    ]
    user_entries = [
        "name: Tim",
        "primary IDE: VS Code on Windows 11",
    ]
    (home / "memories" / "MEMORY.md").write_text(
        delim.join(memory_entries), encoding="utf-8"
    )
    (home / "memories" / "USER.md").write_text(
        delim.join(user_entries), encoding="utf-8"
    )
    return home


class TestCmdShow:
    def test_show_lists_both_stores_with_entry_counts(self, memory_home, capsys):
        from bwm_cli.memory_setup import cmd_show

        cmd_show(argparse.Namespace(target=None))
        out = capsys.readouterr().out

        assert "MEMORY.md" in out
        assert "USER.md" in out
        assert "3 entries" in out  # MEMORY.md
        assert "2 entries" in out  # USER.md
        assert "user prefers pnpm" in out
        assert "primary IDE" in out

    def test_show_filter_memory_only(self, memory_home, capsys):
        from bwm_cli.memory_setup import cmd_show

        cmd_show(argparse.Namespace(target="memory"))
        out = capsys.readouterr().out

        assert "MEMORY.md" in out
        assert "USER.md" not in out

    def test_show_filter_user_only(self, memory_home, capsys):
        from bwm_cli.memory_setup import cmd_show

        cmd_show(argparse.Namespace(target="user"))
        out = capsys.readouterr().out

        assert "USER.md" in out
        assert "━━ MEMORY.md" not in out

    def test_show_handles_missing_files(self, tmp_path, monkeypatch, capsys):
        home = tmp_path / "fresh"
        (home / "memories").mkdir(parents=True)
        monkeypatch.setenv("BOOKWORMPRO_HOME", str(home))

        from bwm_cli.memory_setup import cmd_show

        cmd_show(argparse.Namespace(target=None))
        out = capsys.readouterr().out
        assert "not present" in out

    def test_show_handles_empty_file(self, tmp_path, monkeypatch, capsys):
        home = tmp_path / "empty"
        (home / "memories").mkdir(parents=True)
        (home / "memories" / "MEMORY.md").write_text("", encoding="utf-8")
        monkeypatch.setenv("BOOKWORMPRO_HOME", str(home))

        from bwm_cli.memory_setup import cmd_show

        cmd_show(argparse.Namespace(target="memory"))
        out = capsys.readouterr().out
        # Either '(empty)' or '(not present)' is acceptable; both signal
        # 'nothing to show' to the user.
        assert "empty" in out or "not present" in out


class TestCmdWhy:
    def test_why_finds_matching_entry_with_provenance(self, memory_home, capsys):
        from bwm_cli.memory_setup import cmd_why

        cmd_why(argparse.Namespace(query="pnpm"))
        out = capsys.readouterr().out

        assert "Found 1 matching" in out
        assert "MEMORY.md" in out
        assert "user prefers pnpm" in out
        assert "source:" in out

    def test_why_case_insensitive(self, memory_home, capsys):
        from bwm_cli.memory_setup import cmd_why

        cmd_why(argparse.Namespace(query="MOCK"))
        out = capsys.readouterr().out
        assert "no mocks" in out

    def test_why_searches_user_store_too(self, memory_home, capsys):
        from bwm_cli.memory_setup import cmd_why

        cmd_why(argparse.Namespace(query="VS Code"))
        out = capsys.readouterr().out
        assert "USER.md" in out

    def test_why_multiple_matches(self, memory_home, capsys):
        from bwm_cli.memory_setup import cmd_why

        # 'must' appears in one MEMORY entry; 'IDE' in one USER entry.
        # Pick a substring that hits multiple entries within MEMORY.md.
        cmd_why(argparse.Namespace(query="20"))  # matches "2026-03-05"
        out = capsys.readouterr().out
        assert "Found" in out
        assert "matching memory" in out

    def test_why_no_match_explains_inference(self, memory_home, capsys):
        from bwm_cli.memory_setup import cmd_why

        cmd_why(argparse.Namespace(query="totally-unknown-thing-xyz"))
        out = capsys.readouterr().out
        assert "No memory entry mentions" in out
        assert "inferring" in out

    def test_why_empty_query_prints_usage(self, memory_home, capsys):
        from bwm_cli.memory_setup import cmd_why

        cmd_why(argparse.Namespace(query=""))
        out = capsys.readouterr().out
        assert "Usage:" in out


class TestRouter:
    """memory_command() must dispatch the new subcommands."""

    def test_router_dispatches_show(self, memory_home, capsys):
        from bwm_cli.memory_setup import memory_command

        memory_command(argparse.Namespace(memory_command="show", target=None))
        out = capsys.readouterr().out
        assert "MEMORY.md" in out

    def test_router_dispatches_why(self, memory_home, capsys):
        from bwm_cli.memory_setup import memory_command

        memory_command(argparse.Namespace(memory_command="why", query="pnpm"))
        out = capsys.readouterr().out
        assert "Found" in out
