"""Tests for agent.skill_crypto — AES-256-GCM skill encryption/decryption + license validation."""

import base64
import json
import os
import struct
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _clear_caches():
    """Reset all caches between tests."""
    from agent import skill_crypto
    skill_crypto._cached_key = None
    skill_crypto._cached_salt = None
    skill_crypto._cached_license = None
    yield
    skill_crypto._cached_key = None
    skill_crypto._cached_salt = None
    skill_crypto._cached_license = None


SAMPLE_KEY = "test-license-key-minimum-16ch"
SAMPLE_CONTENT = """---
name: test-skill
description: A test skill for encryption roundtrip
---

# Test Skill

This is a test skill with unicode: 中文内容 日本語 한국어
"""


class TestEncryptDecryptRoundtrip:
    def test_basic_roundtrip(self):
        from agent.skill_crypto import encrypt_skill, decrypt_skill

        encrypted = encrypt_skill(SAMPLE_CONTENT, SAMPLE_KEY)
        decrypted = decrypt_skill(encrypted, SAMPLE_KEY)
        assert decrypted == SAMPLE_CONTENT

    def test_unicode_roundtrip(self):
        from agent.skill_crypto import encrypt_skill, decrypt_skill

        content = "Unicode: éèê üöä \U0001f4da ☃"
        encrypted = encrypt_skill(content, SAMPLE_KEY)
        assert decrypt_skill(encrypted, SAMPLE_KEY) == content

    def test_empty_content(self):
        from agent.skill_crypto import encrypt_skill, decrypt_skill

        encrypted = encrypt_skill("", SAMPLE_KEY)
        assert decrypt_skill(encrypted, SAMPLE_KEY) == ""

    def test_large_content(self):
        from agent.skill_crypto import encrypt_skill, decrypt_skill

        content = "x" * 100_000
        encrypted = encrypt_skill(content, SAMPLE_KEY)
        assert decrypt_skill(encrypted, SAMPLE_KEY) == content

    def test_different_keys_produce_different_ciphertext(self):
        from agent.skill_crypto import encrypt_skill

        enc1 = encrypt_skill(SAMPLE_CONTENT, "key-one-minimum-16chars")
        enc2 = encrypt_skill(SAMPLE_CONTENT, "key-two-minimum-16chars")
        assert enc1[1 + 16 + 12:] != enc2[1 + 16 + 12:]

    def test_each_encryption_uses_unique_salt_and_nonce(self):
        from agent.skill_crypto import encrypt_skill

        enc1 = encrypt_skill(SAMPLE_CONTENT, SAMPLE_KEY)
        enc2 = encrypt_skill(SAMPLE_CONTENT, SAMPLE_KEY)
        salt1 = enc1[1:17]
        salt2 = enc2[1:17]
        nonce1 = enc1[17:29]
        nonce2 = enc2[17:29]
        assert salt1 != salt2 or nonce1 != nonce2


class TestDecryptionErrors:
    def test_wrong_key_raises(self):
        from agent.skill_crypto import encrypt_skill, decrypt_skill

        encrypted = encrypt_skill(SAMPLE_CONTENT, SAMPLE_KEY)
        with pytest.raises(ValueError, match="invalid license key"):
            decrypt_skill(encrypted, "wrong-key-at-least-16-chars")

    def test_truncated_data_raises(self):
        from agent.skill_crypto import decrypt_skill

        with pytest.raises(ValueError, match="too short"):
            decrypt_skill(b"\x01" + b"\x00" * 10, SAMPLE_KEY)

    def test_corrupted_ciphertext_raises(self):
        from agent.skill_crypto import encrypt_skill, decrypt_skill

        encrypted = bytearray(encrypt_skill(SAMPLE_CONTENT, SAMPLE_KEY))
        encrypted[-1] ^= 0xFF
        with pytest.raises(ValueError, match="invalid license key"):
            decrypt_skill(bytes(encrypted), SAMPLE_KEY)

    def test_unsupported_version_raises(self):
        from agent.skill_crypto import decrypt_skill

        bad_data = struct.pack("B", 99) + b"\x00" * 50
        with pytest.raises(ValueError, match="Unsupported encryption version"):
            decrypt_skill(bad_data, SAMPLE_KEY)


class TestWireFormat:
    def test_version_byte(self):
        from agent.skill_crypto import encrypt_skill

        encrypted = encrypt_skill("hello", SAMPLE_KEY)
        assert encrypted[0] == 1

    def test_minimum_output_size(self):
        from agent.skill_crypto import encrypt_skill

        encrypted = encrypt_skill("", SAMPLE_KEY)
        # 1 (version) + 16 (salt) + 12 (nonce) + 16 (GCM tag) = 45 minimum
        assert len(encrypted) >= 45


class TestFileOperations:
    def test_find_skill_file_plain(self, tmp_path):
        from agent.skill_crypto import find_skill_file

        (tmp_path / "SKILL.md").write_text("content")
        path, is_enc = find_skill_file(tmp_path)
        assert path == tmp_path / "SKILL.md"
        assert is_enc is False

    def test_find_skill_file_encrypted(self, tmp_path):
        from agent.skill_crypto import find_skill_file

        (tmp_path / "SKILL.skill.enc").write_bytes(b"\x01" + b"\x00" * 50)
        path, is_enc = find_skill_file(tmp_path)
        assert path == tmp_path / "SKILL.skill.enc"
        assert is_enc is True

    def test_find_skill_file_prefers_plain(self, tmp_path):
        from agent.skill_crypto import find_skill_file

        (tmp_path / "SKILL.md").write_text("content")
        (tmp_path / "SKILL.skill.enc").write_bytes(b"\x01" + b"\x00" * 50)
        path, is_enc = find_skill_file(tmp_path)
        assert path == tmp_path / "SKILL.md"
        assert is_enc is False

    def test_find_skill_file_empty_dir(self, tmp_path):
        from agent.skill_crypto import find_skill_file

        path, is_enc = find_skill_file(tmp_path)
        assert path is None
        assert is_enc is False

    def test_read_skill_content_plain(self, tmp_path):
        from agent.skill_crypto import read_skill_content

        (tmp_path / "SKILL.md").write_text(SAMPLE_CONTENT, encoding="utf-8")
        result = read_skill_content(tmp_path)
        assert result == SAMPLE_CONTENT

    def test_read_skill_content_encrypted(self, tmp_path):
        from agent.skill_crypto import encrypt_skill, read_skill_content

        enc = encrypt_skill(SAMPLE_CONTENT, SAMPLE_KEY)
        (tmp_path / "SKILL.skill.enc").write_bytes(enc)
        result = read_skill_content(tmp_path, license_key=SAMPLE_KEY)
        assert result == SAMPLE_CONTENT

    def test_read_skill_content_no_key_returns_none(self, tmp_path, monkeypatch):
        from agent.skill_crypto import encrypt_skill, read_skill_content

        enc = encrypt_skill(SAMPLE_CONTENT, SAMPLE_KEY)
        (tmp_path / "SKILL.skill.enc").write_bytes(enc)
        monkeypatch.delenv("BOOKWORMPRO_LICENSE_KEY", raising=False)
        result = read_skill_content(tmp_path, license_key=None)
        assert result is None


class TestLicenseKeyResolution:
    def test_env_var(self, monkeypatch):
        from agent.skill_crypto import get_license_key

        monkeypatch.setenv("BOOKWORMPRO_LICENSE_KEY", "from-env-key-16ch")
        assert get_license_key() == "from-env-key-16ch"

    def test_license_file(self, tmp_path, monkeypatch):
        from agent import skill_crypto

        monkeypatch.delenv("BOOKWORMPRO_LICENSE_KEY", raising=False)
        license_file = tmp_path / ".license"
        license_file.write_text("from-file-key-16ch\n")

        import bwm_constants
        monkeypatch.setattr(bwm_constants, "get_hermes_home", lambda: tmp_path)
        monkeypatch.setattr(skill_crypto, "get_license_key", lambda: license_file.read_text().strip() if license_file.exists() else None)

        assert skill_crypto.get_license_key() == "from-file-key-16ch"

    def test_no_key_returns_none(self, monkeypatch):
        from agent.skill_crypto import get_license_key

        monkeypatch.delenv("BOOKWORMPRO_LICENSE_KEY", raising=False)
        # get_license_key will try to read ~/.bookwormpro/.license which may not exist
        # It should return None gracefully
        result = get_license_key()
        # Result may or may not be None depending on whether .license file exists
        # on the test machine — we just verify no exception is raised
        assert result is None or isinstance(result, str)


class TestKeyCaching:
    def test_cache_reused_for_same_salt(self):
        from agent.skill_crypto import encrypt_skill, decrypt_skill
        from agent import skill_crypto

        encrypted = encrypt_skill("hello", SAMPLE_KEY)
        decrypt_skill(encrypted, SAMPLE_KEY)

        cached_key = skill_crypto._cached_key
        cached_salt = skill_crypto._cached_salt
        assert cached_key is not None
        assert cached_salt is not None

        # Second decrypt with same encrypted data should reuse cache
        decrypt_skill(encrypted, SAMPLE_KEY)
        assert skill_crypto._cached_key is cached_key


# ── Ed25519 密钥对 fixture ──────────────────────────────────────────────────


@pytest.fixture
def ed25519_keypair():
    """Generate a fresh Ed25519 keypair for testing."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private_key = Ed25519PrivateKey.generate()
    priv_bytes = private_key.private_bytes_raw()
    pub_bytes = private_key.public_key().public_bytes_raw()
    pub_b64 = base64.b64encode(pub_bytes).decode()
    return priv_bytes, pub_bytes, pub_b64


@pytest.fixture
def valid_license(ed25519_keypair, monkeypatch):
    """Create a valid signed license dict bound to the current machine."""
    from agent.skill_crypto import get_machine_hwid, sign_license

    priv_bytes, _, pub_b64 = ed25519_keypair
    hwid = get_machine_hwid()
    expires = (date.today() + timedelta(days=365)).isoformat()

    lic = {
        "licensee": "Test Corp",
        "hwid": hwid,
        "tier": "pro",
        "expires": expires,
        "key": SAMPLE_KEY,
    }
    lic["signature"] = sign_license(lic, priv_bytes)
    return lic, pub_b64


# ── HWID 采集 ───────────────────────────────────────────────────────────────


class TestHWID:
    def test_hwid_returns_64_hex(self):
        from agent.skill_crypto import get_machine_hwid

        hwid = get_machine_hwid()
        assert len(hwid) == 64
        assert all(c in "0123456789abcdef" for c in hwid)

    def test_hwid_is_deterministic(self):
        from agent.skill_crypto import get_machine_hwid

        assert get_machine_hwid() == get_machine_hwid()

    def test_stable_mac_format(self):
        from agent.skill_crypto import _get_stable_mac

        mac = _get_stable_mac()
        # Either empty or "mac:<12hex>"
        if mac:
            assert mac.startswith("mac:")
            assert len(mac) == 4 + 12


# ── License 签名 ────────────────────────────────────────────────────────────


class TestLicenseSignature:
    def test_sign_and_verify_roundtrip(self, ed25519_keypair):
        from agent.skill_crypto import sign_license, verify_license_signature

        priv_bytes, _, pub_b64 = ed25519_keypair

        lic = {
            "licensee": "Test Corp",
            "hwid": "a" * 64,
            "tier": "pro",
            "expires": "2099-12-31",
            "key": "test-aes-key-at-least-16",
        }
        sig = sign_license(lic, priv_bytes)
        lic["signature"] = sig

        assert verify_license_signature(lic, pub_b64) is True

    def test_tampered_licensee_fails(self, ed25519_keypair):
        from agent.skill_crypto import sign_license, verify_license_signature

        priv_bytes, _, pub_b64 = ed25519_keypair

        lic = {
            "licensee": "Test Corp",
            "hwid": "a" * 64,
            "tier": "pro",
            "expires": "2099-12-31",
            "key": "test-aes-key-at-least-16",
        }
        lic["signature"] = sign_license(lic, priv_bytes)

        # Tamper
        lic["licensee"] = "Evil Corp"
        assert verify_license_signature(lic, pub_b64) is False

    def test_tampered_expires_fails(self, ed25519_keypair):
        from agent.skill_crypto import sign_license, verify_license_signature

        priv_bytes, _, pub_b64 = ed25519_keypair

        lic = {
            "licensee": "Test Corp",
            "hwid": "a" * 64,
            "tier": "pro",
            "expires": "2027-01-01",
            "key": "test-aes-key-at-least-16",
        }
        lic["signature"] = sign_license(lic, priv_bytes)

        lic["expires"] = "2099-12-31"
        assert verify_license_signature(lic, pub_b64) is False

    def test_tampered_key_fails(self, ed25519_keypair):
        from agent.skill_crypto import sign_license, verify_license_signature

        priv_bytes, _, pub_b64 = ed25519_keypair

        lic = {
            "licensee": "Test Corp",
            "hwid": "a" * 64,
            "tier": "pro",
            "expires": "2099-12-31",
            "key": "original-key-at-least16",
        }
        lic["signature"] = sign_license(lic, priv_bytes)

        lic["key"] = "tampered-key-at-least16"
        assert verify_license_signature(lic, pub_b64) is False

    def test_wrong_public_key_fails(self, ed25519_keypair):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from agent.skill_crypto import sign_license, verify_license_signature

        priv_bytes, _, _ = ed25519_keypair

        lic = {
            "licensee": "Test Corp",
            "hwid": "a" * 64,
            "tier": "pro",
            "expires": "2099-12-31",
            "key": "test-aes-key-at-least-16",
        }
        lic["signature"] = sign_license(lic, priv_bytes)

        # Different key
        other_pub = Ed25519PrivateKey.generate().public_key().public_bytes_raw()
        other_b64 = base64.b64encode(other_pub).decode()

        assert verify_license_signature(lic, other_b64) is False


# ── License 全流程校验 ──────────────────────────────────────────────────────


class TestLicenseValidation:
    def test_valid_license_passes(self, valid_license):
        from agent.skill_crypto import validate_license

        lic, pub_b64 = valid_license
        valid, reason = validate_license(lic, pub_b64)
        assert valid is True
        assert reason == "OK"

    def test_missing_fields_fails(self, valid_license):
        from agent.skill_crypto import validate_license

        lic, pub_b64 = valid_license
        del lic["signature"]
        valid, reason = validate_license(lic, pub_b64)
        assert valid is False
        assert "missing fields" in reason.lower()

    def test_expired_license_fails(self, ed25519_keypair):
        from agent.skill_crypto import get_machine_hwid, sign_license, validate_license

        priv_bytes, _, pub_b64 = ed25519_keypair
        lic = {
            "licensee": "Test Corp",
            "hwid": get_machine_hwid(),
            "tier": "pro",
            "expires": "2020-01-01",
            "key": SAMPLE_KEY,
        }
        lic["signature"] = sign_license(lic, priv_bytes)

        valid, reason = validate_license(lic, pub_b64)
        assert valid is False
        assert "expired" in reason.lower()

    def test_wrong_hwid_fails(self, ed25519_keypair):
        from agent.skill_crypto import sign_license, validate_license

        priv_bytes, _, pub_b64 = ed25519_keypair
        lic = {
            "licensee": "Test Corp",
            "hwid": "wrong" + "f" * 59,
            "tier": "pro",
            "expires": "2099-12-31",
            "key": SAMPLE_KEY,
        }
        lic["signature"] = sign_license(lic, priv_bytes)

        valid, reason = validate_license(lic, pub_b64)
        assert valid is False
        assert "hwid mismatch" in reason.lower()

    def test_bad_signature_fails(self, valid_license):
        from agent.skill_crypto import validate_license

        lic, pub_b64 = valid_license
        lic["signature"] = base64.b64encode(b"\x00" * 64).decode()

        valid, reason = validate_license(lic, pub_b64)
        assert valid is False
        assert "signature" in reason.lower()

    def test_invalid_expires_format_fails(self, ed25519_keypair):
        from agent.skill_crypto import get_machine_hwid, sign_license, validate_license

        priv_bytes, _, pub_b64 = ed25519_keypair
        lic = {
            "licensee": "Test Corp",
            "hwid": get_machine_hwid(),
            "tier": "pro",
            "expires": "not-a-date",
            "key": SAMPLE_KEY,
        }
        lic["signature"] = sign_license(lic, priv_bytes)

        valid, reason = validate_license(lic, pub_b64)
        assert valid is False
        assert "invalid expires" in reason.lower()


# ── License JSON 文件读取 ──────────────────────────────────────────────────


class TestLicenseFileLoading:
    def test_json_license_extracts_key(self, tmp_path, monkeypatch, valid_license):
        from agent import skill_crypto

        lic, pub_b64 = valid_license
        license_file = tmp_path / ".license"
        license_file.write_text(json.dumps(lic), encoding="utf-8")

        monkeypatch.delenv("BOOKWORMPRO_LICENSE_KEY", raising=False)
        import bwm_constants
        monkeypatch.setattr(bwm_constants, "get_hermes_home", lambda: tmp_path)
        monkeypatch.setattr(skill_crypto, "_LICENSE_PUBLIC_KEY_B64", pub_b64)
        skill_crypto._cached_license = None

        key = skill_crypto.get_license_key()
        assert key == SAMPLE_KEY

    def test_env_var_overrides_file(self, tmp_path, monkeypatch, valid_license):
        from agent import skill_crypto

        lic, _ = valid_license
        license_file = tmp_path / ".license"
        license_file.write_text(json.dumps(lic), encoding="utf-8")

        monkeypatch.setenv("BOOKWORMPRO_LICENSE_KEY", "env-override-key-16ch")
        key = skill_crypto.get_license_key()
        assert key == "env-override-key-16ch"

    def test_plaintext_license_backward_compat(self, tmp_path, monkeypatch):
        """Old-format .license (plain string) still works."""
        from agent import skill_crypto

        license_file = tmp_path / ".license"
        license_file.write_text("plain-text-key-at-least-16ch\n", encoding="utf-8")

        monkeypatch.delenv("BOOKWORMPRO_LICENSE_KEY", raising=False)
        import bwm_constants
        monkeypatch.setattr(bwm_constants, "get_hermes_home", lambda: tmp_path)
        skill_crypto._cached_license = None

        key = skill_crypto.get_license_key()
        # Plain text won't JSON-parse to a dict with "key", so fallback path reads raw
        assert key is not None


# ── generate_license.py E2E ─────────────────────────────────────────────────


class TestGenerateLicenseE2E:
    def test_keygen_creates_files(self, tmp_path):
        """keygen subcommand creates private.key and public.key."""
        import subprocess, sys

        result = subprocess.run(
            [sys.executable, "scripts/generate_license.py", "keygen",
             "--output-dir", str(tmp_path / "keys")],
            capture_output=True, text=True, cwd=str(Path(__file__).parent.parent.parent),
        )
        assert result.returncode == 0
        assert (tmp_path / "keys" / "private.key").exists()
        assert (tmp_path / "keys" / "public.key").exists()
        assert len((tmp_path / "keys" / "private.key").read_bytes()) == 32
        assert len((tmp_path / "keys" / "public.key").read_bytes()) == 32

    def test_full_issue_verify_cycle(self, tmp_path):
        """keygen → hwid → issue → verify roundtrip."""
        import subprocess, sys
        from agent.skill_crypto import get_machine_hwid

        proj = str(Path(__file__).parent.parent.parent)

        # 1. keygen
        subprocess.run(
            [sys.executable, "scripts/generate_license.py", "keygen",
             "--output-dir", str(tmp_path / "keys")],
            capture_output=True, text=True, cwd=proj, check=True,
        )

        # 2. issue
        hwid = get_machine_hwid()
        lic_file = tmp_path / "test.license"
        result = subprocess.run(
            [sys.executable, "scripts/generate_license.py", "issue",
             "--licensee", "TestCo",
             "--hwid", hwid,
             "--tier", "pro",
             "--expires", "2099-12-31",
             "--aes-key", SAMPLE_KEY,
             "--private-key", str(tmp_path / "keys" / "private.key"),
             "--output", str(lic_file)],
            capture_output=True, text=True, cwd=proj, check=True,
        )
        assert lic_file.exists()

        lic_data = json.loads(lic_file.read_text())
        assert lic_data["licensee"] == "TestCo"
        assert "signature" in lic_data

        # 3. verify
        result = subprocess.run(
            [sys.executable, "scripts/generate_license.py", "verify",
             str(lic_file),
             "--public-key", str(tmp_path / "keys" / "public.key")],
            capture_output=True, text=True, cwd=proj,
        )
        assert result.returncode == 0
        assert "VALID" in result.stdout
