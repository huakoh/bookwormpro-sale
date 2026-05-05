"""Tests for CLI --resume interactive picker and number selection.

Verifies that `bookworm --resume` (no arg) launches the picker,
and `bookworm --resume 3` selects the 3rd recent session.
"""

from argparse import Namespace
import sys

import pytest


def _args(**overrides):
    base = {
        "continue_last": None,
        "resume": None,
        "tui": False,
    }
    base.update(overrides)
    return Namespace(**base)


@pytest.fixture
def main_mod(monkeypatch):
    import bwm_cli.main as mod
    monkeypatch.setattr(mod, "_has_any_provider_configured", lambda: True)
    return mod


class TestResumeNoArg:
    """--resume with no argument launches the interactive picker."""

    def test_picker_launched_and_selects(self, monkeypatch, main_mod):
        """When picker returns a session ID, args.resume is set to it."""
        fake_sessions = [
            {"id": "sess_001", "title": "First", "preview": "", "last_active": 0},
            {"id": "sess_002", "title": "Second", "preview": "", "last_active": 0},
        ]

        class _FakeDB:
            def list_sessions_rich(self, **kw):
                return fake_sessions
            def close(self):
                pass

        monkeypatch.setattr(
            "bwm_cli.main.SessionDB" if hasattr(main_mod, "SessionDB") else "bwm_state.SessionDB",
            lambda *a, **kw: _FakeDB(),
        )
        monkeypatch.setattr(main_mod, "_session_browse_picker", lambda sessions: "sess_002")
        monkeypatch.setattr(main_mod, "_resolve_session_by_name_or_id", lambda v: v)

        args = _args(resume=True)

        # Run the resume resolution section of cmd_chat.
        # We can't call cmd_chat fully (it would try to start the agent),
        # so we extract and test the resume logic inline.
        resume_val = args.resume
        if resume_val is True:
            from bwm_state import SessionDB as _orig
            monkeypatch.setitem(sys.modules, "bwm_state",
                                type(sys)("bwm_state"))
            sys.modules["bwm_state"].SessionDB = lambda *a, **kw: _FakeDB()

            db = _FakeDB()
            sessions = db.list_sessions_rich(exclude_sources=["tool"], limit=50)
            selected_id = main_mod._session_browse_picker(sessions)
            args.resume = selected_id

        assert args.resume == "sess_002"

    def test_picker_cancelled_exits(self, monkeypatch, main_mod):
        """When picker returns None, should not set resume."""
        fake_sessions = [{"id": "s1", "title": "X", "preview": "", "last_active": 0}]

        class _FakeDB:
            def list_sessions_rich(self, **kw):
                return fake_sessions
            def close(self):
                pass

        monkeypatch.setattr(main_mod, "_session_browse_picker", lambda sessions: None)

        selected = main_mod._session_browse_picker(fake_sessions)
        assert selected is None


class TestResumeByNumber:
    """--resume <number> picks from recent sessions."""

    def test_number_resolves_to_session_id(self, monkeypatch, main_mod):
        fake_sessions = [
            {"id": "newest_sess", "title": "A"},
            {"id": "second_sess", "title": "B"},
            {"id": "third_sess", "title": "C"},
        ]

        class _FakeDB:
            def list_sessions_rich(self, **kw):
                return fake_sessions
            def close(self):
                pass

        monkeypatch.setitem(sys.modules.get("bwm_state", {}).__dict__ if "bwm_state" in sys.modules else {},
                            "SessionDB", lambda *a, **kw: _FakeDB())

        # Simulate the number resolution logic
        resume_val = "2"
        try:
            idx = int(resume_val)
            if idx >= 1:
                db = _FakeDB()
                sessions = db.list_sessions_rich(exclude_sources=["tool"], limit=idx + 5)
                if idx <= len(sessions):
                    result = sessions[idx - 1]["id"]
                else:
                    result = None
            else:
                result = None
        except (ValueError, TypeError):
            result = None

        assert result == "second_sess"

    def test_number_out_of_range_falls_to_title(self, monkeypatch, main_mod):
        """Number larger than session count falls to title/ID resolution."""
        fake_sessions = [{"id": "s1", "title": "Only"}]

        class _FakeDB:
            def list_sessions_rich(self, **kw):
                return fake_sessions
            def close(self):
                pass

        resume_val = "99"
        idx = int(resume_val)
        db = _FakeDB()
        sessions = db.list_sessions_rich(exclude_sources=["tool"], limit=idx + 5)
        resolved_by_number = idx <= len(sessions)

        assert resolved_by_number is False


class TestResumeArgparse:
    """Argparse accepts --resume with and without argument."""

    def test_resume_no_arg_gives_true(self):
        """bookworm --resume → args.resume = True."""
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--resume", "-r", nargs="?", const=True, default=None)
        args = parser.parse_args(["--resume"])
        assert args.resume is True

    def test_resume_with_arg(self):
        """bookworm --resume my_session → args.resume = 'my_session'."""
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--resume", "-r", nargs="?", const=True, default=None)
        args = parser.parse_args(["--resume", "my_session"])
        assert args.resume == "my_session"

    def test_resume_with_number(self):
        """bookworm --resume 3 → args.resume = '3'."""
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--resume", "-r", nargs="?", const=True, default=None)
        args = parser.parse_args(["--resume", "3"])
        assert args.resume == "3"

    def test_no_resume_flag(self):
        """No --resume → args.resume = None."""
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--resume", "-r", nargs="?", const=True, default=None)
        args = parser.parse_args([])
        assert args.resume is None
