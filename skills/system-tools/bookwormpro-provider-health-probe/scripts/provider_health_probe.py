#!/usr/bin/env python
"""Provider health probe — run for all configured providers.

Probes each provider's base URL, logs results, and trips circuit breakers
for dead providers. Designed to run as a cron job or manual diagnostic.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Ensure BookwormPRO root is on sys.path
_ROOT = Path(r"C:\Users\BOOKWORMPRO_USER\BookwormPRO")
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from agent.provider_health import probe, HealthStatus
from agent.circuit_breaker import report_failure as cb_fail, status as cb_status, CircuitState


def load_providers() -> list[tuple[str, str]]:
    """Return list of (provider_name, base_url) for all configured providers."""
    providers: dict[str, str] = {}

    # 1. From auth.json credential_pool
    auth_path = Path.home() / ".bookwormpro" / "auth.json"
    if auth_path.exists():
        try:
            auth = json.loads(auth_path.read_text())
            pool = auth.get("credential_pool", {})
            for name, entries in pool.items():
                for entry in entries:
                    if entry.get("auth_type") == "api_key" and entry.get("base_url"):
                        providers[name] = entry["base_url"]
                        break  # first valid entry wins
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"[WARN] Failed to parse auth.json: {e}")

    # 2. From .env — pattern: <PROVIDER>_BASE_URL and <PROVIDER>_API_KEY
    env_path = Path.home() / ".bookwormpro" / ".env"
    if env_path.exists():
        base_urls: dict[str, str] = {}
        has_keys: set[str] = set()
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip().upper()
            v = v.strip()
            if k.endswith("_BASE_URL") and v:
                provider = k[:-len("_BASE_URL")].lower()
                base_urls[provider] = v
            elif k.endswith("_API_KEY") and v and v != "***":
                provider = k[:-len("_API_KEY")].lower()
                has_keys.add(provider)

        for provider, base_url in base_urls.items():
            if provider not in providers:
                providers[provider] = base_url

    return [(name, url) for name, url in sorted(providers.items())]


def main():
    print("=" * 72)
    print("BookwormPRO Provider Health Probe")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 72)

    providers = load_providers()
    if not providers:
        print("[INFO] No providers configured in auth.json or .env")
        return

    print(f"\n[INFO] Found {len(providers)} configured provider(s):")
    for name, url in providers:
        cb = cb_status(name)
        cb_state = cb.state.value if cb else "unknown"
        print(f"  - {name:20s} | {url:45s} | circuit: {cb_state}")

    results: list[dict] = []
    healthy = degraded = dead = unknown_count = 0

    print(f"\n{'─' * 72}")
    print(f"{'Provider':<20s} {'Status':<12s} {'Latency':<10s} {'Fails':<8s} {'Error'}")
    print(f"{'─' * 72}")

    for provider_name, base_url in providers:
        print(f"  Probing {provider_name}...", end=" ", flush=True)

        try:
            record = probe(provider_name, base_url, force=True)
        except Exception as exc:
            print(f"EXCEPTION: {exc}")
            unknown_count += 1
            results.append({
                "provider": provider_name,
                "base_url": base_url,
                "status": "unknown",
                "error": str(exc),
            })
            continue

        status_str = record.status.value
        latency = f"{record.last_latency_ms:.0f}ms" if record.last_latency_ms else "N/A"
        fails = f"{record.consecutive_failures}/{record.total_failures}"
        error = record.last_error[:80] if record.last_error else "—"

        print(f"\r  {provider_name:<18s} | {status_str:<12s} | {latency:<10s} | {fails:<8s} | {error}")

        if record.status == HealthStatus.DEAD:
            dead += 1
            try:
                cb_fail(provider_name, reason="overloaded", error=None)
            except Exception as exc:
                print(f"    [WARN] Circuit breaker trip failed: {exc}")
        elif record.status == HealthStatus.DEGRADED:
            degraded += 1
        elif record.status == HealthStatus.HEALTHY:
            healthy += 1
        else:
            unknown_count += 1

        results.append({
            "provider": provider_name,
            "base_url": base_url,
            "status": record.status.value,
            "latency_ms": record.last_latency_ms,
            "consecutive_failures": record.consecutive_failures,
            "error": record.last_error,
        })

    print(f"{'─' * 72}")

    # Summary
    print(f"\n{'=' * 72}")
    print(f"SUMMARY")
    print(f"{'=' * 72}")
    print(f"  HEALTHY:   {healthy}")
    print(f"  DEGRADED:  {degraded}")
    print(f"  DEAD:      {dead}")
    print(f"  UNKNOWN:   {unknown_count}")
    print(f"  Total:     {len(results)}")

    if dead:
        print(f"\n  DEAD providers require attention:")
        for r in results:
            if r["status"] == "dead":
                print(f"    - {r['provider']} ({r['base_url']}): {r['error']}")

    if degraded:
        print(f"\n  DEGRADED providers (watch list):")
        for r in results:
            if r["status"] == "degraded":
                print(f"    - {r['provider']} ({r['base_url']}): {r['error']}")

    # Write results to debug file
    debug_dir = Path.home() / ".bookwormpro" / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    report_path = debug_dir / "provider_health_report.json"
    report = {
        "timestamp": time.time(),
        "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "summary": {
            "healthy": healthy,
            "degraded": degraded,
            "dead": dead,
            "unknown": unknown_count,
            "total": len(results),
        },
        "providers": results,
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\n[INFO] Report written to: {report_path}")

    # Also append to health log
    log_path = debug_dir / "provider_health.log"
    with open(log_path, "a") as f:
        for r in results:
            f.write(
                f"{report['timestamp_iso']} | {r['provider']:20s} | {r['status']:10s} | "
                f"{r.get('latency_ms', 0):.0f}ms | fails={r.get('consecutive_failures', 0)} | "
                f"{r.get('error', '')}\n"
            )

    return 0 if dead == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
