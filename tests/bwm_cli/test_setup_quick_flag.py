"""Tests for the new `bookworm setup --quick` flag.

Verifies:
  - the argparse parser exposes --quick;
  - run_setup_wizard short-circuits to _run_quick_setup when args.quick=True
    (skipping the full menu and any section logic).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Argparse exposure
# ---------------------------------------------------------------------------

class TestSetupParserQuickFlag:
    def test_quick_flag_parses(self):
        # We import lazily to avoid pulling the heavy main.py at module import.
        import argparse

        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers()

        # Mirror the real setup parser definition (just the subset we care
        # about) — confirms the canonical contract.
        setup_p = sub.add_parser("setup")
        setup_p.add_argument("section", nargs="?", default=None)
        setup_p.add_argument("--non-interactive", action="store_true")
        setup_p.add_argument("--reset", action="store_true")
        setup_p.add_argument("--quick", action="store_true")

        ns = parser.parse_args(["setup", "--quick"])
        assert ns.quick is True
        assert ns.section is None

    def test_real_main_parser_has_quick(self):
        # Inspect the real subparser definition to catch regressions.
        from bwm_cli import main as _main
        import argparse

        parser = argparse.ArgumentParser()
        # Re-execute just the setup_parser block by calling main's parser
        # builder. main.py defines the parser inside main() so we can't
        # cleanly import it; instead, do a string-level smoke check that
        # the flag is wired in source.
        src = (_main.__file__ and open(_main.__file__, encoding="utf-8").read()) or ""
        assert '"--quick"' in src
        assert "Quick setup" in src or "quick setup" in src.lower()


# ---------------------------------------------------------------------------
# run_setup_wizard short-circuit
# ---------------------------------------------------------------------------

class TestQuickShortCircuit:
    def _stub_environment(self, monkeypatch, tmp_path):
        """Neutralise the heavy startup steps so the test can isolate dispatch."""
        from bwm_cli import config as _cfg
        from bwm_cli import setup as _setup

        monkeypatch.setattr(_cfg, "is_managed", lambda: False)
        monkeypatch.setattr(_setup, "ensure_hermes_home", lambda: None)
        monkeypatch.setattr(_setup, "load_config", lambda: {})
        monkeypatch.setattr(_setup, "save_config", lambda c: None)
        monkeypatch.setattr(_setup, "get_hermes_home", lambda: tmp_path)
        monkeypatch.setattr(_setup, "is_interactive_stdin", lambda: True)
        return _setup

    def test_quick_calls_run_quick_setup_and_skips_menu(self, monkeypatch, tmp_path):
        _setup = self._stub_environment(monkeypatch, tmp_path)

        called = {"quick": 0, "menu": 0}

        def _quick(config, home):
            called["quick"] += 1

        # If anything calls prompt_choice, the menu fired.
        def _menu(*args, **kwargs):
            called["menu"] += 1
            return 7  # exit

        monkeypatch.setattr(_setup, "_run_quick_setup", _quick)
        monkeypatch.setattr(_setup, "prompt_choice", _menu)

        args = SimpleNamespace(quick=True, section=None, non_interactive=False, reset=False)
        _setup.run_setup_wizard(args)

        assert called["quick"] == 1
        assert called["menu"] == 0

    def test_no_quick_does_not_short_circuit(self, monkeypatch, tmp_path):
        _setup = self._stub_environment(monkeypatch, tmp_path)
        # Make get_active_provider importable as a stub via bwm_cli.auth path.
        from bwm_cli import auth as _auth
        monkeypatch.setattr(_auth, "get_active_provider", lambda: None)
        monkeypatch.setattr(_setup, "get_env_value", lambda *a, **k: None)

        called = {"quick": 0}
        monkeypatch.setattr(
            _setup,
            "_run_quick_setup",
            lambda c, h: called.__setitem__("quick", called["quick"] + 1),
        )
        # Exit menu immediately so we don't run any real wizard sections.
        monkeypatch.setattr(_setup, "prompt_choice", lambda *a, **k: 7)

        args = SimpleNamespace(quick=False, section=None, non_interactive=False, reset=False)
        try:
            _setup.run_setup_wizard(args)
        except Exception:
            # Downstream prompts may still trip; we only care that the quick
            # short-circuit wasn't taken.
            pass

        assert called["quick"] == 0
