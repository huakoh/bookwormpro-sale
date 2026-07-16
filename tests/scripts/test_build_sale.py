"""Tests for scripts/build_sale.py — I5 凭证扫描 + I1 SHA pinning 验证."""

import re
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.build_sale import scan_credentials, _CREDENTIAL_PATTERNS, SANITIZE_PAIRS


# ── I5: scan_credentials ──────────────────────────────────────────────────
# 测试假数据通过拼接构造, 非真实凭证


def _make_yaml(lines: list[str]) -> str:
    return "\n".join(lines) + "\n"


class TestScanCredentials:
    def test_clean_file_passes(self, tmp_path):
        dc = tmp_path / "docker-compose.yml"
        dc.write_text(_make_yaml([
            "version: '3'",
            "services:",
            "  web:",
            "    image: myapp:latest",
        ]), encoding="utf-8")
        assert scan_credentials(tmp_path) == []

    def test_detects_pw_keyword(self, tmp_path):
        kw = "pass" + "word"  # 动态拼接避开静态扫描
        dc = tmp_path / "docker-compose.yml"
        dc.write_text(_make_yaml([
            "services:",
            "  db:",
            "    environment:",
            f'      {kw}: "FakeTestVal1234"',
        ]), encoding="utf-8")
        findings = scan_credentials(tmp_path)
        assert len(findings) >= 1

    def test_detects_apikey_keyword(self, tmp_path):
        dc = tmp_path / "docker-compose.yml"
        dc.write_text(_make_yaml([
            "services:",
            "  app:",
            "    environment:",
            "      api" + "_key=sk-fake-test-key-0000",
        ]), encoding="utf-8")
        findings = scan_credentials(tmp_path)
        assert len(findings) >= 1

    def test_detects_pem_header(self, tmp_path):
        header = "-----BEGIN " + "PRIVATE KEY-----"
        dc = tmp_path / "docker-compose.yml"
        dc.write_text(_make_yaml([
            "data: |",
            f"  {header}",
            "  MIIEvQIBADANBgkq...",
        ]), encoding="utf-8")
        findings = scan_credentials(tmp_path)
        assert len(findings) >= 1

    def test_detects_user_path_residual(self, tmp_path):
        user_path = "C:\\Users\\" + "leesu" + "\\Desktop"
        dc = tmp_path / "docker-compose.yml"
        dc.write_text(_make_yaml([
            "volumes:",
            f"  - {user_path}:/data",
        ]), encoding="utf-8")
        findings = scan_credentials(tmp_path)
        assert len(findings) >= 1

    def test_skips_comments(self, tmp_path):
        kw = "pass" + "word"
        dc = tmp_path / "docker-compose.yml"
        dc.write_text(_make_yaml([
            f"# {kw}: fake-comment-value",
            "services:",
            "  web:",
            "    image: nginx",
        ]), encoding="utf-8")
        assert scan_credentials(tmp_path) == []

    def test_no_file_passes(self, tmp_path):
        assert scan_credentials(tmp_path) == []

    def test_dry_run_still_detects(self, tmp_path):
        kw = "sec" + "ret"
        dc = tmp_path / "docker-compose.yml"
        dc.write_text(f'  {kw}: "fake-test-value-1234"\n', encoding="utf-8")
        findings = scan_credentials(tmp_path, dry_run=True)
        assert len(findings) >= 1


# ── I1: SHA pinning 验证 (静态 YAML 检查) ──────────────────────────────────


class TestSHAPinning:
    WORKFLOW_PATH = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "build-sale.yml"

    def test_workflow_exists(self):
        assert self.WORKFLOW_PATH.exists(), "build-sale.yml not found"

    def test_no_unpinned_actions(self):
        content = self.WORKFLOW_PATH.read_text(encoding="utf-8")
        uses_lines = [
            line.strip() for line in content.splitlines()
            if line.strip().startswith("- uses:") or line.strip().startswith("uses:")
        ]
        assert len(uses_lines) >= 4, f"Expected >=4 uses: lines, got {len(uses_lines)}"

        sha_re = re.compile(r"actions/[\w-]+@[0-9a-f]{40}")
        for line in uses_lines:
            ref = line.split("uses:")[-1].strip()
            assert sha_re.search(ref), f"Unpinned action: {ref}"

    def test_version_comments_present(self):
        content = self.WORKFLOW_PATH.read_text(encoding="utf-8")
        uses_lines = [
            line.strip() for line in content.splitlines()
            if "uses:" in line and "actions/" in line
        ]
        for line in uses_lines:
            assert "#" in line, f"Missing version comment: {line}"
