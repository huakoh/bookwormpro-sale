"""
BookwormPRO License 生成工具 (发行侧).

用法:
    # 首次: 生成 Ed25519 密钥对
    python scripts/generate_license.py keygen

    # 为客户生成 license (需要客户提供 HWID)
    python scripts/generate_license.py issue \
        --licensee "Company Name" \
        --hwid <客户机器 sha256 hex> \
        --tier pro \
        --expires 2027-01-01 \
        --aes-key <用于加密 skills 的 key> \
        --private-key keys/private.key

    # 客户采集自己的 HWID
    python scripts/generate_license.py hwid
"""

import argparse
import base64
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def cmd_keygen(args):
    """生成 Ed25519 密钥对."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    priv_bytes = private_key.private_bytes_raw()
    pub_bytes = public_key.public_bytes_raw()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    priv_file = out_dir / "private.key"
    pub_file = out_dir / "public.key"

    priv_file.write_bytes(priv_bytes)
    pub_file.write_bytes(pub_bytes)

    pub_b64 = base64.b64encode(pub_bytes).decode()

    print(f"\n  密钥对已生成:")
    print(f"  私钥: {priv_file}  (32 bytes, 绝不可泄露)")
    print(f"  公钥: {pub_file}  (32 bytes)")
    print(f"\n  公钥 Base64 (嵌入 skill_crypto.py _LICENSE_PUBLIC_KEY_B64):")
    print(f"  {pub_b64}")
    print(f"\n  [重要] 私钥务必离线保管, 不可提交到 git 仓库\n")


def cmd_hwid(_args):
    """采集当前机器 HWID."""
    from agent.skill_crypto import get_machine_hwid
    hwid = get_machine_hwid()
    print(f"\n  Machine HWID: {hwid}")
    print(f"  (将此值发送给发行方以绑定 license)\n")


def cmd_issue(args):
    """签发 license."""
    from agent.skill_crypto import sign_license

    priv_file = Path(args.private_key)
    if not priv_file.exists():
        print(f"[ERROR] 私钥文件不存在: {priv_file}")
        sys.exit(1)

    priv_bytes = priv_file.read_bytes()
    if len(priv_bytes) != 32:
        print(f"[ERROR] 私钥长度不正确: {len(priv_bytes)} bytes (应为 32)")
        sys.exit(1)

    lic = {
        "licensee": args.licensee,
        "hwid": args.hwid,
        "tier": args.tier,
        "expires": args.expires,
        "key": args.aes_key,
    }

    signature = sign_license(lic, priv_bytes)
    lic["signature"] = signature

    output = json.dumps(lic, indent=2, ensure_ascii=False)

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(output + "\n", encoding="utf-8")
        print(f"\n  License 已写入: {out_path}")
    else:
        print(f"\n  License JSON (写入 ~/.bookwormpro/.license):")
        print(output)

    print(f"\n  Licensee: {lic['licensee']}")
    print(f"  HWID:     {lic['hwid'][:24]}...")
    print(f"  Tier:     {lic['tier']}")
    print(f"  Expires:  {lic['expires']}")
    print(f"  Signed:   ✓\n")


def cmd_verify(args):
    """验证 license 文件."""
    from agent.skill_crypto import validate_license

    lic_path = Path(args.license_file)
    if not lic_path.exists():
        print(f"[ERROR] License 文件不存在: {lic_path}")
        sys.exit(1)

    lic = json.loads(lic_path.read_text(encoding="utf-8"))

    pub_b64 = None
    if args.public_key:
        pub_bytes = Path(args.public_key).read_bytes()
        pub_b64 = base64.b64encode(pub_bytes).decode()

    valid, reason = validate_license(lic, pub_b64)

    if valid:
        print(f"\n  ✓ License VALID")
        print(f"    Licensee: {lic['licensee']}")
        print(f"    Tier:     {lic['tier']}")
        print(f"    Expires:  {lic['expires']}\n")
    else:
        print(f"\n  ✗ License INVALID: {reason}\n")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="BookwormPRO License Tool")
    sub = parser.add_subparsers(dest="command")

    kg = sub.add_parser("keygen", help="生成 Ed25519 密钥对")
    kg.add_argument("--output-dir", default="keys", help="密钥输出目录")

    sub.add_parser("hwid", help="显示当前机器 HWID")

    iss = sub.add_parser("issue", help="签发 license")
    iss.add_argument("--licensee", required=True, help="被授权方名称")
    iss.add_argument("--hwid", required=True, help="目标机器 HWID (sha256 hex)")
    iss.add_argument("--tier", default="pro", choices=["starter", "pro", "enterprise"])
    iss.add_argument("--expires", required=True, help="过期日期 YYYY-MM-DD")
    iss.add_argument("--aes-key", required=True, help="AES 加密 key (与 build_sale.py --license-key 一致)")
    iss.add_argument("--private-key", required=True, help="Ed25519 私钥文件路径")
    iss.add_argument("--output", help="输出文件路径 (默认 stdout)")

    vfy = sub.add_parser("verify", help="验证 license 文件")
    vfy.add_argument("license_file", help=".license 文件路径")
    vfy.add_argument("--public-key", help="公钥文件路径 (默认用内嵌公钥)")

    args = parser.parse_args()

    if args.command == "keygen":
        cmd_keygen(args)
    elif args.command == "hwid":
        cmd_hwid(args)
    elif args.command == "issue":
        cmd_issue(args)
    elif args.command == "verify":
        cmd_verify(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
