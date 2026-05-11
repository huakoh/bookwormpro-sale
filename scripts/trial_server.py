"""
BookwormPRO Trial License 签发服务.

部署在服务器上，接受 HWID 请求，签发 7 天试用 license。
每个 HWID 仅可试用一次。

用法:
    python trial_server.py --private-key /path/to/private.key --aes-key <key> --port 8699

部署:
    scp scripts/trial_server.py root@server:/opt/bookworm-web/
    scp keys/private.key root@server:/opt/bookworm-web/private/signing.key

    # systemd service
    [Unit]
    Description=BookwormPRO Trial License Server
    [Service]
    ExecStart=/usr/bin/python3 /opt/bookworm-web/trial_server.py \
        --private-key /opt/bookworm-web/private/signing.key \
        --aes-key <production-aes-key>
    Restart=always
    [Install]
    WantedBy=multi-user.target
"""

import argparse
import base64
import hashlib
import json
import os
import sys
from datetime import date, timedelta, datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

TRIAL_DAYS = 7
TRIAL_TIER = "trial"
TRIAL_DB_PATH = Path("/opt/bookworm-web/private/trial_hwids.json")

_private_key_bytes: bytes = b""
_aes_key: str = ""


def _load_trial_db() -> dict:
    if TRIAL_DB_PATH.exists():
        try:
            return json.loads(TRIAL_DB_PATH.read_text())
        except Exception:
            pass
    return {}


def _save_trial_db(db: dict):
    TRIAL_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRIAL_DB_PATH.write_text(json.dumps(db, indent=2, ensure_ascii=False))


def _sign_trial(hwid: str) -> dict:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    expires = (date.today() + timedelta(days=TRIAL_DAYS)).isoformat()
    lic = {
        "licensee": "Trial User",
        "hwid": hwid,
        "tier": TRIAL_TIER,
        "expires": expires,
        "key": _aes_key,
    }

    payload = json.dumps(
        {k: lic[k] for k in sorted(lic)},
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")

    private_key = Ed25519PrivateKey.from_private_bytes(_private_key_bytes)
    signature = private_key.sign(payload)
    lic["signature"] = base64.b64encode(signature).decode("ascii")

    return lic


class TrialHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/api/trial":
            self._json_response(404, {"error": "Not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
        except Exception:
            self._json_response(400, {"error": "Invalid JSON body"})
            return

        hwid = body.get("hwid", "").strip()
        if not hwid or len(hwid) != 64:
            self._json_response(400, {"error": "Invalid HWID (must be 64-char hex)"})
            return

        db = _load_trial_db()
        if hwid in db:
            issued = db[hwid].get("issued", "unknown")
            self._json_response(409, {
                "error": "Trial already used",
                "message": f"This machine already used a trial on {issued}. Contact sales for a full license.",
            })
            return

        try:
            lic = _sign_trial(hwid)
        except Exception as e:
            self._json_response(500, {"error": f"Signing failed: {e}"})
            return

        db[hwid] = {"issued": datetime.now().isoformat(), "expires": lic["expires"]}
        _save_trial_db(db)

        self._json_response(200, {"license": lic, "expires": lic["expires"], "days": TRIAL_DAYS})

    def do_GET(self):
        if self.path == "/api/trial/health":
            self._json_response(200, {"status": "ok", "trial_days": TRIAL_DAYS})
            return
        self._json_response(404, {"error": "Not found"})

    def _json_response(self, code: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {fmt % args}")


def main():
    parser = argparse.ArgumentParser(description="BookwormPRO Trial Server")
    parser.add_argument("--private-key", required=True, help="Ed25519 private key file")
    parser.add_argument("--aes-key", required=True, help="AES key for skill decryption")
    parser.add_argument("--port", type=int, default=8699, help="Listen port (default 8699)")
    args = parser.parse_args()

    global _private_key_bytes, _aes_key

    priv_file = Path(args.private_key)
    if not priv_file.exists():
        print(f"[ERROR] Private key not found: {priv_file}")
        sys.exit(1)
    _private_key_bytes = priv_file.read_bytes()
    _aes_key = args.aes_key

    print(f"BookwormPRO Trial Server starting on :{args.port}")
    print(f"  Trial duration: {TRIAL_DAYS} days")
    print(f"  HWID database: {TRIAL_DB_PATH}")

    server = HTTPServer(("127.0.0.1", args.port), TrialHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")


if __name__ == "__main__":
    main()
