"""
auth_encryption.py — AES-256-GCM encryption for ~/.bookwormpro/auth.json

Usage (in bwm_cli/auth.py):
    from bwm_cli.auth_encryption import encrypt_auth, decrypt_auth, get_encryption_key

Design:
- Master key from BOOKWORMPRO_MASTER_KEY env var (32+ chars recommended)
- If no master key, plaintext mode (backward compatible)
- AES-256-GCM: 32-byte key derived via PBKDF2-SHA256, 12-byte random nonce
- On-disk format: base64(nonce||ciphertext||tag) prefixed with ENC_AES256:
- Atomic write with tmp file + os.replace (inherits existing pattern)
- Graceful fallback: if decryption fails, try plaintext JSON

P2-3 Security Harden: 2026-05-06
"""

import os
import json
import base64
import secrets
import hashlib
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# ── Magic prefix to detect encrypted files ──────────────────────────
MAGIC_PREFIX = b"ENC_AES256:"
MAGIC_PREFIX_LEN = len(MAGIC_PREFIX)

# ── Crypto constants ────────────────────────────────────────────────
PBKDF2_ITERATIONS = 600_000  # OWASP 2025 recommendation
PBKDF2_HASH = "sha256"
KEY_LENGTH = 32  # AES-256
NONCE_LENGTH = 12  # GCM standard
SALT_LENGTH = 16


def _derive_key(master_key: str, salt: bytes) -> bytes:
    """Derive AES-256 key from master key using PBKDF2-SHA256."""
    return hashlib.pbkdf2_hmac(
        PBKDF2_HASH,
        master_key.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
        dklen=KEY_LENGTH,
    )


def get_encryption_key() -> Optional[str]:
    """Get master key from environment. Returns None if not configured."""
    master_key = os.getenv("BOOKWORMPRO_MASTER_KEY", "").strip()
    if not master_key:
        # Also check legacy env var name
        master_key = os.getenv("MASTER_KEY", "").strip()
    if len(master_key) < 16:
        if master_key:
            logger.warning(
                "BOOKWORMPRO_MASTER_KEY is too short (%d chars, need >=16). "
                "Auth file will be stored unencrypted.",
                len(master_key),
            )
        return None
    return master_key


def _try_decrypt(raw_bytes: bytes, master_key: str) -> Optional[bytes]:
    """Attempt AES-256-GCM decryption. Returns plaintext or None on failure."""
    try:
        # Strip magic prefix
        if not raw_bytes.startswith(MAGIC_PREFIX):
            return None
        payload_b64 = raw_bytes[MAGIC_PREFIX_LEN:]

        # Decode base64
        ciphertext = base64.b64decode(payload_b64)

        # Extract components: salt(16) + nonce(12) + ciphertext + tag(16)
        if len(ciphertext) < SALT_LENGTH + NONCE_LENGTH + 16:
            logger.warning("Encrypted auth file too short, may be corrupted")
            return None

        salt = ciphertext[:SALT_LENGTH]
        nonce = ciphertext[SALT_LENGTH:SALT_LENGTH + NONCE_LENGTH]
        encrypted = ciphertext[SALT_LENGTH + NONCE_LENGTH:]

        # Derive key
        key = _derive_key(master_key, salt)

        # AES-256-GCM decrypt
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, encrypted, None)
        return plaintext

    except ImportError:
        logger.error("cryptography library not installed — cannot decrypt auth file")
        return None
    except Exception as e:
        logger.warning("Auth file decryption failed: %s", e)
        return None


def encrypt_auth(data: Dict[str, Any], master_key: str) -> bytes:
    """Encrypt auth store dict to bytes (with magic prefix).

    Returns bytes ready to write to disk.
    """
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError:
        logger.error("cryptography library not installed — storing auth in plaintext")
        return json.dumps(data, indent=2).encode("utf-8") + b"\n"

    # Generate random salt and nonce
    salt = secrets.token_bytes(SALT_LENGTH)
    nonce = secrets.token_bytes(NONCE_LENGTH)

    # Derive key
    key = _derive_key(master_key, salt)

    # Serialize to JSON
    plaintext = json.dumps(data, indent=2).encode("utf-8")

    # Encrypt
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    # Pack: salt + nonce + ciphertext
    payload = salt + nonce + ciphertext

    # Encode and prefix
    result = MAGIC_PREFIX + base64.b64encode(payload) + b"\n"
    return result


def decrypt_auth(raw_bytes: bytes) -> Optional[Dict[str, Any]]:
    """Decrypt auth store bytes to dict.

    Returns None if encrypted but can't decrypt (caller should try plaintext).
    Returns dict if successfully decrypted.
    """
    if not raw_bytes.startswith(MAGIC_PREFIX):
        return None  # Not encrypted

    master_key = get_encryption_key()
    if not master_key:
        logger.warning(
            "Auth file is encrypted but BOOKWORMPRO_MASTER_KEY is not set. "
            "Cannot decrypt — falling back to empty store."
        )
        return None

    plaintext = _try_decrypt(raw_bytes, master_key)
    if plaintext is None:
        return None

    try:
        return json.loads(plaintext.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.warning("Decrypted auth file is not valid JSON: %s", e)
        return None


def load_auth_store(auth_file: Path) -> Dict[str, Any]:
    """Load auth store with automatic encryption detection.

    Tries:
    1. Encrypted format (if magic prefix detected and key available)
    2. Plaintext JSON (backward compatible)
    3. Empty store (on failure)
    """
    if not auth_file.exists():
        return {"version": 1, "providers": {}}

    try:
        raw_bytes = auth_file.read_bytes()
    except Exception as exc:
        logger.warning("auth: cannot read %s (%s)", auth_file, exc)
        return {"version": 1, "providers": {}}

    # Try encrypted first
    if raw_bytes.startswith(MAGIC_PREFIX):
        result = decrypt_auth(raw_bytes)
        if result is not None:
            logger.debug("auth: decrypted %s successfully", auth_file)
            return result
        # Decryption failed — fall through to plaintext attempt
        logger.warning(
            "auth: encrypted file %s could not be decrypted. "
            "Attempting plaintext fallback.", auth_file
        )

    # Plaintext JSON (backward compatible)
    try:
        return json.loads(raw_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        corrupt_path = auth_file.with_suffix(".json.corrupt")
        try:
            import shutil
            shutil.copy2(auth_file, corrupt_path)
        except Exception:
            pass
        logger.warning(
            "auth: failed to parse %s (%s) — starting with empty store. "
            "Corrupt file preserved at %s",
            auth_file, exc, corrupt_path,
        )
        return {"version": 1, "providers": {}}


def save_auth_store(auth_file: Path, data: Dict[str, Any]) -> None:
    """Save auth store with automatic encryption if master key is available.

    Uses atomic write: tmp file → flush+fsync → os.replace.
    """
    from datetime import datetime, timezone
    import uuid

    data["version"] = data.get("version", 1)
    data["updated_at"] = datetime.now(timezone.utc).isoformat()

    master_key = get_encryption_key()
    if master_key:
        payload = encrypt_auth(data, master_key)
        logger.debug("auth: saving encrypted to %s", auth_file)
    else:
        payload = json.dumps(data, indent=2).encode("utf-8") + b"\n"
        logger.debug("auth: saving plaintext to %s (no master key)", auth_file)

    auth_file.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = auth_file.with_name(
        f"{auth_file.name}.tmp.{os.getpid()}.{uuid.uuid4().hex}"
    )
    try:
        with tmp_path.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, auth_file)

        # Fsync directory to ensure rename is durable
        try:
            dir_fd = os.open(str(auth_file.parent), os.O_RDONLY)
        except OSError:
            dir_fd = None
        if dir_fd is not None:
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass

    # Restrict permissions to owner only
    try:
        auth_file.chmod(0o600)
    except OSError:
        pass


def migrate_to_encrypted(auth_file: Path) -> bool:
    """One-shot: encrypt an existing plaintext auth.json.

    Returns True on success, False if already encrypted or no key.
    """
    if not auth_file.exists():
        logger.info("migrate: %s does not exist, nothing to do", auth_file)
        return False

    master_key = get_encryption_key()
    if not master_key:
        logger.warning("migrate: no master key set, cannot encrypt")
        return False

    raw_bytes = auth_file.read_bytes()
    if raw_bytes.startswith(MAGIC_PREFIX):
        logger.info("migrate: %s is already encrypted", auth_file)
        return False

    # Load plaintext
    try:
        data = json.loads(raw_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.error("migrate: cannot parse %s as JSON: %s", auth_file, e)
        return False

    # Backup plaintext
    backup_path = auth_file.with_suffix(".json.plaintext-backup")
    try:
        import shutil
        shutil.copy2(auth_file, backup_path)
        logger.info("migrate: plaintext backup saved to %s", backup_path)
    except Exception as e:
        logger.warning("migrate: cannot create backup: %s", e)

    # Save encrypted
    save_auth_store(auth_file, data)
    logger.info("migrate: %s encrypted successfully", auth_file)
    return True
