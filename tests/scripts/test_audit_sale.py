"""Tests for scripts/audit-sale.py — I2 --verbose 输出控制."""

from unittest.mock import patch

import pytest

import sys
import importlib.util

# audit-sale.py 文件名含连字符, 无法直接 import, 用 spec 加载
_spec = importlib.util.spec_from_file_location(
    "audit_sale",
    str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scripts" / "audit-sale.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
run_audit = _mod.run_audit
COMPILE_TARGETS = _mod.COMPILE_TARGETS
INTERNAL_FILES = _mod.INTERNAL_FILES


def _fake_git_files(mapping: dict):
    """返回一个 mock, 根据 ref 返回不同的文件集合."""
    def _git_files(ref):
        return mapping.get(ref, set())
    return _git_files


class TestRunAuditVerbose:
    ORIGIN_FILES = {
        "agent/main.py",
        "agent/prompt_builder.py",       # COMPILE_TARGET
        "agent/skill_preprocessing.py",  # COMPILE_TARGET
        "agent/context_compressor.py",   # COMPILE_TARGET
        "agent/prompt_caching.py",       # COMPILE_TARGET
        "agent/redact.py",               # COMPILE_TARGET
        "agent/skill_crypto.py",         # COMPILE_TARGET
        "README.md",
        "skills/foo/SKILL.md",           # encrypted
        "skills/bar/SKILL.md",           # encrypted
        "scripts/build_sale.py",         # INTERNAL
    }
    SALE_FILES = {
        "agent/main.py",
        "agent/prompt_builder.cpython-312-x86_64-linux-gnu.so",
        "README.md",
        "skills/foo/SKILL.skill.enc",
        "skills/bar/SKILL.skill.enc",
    }

    @patch.object(_mod, "git_files")
    def test_verbose_false_truncates(self, mock_gf):
        mock_gf.side_effect = _fake_git_files({
            "HEAD": self.ORIGIN_FILES,
            "sale/master": self.SALE_FILES,
        })
        verdict, lines, ug, un = run_audit("HEAD", "sale/master", verbose=False)
        assert verdict == "PASS"
        text = "\n".join(lines)
        assert "--verbose" in text or "共" in text

    @patch.object(_mod, "git_files")
    def test_verbose_true_shows_all(self, mock_gf):
        mock_gf.side_effect = _fake_git_files({
            "HEAD": self.ORIGIN_FILES,
            "sale/master": self.SALE_FILES,
        })
        verdict, lines, ug, un = run_audit("HEAD", "sale/master", verbose=True)
        assert verdict == "PASS"
        text = "\n".join(lines)
        # verbose 模式不应出现截断提示
        assert "--verbose 查看全部" not in text

    @patch.object(_mod, "git_files")
    def test_unexpected_file_warns(self, mock_gf):
        sale_with_extra = self.SALE_FILES | {"secrets.txt"}
        mock_gf.side_effect = _fake_git_files({
            "HEAD": self.ORIGIN_FILES,
            "sale/master": sale_with_extra,
        })
        verdict, lines, ug, un = run_audit("HEAD", "sale/master")
        assert verdict == "WARN"
        assert "secrets.txt" in un

    @patch.object(_mod, "git_files")
    def test_empty_refs_returns_error(self, mock_gf):
        mock_gf.return_value = set()
        verdict, lines, _, _ = run_audit("HEAD", "sale/master")
        assert verdict == "ERROR"


class TestRunAuditClassification:
    @patch.object(_mod, "git_files")
    def test_compile_target_is_expected(self, mock_gf):
        origin = {"agent/skill_crypto.py", "README.md"}
        sale = {"README.md"}
        mock_gf.side_effect = _fake_git_files({"HEAD": origin, "sale/master": sale})
        verdict, lines, ug, un = run_audit("HEAD", "sale/master")
        assert verdict == "PASS"
        assert not ug

    @patch.object(_mod, "git_files")
    def test_internal_file_is_expected(self, mock_gf):
        origin = {"scripts/build_sale.py", "README.md"}
        sale = {"README.md"}
        mock_gf.side_effect = _fake_git_files({"HEAD": origin, "sale/master": sale})
        verdict, _, ug, _ = run_audit("HEAD", "sale/master")
        assert verdict == "PASS"
        assert not ug

    @patch.object(_mod, "git_files")
    def test_enc_new_is_expected(self, mock_gf):
        origin = {"README.md"}
        sale = {"README.md", "skills/bar/SKILL.skill.enc"}
        mock_gf.side_effect = _fake_git_files({"HEAD": origin, "sale/master": sale})
        verdict, _, _, un = run_audit("HEAD", "sale/master")
        assert verdict == "PASS"
        assert not un
