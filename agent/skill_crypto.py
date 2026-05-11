"""
Skill encryption/decryption for BookwormPRO Sale distribution.

AES-256-GCM with PBKDF2-derived keys. Encrypted skills (.skill.enc) are
decrypted in memory at runtime — plaintext never touches disk.

Wire format (binary):
    [1B version][16B salt][12B nonce][...ciphertext+tag...]

Version 1 uses PBKDF2-HMAC-SHA256, 600_000 iterations.

License file format (~/.bookwormpro/.license JSON):
    {
        "licensee": "Company Name",
        "hwid": "sha256-hex-of-machine-fingerprint",
        "tier": "pro",
        "expires": "2027-01-01",
        "key": "base64-aes-key-material",
        "signature": "base64-ed25519-signature-over-payload"
    }

Signature covers the canonical JSON of {licensee, hwid, tier, expires, key}
sorted keys, no whitespace. Public key is embedded for offline verification.
"""

import base64
import hashlib
import json
import logging
import os
import platform
import struct
import uuid
from datetime import date, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_VERSION = 1
_PBKDF2_ITERATIONS = 600_000
_SALT_LEN = 16
_NONCE_LEN = 12
_KEY_LEN = 32  # AES-256

# Cached derived key to avoid re-running PBKDF2 on every skill load
_cached_key: bytes | None = None
_cached_salt: bytes | None = None

# Cached validated license to avoid re-reading + re-verifying every call
_cached_license: dict | None = None

# Ed25519 公钥 (发行侧持有私钥, 此处仅用于验签)
# 生成方式: python -c "from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey; \
#   k=Ed25519PrivateKey.generate(); \
#   print(base64.b64encode(k.public_key().public_bytes_raw()).decode())"
# 替换为你的真实公钥
_LICENSE_PUBLIC_KEY_B64 = "YIvcfDYLsJVesjMEVWZGIV8EaSQGKo0yn5/Ni8L1l4w="


# ── HWID 指纹采集 ───────────────────────────────────────────────────────────


def get_machine_hwid() -> str:
    """采集机器硬件指纹, 返回 SHA-256 hex digest.

    Windows: CIM MachineGuid → wmic → uuid.getnode (三级 fallback)
    Linux/Mac: /etc/machine-id → DMI product_uuid → uuid.getnode
    """
    raw_parts: list[str] = []

    if platform.system() == "Windows":
        raw_parts.append(_win_machine_guid())
    else:
        raw_parts.append(_unix_machine_id())

    mac = _get_stable_mac()
    if mac:
        raw_parts.append(mac)

    fingerprint = "|".join(p for p in raw_parts if p)
    if not fingerprint:
        fingerprint = str(uuid.getnode())

    return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()


def _win_machine_guid() -> str:
    """读取 Windows MachineGuid (CIM → wmic → 注册表 fallback)."""
    # CIM (PowerShell 5.1+)
    try:
        import subprocess
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance -ClassName Win32_ComputerSystemProduct).UUID"],
            capture_output=True, text=True, timeout=5,
        )
        val = result.stdout.strip()
        if val and val != "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF":
            return f"csproduct:{val}"
    except Exception:
        pass

    # 注册表直读
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
        ) as key:
            val, _ = winreg.QueryValueEx(key, "MachineGuid")
            if val:
                return f"reg:{val}"
    except Exception:
        pass

    return ""


def _unix_machine_id() -> str:
    """读取 Linux/Mac machine-id."""
    for path in ["/etc/machine-id", "/var/lib/dbus/machine-id"]:
        try:
            val = Path(path).read_text().strip()
            if val:
                return f"mid:{val}"
        except Exception:
            pass

    # macOS hardware UUID
    try:
        import subprocess
        result = subprocess.run(
            ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            if "IOPlatformUUID" in line:
                val = line.split('"')[-2]
                if val:
                    return f"ioreg:{val}"
    except Exception:
        pass

    return ""


def _get_stable_mac() -> str:
    """取第一个非虚拟网卡 MAC 地址作为辅助指纹."""
    try:
        mac_int = uuid.getnode()
        # uuid.getnode 在无真实 MAC 时会设 bit 0 of byte 0
        if (mac_int >> 40) & 1:
            return ""
        mac_hex = f"{mac_int:012x}"
        return f"mac:{mac_hex}"
    except Exception:
        return ""


# ── License 签名与验证 ──────────────────────────────────────────────────────


def _license_payload_bytes(lic: dict) -> bytes:
    """从 license dict 提取待签名的 canonical JSON bytes."""
    payload = {
        "licensee": lic["licensee"],
        "hwid": lic["hwid"],
        "tier": lic["tier"],
        "expires": lic["expires"],
        "key": lic["key"],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_license(lic: dict, private_key_bytes: bytes) -> str:
    """用 Ed25519 私钥签名 license payload, 返回 base64 签名.

    供发行侧 (scripts/generate_license.py) 调用.
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private_key = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
    payload = _license_payload_bytes(lic)
    signature = private_key.sign(payload)
    return base64.b64encode(signature).decode("ascii")


def verify_license_signature(lic: dict, public_key_b64: str | None = None) -> bool:
    """验证 license 的 Ed25519 签名."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.exceptions import InvalidSignature

    pub_b64 = public_key_b64 or _LICENSE_PUBLIC_KEY_B64
    if pub_b64 == "REPLACE_WITH_YOUR_ED25519_PUBLIC_KEY_BASE64":
        logger.warning("License public key not configured — signature check skipped")
        return True

    try:
        pub_bytes = base64.b64decode(pub_b64)
        public_key = Ed25519PublicKey.from_public_bytes(pub_bytes)
        payload = _license_payload_bytes(lic)
        sig = base64.b64decode(lic["signature"])
        public_key.verify(sig, payload)
        return True
    except (InvalidSignature, Exception):
        return False


def validate_license(lic: dict, public_key_b64: str | None = None) -> tuple[bool, str]:
    """完整 license 校验: 签名 + HWID + 有效期.

    Returns (valid, reason).
    """
    required_fields = {"licensee", "hwid", "tier", "expires", "key", "signature"}
    missing = required_fields - set(lic.keys())
    if missing:
        return False, f"License missing fields: {', '.join(sorted(missing))}"

    if not verify_license_signature(lic, public_key_b64):
        return False, "Invalid license signature"

    current_hwid = get_machine_hwid()
    if lic["hwid"] != current_hwid:
        return False, f"HWID mismatch (license: {lic['hwid'][:16]}..., machine: {current_hwid[:16]}...)"

    try:
        expires = date.fromisoformat(lic["expires"])
    except (ValueError, TypeError):
        return False, f"Invalid expires date: {lic.get('expires')}"

    if date.today() > expires:
        return False, f"License expired on {lic['expires']}"

    return True, "OK"


# ── AES-256-GCM 加解密 (不变) ───────────────────────────────────────────────


def _derive_key(license_key: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256",
        license_key.encode("utf-8"),
        salt,
        _PBKDF2_ITERATIONS,
        dklen=_KEY_LEN,
    )


def encrypt_skill(plaintext: str, license_key: str) -> bytes:
    """Encrypt a SKILL.md content string. Returns binary .skill.enc payload."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    salt = os.urandom(_SALT_LEN)
    nonce = os.urandom(_NONCE_LEN)
    key = _derive_key(license_key, salt)

    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)

    return struct.pack("B", _VERSION) + salt + nonce + ciphertext


def decrypt_skill(data: bytes, license_key: str) -> str:
    """Decrypt a .skill.enc payload. Returns plaintext SKILL.md content.

    Raises ValueError on wrong key or corrupted data.
    """
    global _cached_key, _cached_salt

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.exceptions import InvalidTag

    if len(data) < 1 + _SALT_LEN + _NONCE_LEN + 16:
        raise ValueError("Encrypted skill data too short")

    version = data[0]
    if version != _VERSION:
        raise ValueError(f"Unsupported encryption version: {version}")

    salt = data[1 : 1 + _SALT_LEN]
    nonce = data[1 + _SALT_LEN : 1 + _SALT_LEN + _NONCE_LEN]
    ciphertext = data[1 + _SALT_LEN + _NONCE_LEN :]

    if _cached_key is not None and _cached_salt == salt:
        key = _cached_key
    else:
        key = _derive_key(license_key, salt)
        _cached_key = key
        _cached_salt = salt

    aesgcm = AESGCM(key)
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    except InvalidTag:
        raise ValueError("Decryption failed — invalid license key or corrupted data")

    return plaintext.decode("utf-8")


# ── License 读取与解密 key 提取 ─────────────────────────────────────────────


def _load_license_file() -> dict | None:
    """读取并解析 .license JSON 文件."""
    try:
        from bwm_constants import get_hermes_home
        license_file = get_hermes_home() / ".license"
    except Exception:
        license_file = Path.home() / ".bookwormpro" / ".license"

    if not license_file.exists():
        return None

    try:
        content = license_file.read_text(encoding="utf-8").strip()
        if not content:
            return None
        lic = json.loads(content)
        if isinstance(lic, dict):
            return lic
    except (json.JSONDecodeError, Exception):
        pass

    return None


def _load_and_validate_license() -> dict | None:
    """加载 license 并执行完整校验, 缓存结果."""
    global _cached_license

    if _cached_license is not None:
        return _cached_license

    lic = _load_license_file()
    if lic is None:
        return None

    # 兼容旧格式: 纯字符串 key → 无签名/HWID 校验
    if "signature" not in lic:
        _cached_license = lic
        return lic

    valid, reason = validate_license(lic)
    if not valid:
        logger.warning("License validation failed: %s", reason)
        return None

    _cached_license = lic
    return lic


def get_license_key() -> str | None:
    """提取用于 AES 解密的 key material.

    优先级: 环境变量 > .license JSON "key" 字段 > .license 纯文本 (旧兼容)
    """
    env_key = os.environ.get("BOOKWORMPRO_LICENSE_KEY")
    if env_key:
        return env_key.strip()

    lic = _load_and_validate_license()
    if lic is not None and "key" in lic:
        return lic["key"]

    # 旧兼容: 纯文本 .license (非 JSON)
    try:
        from bwm_constants import get_hermes_home
        license_file = get_hermes_home() / ".license"
    except Exception:
        license_file = Path.home() / ".bookwormpro" / ".license"

    if license_file.exists():
        content = license_file.read_text(encoding="utf-8").strip()
        if content and not content.startswith("{"):
            return content

    return None


def is_encrypted_skill(path: Path) -> bool:
    """Check if a path points to an encrypted skill file."""
    return path.suffix == ".enc" and path.stem.endswith(".skill")


def find_skill_file(skill_dir: Path) -> tuple[Path | None, bool]:
    """Find the skill content file in a directory.

    Returns (path, is_encrypted). Prefers SKILL.md if both exist.
    """
    plain = skill_dir / "SKILL.md"
    if plain.exists():
        return plain, False

    encrypted = skill_dir / "SKILL.skill.enc"
    if encrypted.exists():
        return encrypted, True

    return None, False


def read_skill_content(skill_dir: Path, license_key: str | None = None) -> str | None:
    """Read skill content, transparently decrypting if needed.

    Returns None if no skill file found or decryption fails.
    """
    path, is_encrypted = find_skill_file(skill_dir)
    if path is None:
        return None

    if not is_encrypted:
        return path.read_text(encoding="utf-8")

    if license_key is None:
        license_key = get_license_key()
    if not license_key:
        return None

    try:
        data = path.read_bytes()
        return decrypt_skill(data, license_key)
    except (ValueError, Exception):
        return None
