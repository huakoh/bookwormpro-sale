"""Tests for agent/skill_crypto.py — I3 线程安全 + I4 解密日志."""

import logging
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from agent.skill_crypto import (
    encrypt_skill,
    decrypt_skill,
    read_skill_content,
    find_skill_file,
    is_encrypted_skill,
    _cache_lock,
)


# ── 基础加解密 round-trip ──────────────────────────────────────────────────


class TestEncryptDecryptRoundTrip:
    LICENSE_KEY = "test-license-key-at-least-16-chars"

    def test_roundtrip(self):
        plaintext = "# My Skill\n\nThis is a test skill."
        encrypted = encrypt_skill(plaintext, self.LICENSE_KEY)
        decrypted = decrypt_skill(encrypted, self.LICENSE_KEY)
        assert decrypted == plaintext

    def test_roundtrip_with_shared_salt(self):
        import os
        salt = os.urandom(16)
        texts = ["skill A content", "skill B content", "skill C content"]
        for text in texts:
            enc = encrypt_skill(text, self.LICENSE_KEY, salt=salt)
            dec = decrypt_skill(enc, self.LICENSE_KEY)
            assert dec == text

    def test_wrong_key_raises(self):
        encrypted = encrypt_skill("secret", self.LICENSE_KEY)
        with pytest.raises(ValueError, match="Decryption failed"):
            decrypt_skill(encrypted, "wrong-key-that-is-long-enough")

    def test_truncated_data_raises(self):
        with pytest.raises(ValueError, match="too short"):
            decrypt_skill(b"\x01" + b"\x00" * 10, self.LICENSE_KEY)

    def test_bad_version_raises(self):
        encrypted = encrypt_skill("test", self.LICENSE_KEY)
        bad = bytes([0xFF]) + encrypted[1:]
        with pytest.raises(ValueError, match="Unsupported encryption version"):
            decrypt_skill(bad, self.LICENSE_KEY)


# ── I3: 线程安全 ──────────────────────────────────────────────────────────


class TestThreadSafety:
    LICENSE_KEY = "thread-test-key-at-least-16"

    def test_cache_lock_exists(self):
        assert isinstance(_cache_lock, type(threading.Lock()))

    def test_concurrent_decrypt(self):
        """多线程并发解密不抛异常且结果正确."""
        import os
        salt = os.urandom(16)
        plaintext = "concurrent test content"
        encrypted = encrypt_skill(plaintext, self.LICENSE_KEY, salt=salt)

        results = []
        errors = []

        def worker():
            try:
                result = decrypt_skill(encrypted, self.LICENSE_KEY)
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Errors in threads: {errors}"
        assert len(results) == 20
        assert all(r == plaintext for r in results)


# ── I4: read_skill_content 解密日志 ────────────────────────────────────────


class TestReadSkillContentLogging:
    def test_no_skill_file_returns_none(self, tmp_path):
        result = read_skill_content(tmp_path)
        assert result is None

    def test_plain_skill_reads(self, tmp_path):
        (tmp_path / "SKILL.md").write_text("# Plain skill", encoding="utf-8")
        result = read_skill_content(tmp_path)
        assert result == "# Plain skill"

    def test_decrypt_bad_key_logs_debug(self, tmp_path, caplog):
        enc_data = encrypt_skill("secret", "real-key-long-enough-16")
        (tmp_path / "SKILL.skill.enc").write_bytes(enc_data)

        with caplog.at_level(logging.DEBUG, logger="agent.skill_crypto"):
            result = read_skill_content(tmp_path, license_key="wrong-key-long-enough16")

        assert result is None
        assert any("bad key/data" in r.message for r in caplog.records)

    def test_decrypt_no_key_logs_debug(self, tmp_path, caplog):
        enc_data = encrypt_skill("secret", "real-key-long-enough-16")
        (tmp_path / "SKILL.skill.enc").write_bytes(enc_data)

        with patch("agent.skill_crypto.get_license_key", return_value=None):
            with caplog.at_level(logging.DEBUG, logger="agent.skill_crypto"):
                result = read_skill_content(tmp_path)

        assert result is None
        assert any("No license key" in r.message for r in caplog.records)

    def test_decrypt_io_error_logs_debug(self, tmp_path, caplog):
        (tmp_path / "SKILL.skill.enc").write_bytes(b"\x01" + b"\x00" * 50)

        with caplog.at_level(logging.DEBUG, logger="agent.skill_crypto"):
            result = read_skill_content(tmp_path, license_key="some-key-long-enough16")

        assert result is None
        assert any("bad key/data" in r.message or "I/O or other" in r.message
                    for r in caplog.records)


# ── find_skill_file / is_encrypted_skill ───────────────────────────────────


class TestFindSkillFile:
    def test_prefers_plain(self, tmp_path):
        (tmp_path / "SKILL.md").write_text("plain")
        (tmp_path / "SKILL.skill.enc").write_bytes(b"enc")
        path, is_enc = find_skill_file(tmp_path)
        assert path == tmp_path / "SKILL.md"
        assert not is_enc

    def test_finds_encrypted(self, tmp_path):
        (tmp_path / "SKILL.skill.enc").write_bytes(b"enc")
        path, is_enc = find_skill_file(tmp_path)
        assert path == tmp_path / "SKILL.skill.enc"
        assert is_enc

    def test_empty_dir(self, tmp_path):
        path, is_enc = find_skill_file(tmp_path)
        assert path is None
        assert not is_enc

    def test_is_encrypted_skill(self):
        assert is_encrypted_skill(Path("foo/SKILL.skill.enc"))
        assert not is_encrypted_skill(Path("foo/SKILL.md"))
        assert not is_encrypted_skill(Path("foo/bar.enc"))
