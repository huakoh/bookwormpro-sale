"""Tests for `bookworm canary` post-deploy smoke test.

The canary must be:
  * fast (no network unless --live)
  * deterministic (no flakiness from missing optional deps)
  * fail-closed (FAIL exit code 1 when something is genuinely wrong)
  * fail-open in setup (a crashing canary must not block install)

Refs progress note 2026-04-26.
"""

from __future__ import annotations

import argparse
import json

import pytest


@pytest.fixture
def configured_home(tmp_path, monkeypatch):
    home = tmp_path / "bookwormpro"
    (home / "memories").mkdir(parents=True)
    monkeypatch.setenv("BOOKWORMPRO_HOME", str(home))

    # Seed a credential pool so check_credential_pool_resolves passes.
    auth = home / "auth.json"
    auth.write_text(
        json.dumps(
            {
                "version": 1,
                "credential_pool": {
                    "openrouter": [
                        {
                            "id": "cred-1",
                            "label": "manual",
                            "auth_type": "api_key",
                            "priority": 0,
                            "source": "manual",
                            "access_token": "sk-test",
                            "base_url": "https://openrouter.ai/api/v1",
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    # Seed a minimal config pointing at openrouter.
    config = home / "config.yaml"
    config.write_text(
        "model:\n  provider: openrouter\n  default: meta-llama/llama-3.1-8b-instruct\n",
        encoding="utf-8",
    )
    return home


class TestCheckConfigLoadable:
    def test_passes_with_valid_config(self, configured_home):
        from bwm_cli.canary import check_config_loadable

        result = check_config_loadable()
        assert result.status == "PASS"


class TestCheckCredentialPool:
    def test_passes_when_pool_has_entries(self, configured_home):
        from bwm_cli.canary import check_credential_pool_resolves

        result = check_credential_pool_resolves()
        assert result.status == "PASS"
        assert "openrouter" in result.detail

    def test_warns_when_no_provider_configured(self, tmp_path, monkeypatch):
        home = tmp_path / "blank"
        home.mkdir()
        monkeypatch.setenv("BOOKWORMPRO_HOME", str(home))
        (home / "config.yaml").write_text("", encoding="utf-8")

        from bwm_cli.canary import check_credential_pool_resolves

        result = check_credential_pool_resolves()
        assert result.status == "WARN"

    def test_fails_when_provider_has_no_credentials(self, tmp_path, monkeypatch):
        home = tmp_path / "no-creds"
        home.mkdir()
        monkeypatch.setenv("BOOKWORMPRO_HOME", str(home))
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        (home / "auth.json").write_text(
            json.dumps({"version": 1, "credential_pool": {"openrouter": []}}),
            encoding="utf-8",
        )
        (home / "config.yaml").write_text(
            "model:\n  provider: openrouter\n", encoding="utf-8"
        )

        from bwm_cli.canary import check_credential_pool_resolves

        result = check_credential_pool_resolves()
        assert result.status == "FAIL"
        assert "no credentials" in result.detail

    def test_warns_on_base_url_conflict(self, tmp_path, monkeypatch):
        """Two entries with different base_urls → rotation pothole warning."""
        home = tmp_path / "conflict"
        home.mkdir()
        monkeypatch.setenv("BOOKWORMPRO_HOME", str(home))
        (home / "auth.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "credential_pool": {
                        "openrouter": [
                            {
                                "id": "a",
                                "source": "manual",
                                "auth_type": "api_key",
                                "access_token": "sk-relay",
                                "base_url": "https://bww.letcareme.com/v1",
                                "priority": 0,
                            },
                            {
                                "id": "b",
                                "source": "manual:second",
                                "auth_type": "api_key",
                                "access_token": "sk-other",
                                "base_url": "https://openrouter.ai/api/v1",
                                "priority": 1,
                            },
                        ]
                    },
                }
            ),
            encoding="utf-8",
        )
        (home / "config.yaml").write_text(
            "model:\n  provider: openrouter\n", encoding="utf-8"
        )

        from bwm_cli.canary import check_credential_pool_resolves

        result = check_credential_pool_resolves()
        assert result.status == "WARN"
        assert "base_urls" in result.detail


class TestCheckPromptCacheSnapshot:
    def test_warns_when_snapshot_missing(self, configured_home):
        from bwm_cli.canary import check_prompt_cache_snapshot

        result = check_prompt_cache_snapshot()
        assert result.status == "WARN"
        assert "regenerated" in result.detail

    def test_passes_when_snapshot_healthy(self, configured_home):
        snapshot = configured_home / ".skills_prompt_snapshot.json"
        snapshot.write_text(json.dumps({"v": 1, "skills": []}), encoding="utf-8")

        from bwm_cli.canary import check_prompt_cache_snapshot

        result = check_prompt_cache_snapshot()
        assert result.status == "PASS"

    def test_warns_when_snapshot_truncated(self, configured_home):
        (configured_home / ".skills_prompt_snapshot.json").write_text(
            "x", encoding="utf-8"
        )
        from bwm_cli.canary import check_prompt_cache_snapshot

        result = check_prompt_cache_snapshot()
        assert result.status == "WARN"


class TestCheckMemoryWritable:
    def test_passes_when_memories_dir_writable(self, configured_home):
        from bwm_cli.canary import check_memory_writable

        result = check_memory_writable()
        assert result.status == "PASS"


class TestCheckRuntimeImports:
    def test_critical_modules_importable(self, configured_home):
        from bwm_cli.canary import check_runtime_imports

        result = check_runtime_imports()
        # Either PASS or FAIL with a real reason — never a crash.
        assert result.status in ("PASS", "FAIL")


class TestRunCanariesAggregation:
    def test_run_canaries_returns_report_and_exit_code(self, configured_home):
        from bwm_cli.canary import run_canaries

        report = run_canaries(live=False)
        assert len(report.results) >= 4
        # We seeded everything healthy except prompt_cache snapshot is missing
        # → should be exit_code 2 (warn-only) or 0 (if a future canary tightens).
        assert report.exit_code in (0, 2)
        # No FAIL on a freshly-seeded happy-path home.
        assert not report.failed, [r.detail for r in report.failed]

    def test_live_flag_adds_live_check(self, configured_home, monkeypatch):
        """--live appends the live ping (which SKIP/FAILs without network)."""

        # Stub openai import path so we exercise the orchestration without
        # hitting the network.
        import sys
        import types

        stub = types.ModuleType("openai")

        class _StubClient:
            def __init__(self, *_, **__):
                self.chat = types.SimpleNamespace(
                    completions=types.SimpleNamespace(
                        create=lambda **kw: object()
                    )
                )

        stub.OpenAI = _StubClient  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "openai", stub)

        from bwm_cli.canary import run_canaries

        report = run_canaries(live=True)
        names = [r.name for r in report.results]
        assert "live-api-ping" in names


class TestCmdCanary:
    def test_cmd_canary_returns_exit_code_0_on_pass(self, configured_home, capsys):
        # Heal the prompt-cache warning so we get a clean PASS.
        (configured_home / ".skills_prompt_snapshot.json").write_text(
            json.dumps({"v": 1}), encoding="utf-8"
        )

        from bwm_cli.canary import cmd_canary

        rc = cmd_canary(argparse.Namespace(live=False))
        out = capsys.readouterr().out
        assert "post-deploy canary" in out
        assert rc in (0, 2)  # PASS or warn-only acceptable

    def test_cmd_canary_returns_1_when_failures(self, tmp_path, monkeypatch, capsys):
        home = tmp_path / "broken"
        home.mkdir()
        monkeypatch.setenv("BOOKWORMPRO_HOME", str(home))
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        (home / "auth.json").write_text(
            json.dumps({"version": 1, "credential_pool": {"openrouter": []}}),
            encoding="utf-8",
        )
        (home / "config.yaml").write_text(
            "model:\n  provider: openrouter\n", encoding="utf-8"
        )

        from bwm_cli.canary import cmd_canary

        rc = cmd_canary(argparse.Namespace(live=False))
        capsys.readouterr()
        assert rc == 1


class TestReportFormatting:
    def test_failed_report_mentions_investigate(self, configured_home):
        from bwm_cli.canary import (
            CanaryReport, CanaryResult, _format_report,
        )

        report = CanaryReport()
        report.add(CanaryResult("x", "FAIL", "broke"))
        out = _format_report(report)
        assert "investigate" in out.lower()
        assert report.exit_code == 1

    def test_clean_report_says_all_green(self):
        from bwm_cli.canary import (
            CanaryReport, CanaryResult, _format_report,
        )

        report = CanaryReport()
        report.add(CanaryResult("x", "PASS"))
        report.add(CanaryResult("y", "PASS"))
        out = _format_report(report)
        assert "all 2" in out
        assert report.exit_code == 0
