"""bookworm canary — post-deploy smoke test.

Runs a small set of fast, deterministic checks after every install/upgrade
to catch regressions before the user hits them mid-conversation.  Designed
to complement ``bookworm doctor`` (which is exhaustive but slow) by
focusing on the *deployment-fragile* surface: credential pool resolution,
prompt-cache snapshot freshness, model resolution, and (optionally) a
single live API ping.

Exit codes:
    0  all canaries green
    1  at least one canary failed (deploy is suspect — investigate)
    2  partial — non-fatal warnings only

Refs progress note 2026-04-26 (P1 user-experience batch).
"""

from __future__ import annotations

import importlib
import os
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional



@dataclass
class CanaryResult:
    name: str
    status: str  # "PASS" | "FAIL" | "WARN" | "SKIP"
    detail: str = ""
    elapsed_ms: int = 0


@dataclass
class CanaryReport:
    results: List[CanaryResult] = field(default_factory=list)

    def add(self, result: CanaryResult) -> None:
        self.results.append(result)

    @property
    def failed(self) -> List[CanaryResult]:
        return [r for r in self.results if r.status == "FAIL"]

    @property
    def warned(self) -> List[CanaryResult]:
        return [r for r in self.results if r.status == "WARN"]

    @property
    def passed(self) -> List[CanaryResult]:
        return [r for r in self.results if r.status == "PASS"]

    @property
    def exit_code(self) -> int:
        if self.failed:
            return 1
        if self.warned:
            return 2
        return 0


def _timed(func: Callable[[], CanaryResult]) -> CanaryResult:
    start = time.perf_counter()
    try:
        result = func()
    except Exception as exc:  # canary itself blew up — record as FAIL
        elapsed = int((time.perf_counter() - start) * 1000)
        return CanaryResult(
            name=getattr(func, "__name__", "<canary>"),
            status="FAIL",
            detail=f"canary crashed: {exc.__class__.__name__}: {exc}",
            elapsed_ms=elapsed,
        )
    if result.elapsed_ms == 0:
        result.elapsed_ms = int((time.perf_counter() - start) * 1000)
    return result


# ── Individual canary checks ──────────────────────────────────────────────

def check_config_loadable() -> CanaryResult:
    """Config must parse without error."""
    from bwm_cli.config import load_config

    try:
        cfg = load_config()
    except Exception as exc:
        return CanaryResult(
            "config-loadable", "FAIL",
            f"load_config() raised {exc.__class__.__name__}: {exc}",
        )
    if not isinstance(cfg, dict):
        return CanaryResult(
            "config-loadable", "FAIL",
            f"load_config() returned {type(cfg).__name__}, expected dict",
        )
    return CanaryResult("config-loadable", "PASS", f"keys={len(cfg)}")


def check_credential_pool_resolves() -> CanaryResult:
    """Active provider's credential pool must yield at least one entry."""
    from bwm_cli.config import load_config

    cfg = load_config()
    model_cfg = cfg.get("model", {}) if isinstance(cfg.get("model"), dict) else {}
    provider = (model_cfg.get("provider") or "").strip()
    if not provider:
        return CanaryResult(
            "credential-pool", "WARN",
            "no provider configured — run `bookworm setup` first",
        )
    try:
        from agent.credential_pool import load_pool
    except ImportError as exc:
        return CanaryResult(
            "credential-pool", "FAIL",
            f"agent.credential_pool import failed: {exc}",
        )
    try:
        pool = load_pool(provider)
    except Exception as exc:
        return CanaryResult(
            "credential-pool", "FAIL",
            f"load_pool({provider!r}) raised {exc.__class__.__name__}: {exc}",
        )
    entries = getattr(pool, "_entries", []) or []
    if not entries:
        return CanaryResult(
            "credential-pool", "FAIL",
            f"provider {provider!r} has no credentials — set the API key env var",
        )

    # Detect base_url conflict (e.g. relay + official OpenRouter both seeded).
    base_urls = {(e.base_url or "").rstrip("/") for e in entries if e.base_url}
    base_urls.discard("")
    if len(base_urls) > 1:
        return CanaryResult(
            "credential-pool", "WARN",
            f"provider {provider!r} has {len(entries)} entries spanning "
            f"{len(base_urls)} distinct base_urls — rotation may produce 401s",
        )
    return CanaryResult(
        "credential-pool", "PASS",
        f"{provider}: {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}",
    )


def check_prompt_cache_snapshot() -> CanaryResult:
    """Skills prompt snapshot file must be present and self-consistent."""
    from bwm_constants import get_hermes_home

    home = get_hermes_home()
    snapshot = home / ".skills_prompt_snapshot.json"
    if not snapshot.exists():
        return CanaryResult(
            "prompt-cache", "WARN",
            "snapshot not present (will be regenerated on first chat)",
        )
    try:
        size = snapshot.stat().st_size
    except OSError as exc:
        return CanaryResult(
            "prompt-cache", "FAIL",
            f"snapshot stat failed: {exc}",
        )
    if size < 16:
        return CanaryResult(
            "prompt-cache", "WARN",
            f"snapshot suspiciously small ({size} bytes) — delete it to regenerate",
        )
    return CanaryResult("prompt-cache", "PASS", f"{size:,} bytes")


def check_runtime_imports() -> CanaryResult:
    """Critical runtime modules must import without error."""
    failures: list[str] = []
    for mod in (
        "agent.prompt_builder",
        "agent.refusal_interceptor",
        "agent.credential_pool",
        "tools.memory_tool",
        "run_agent",
    ):
        try:
            importlib.import_module(mod)
        except Exception as exc:
            failures.append(f"{mod}: {exc.__class__.__name__}: {exc}")
    if failures:
        return CanaryResult(
            "runtime-imports", "FAIL",
            "; ".join(failures),
        )
    return CanaryResult("runtime-imports", "PASS", "5 modules")


def check_memory_writable() -> CanaryResult:
    """Memory directory must exist and be writable."""
    from bwm_constants import get_hermes_home

    home = get_hermes_home()
    mem = home / "memories"
    try:
        mem.mkdir(parents=True, exist_ok=True)
        probe = mem / ".canary-write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return CanaryResult(
            "memory-writable", "FAIL",
            f"{mem} not writable: {exc}",
        )
    return CanaryResult("memory-writable", "PASS", str(mem))


# ── Optional live API ping ────────────────────────────────────────────────

def check_live_api_ping(timeout: float = 5.0) -> CanaryResult:
    """Send a single 1-token completion to the configured provider.

    Off by default — opt in via ``--live`` so the canary stays
    network-free for offline upgrade flows.
    """
    from bwm_cli.config import load_config

    cfg = load_config()
    model_cfg = cfg.get("model", {}) if isinstance(cfg.get("model"), dict) else {}
    provider = (model_cfg.get("provider") or "").strip()
    model = (model_cfg.get("default") or model_cfg.get("model") or "").strip()
    if not provider or not model:
        return CanaryResult(
            "live-api-ping", "SKIP",
            "no provider/model configured",
        )

    try:
        from agent.credential_pool import load_pool
    except ImportError as exc:
        return CanaryResult(
            "live-api-ping", "FAIL",
            f"credential_pool import failed: {exc}",
        )

    try:
        pool = load_pool(provider)
    except Exception as exc:
        return CanaryResult(
            "live-api-ping", "FAIL",
            f"load_pool failed: {exc.__class__.__name__}: {exc}",
        )
    entry = pool.peek() if hasattr(pool, "peek") else None
    if entry is None:
        return CanaryResult(
            "live-api-ping", "SKIP",
            "no usable credential — fix credential-pool first",
        )

    base_url = entry.base_url or ""
    token = entry.access_token or ""
    if not base_url or not token:
        return CanaryResult(
            "live-api-ping", "SKIP",
            "credential missing base_url or token",
        )

    try:
        from openai import OpenAI
    except ImportError:
        return CanaryResult(
            "live-api-ping", "SKIP",
            "openai SDK not installed",
        )

    try:
        client = OpenAI(base_url=base_url, api_key=token, timeout=timeout)
        client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
        )
    except Exception as exc:
        # Truncate noisy traces — surface the class + first 200 chars
        msg = f"{exc.__class__.__name__}: {exc}"
        if len(msg) > 200:
            msg = msg[:197] + "..."
        return CanaryResult("live-api-ping", "FAIL", msg)
    return CanaryResult("live-api-ping", "PASS", f"{provider}/{model}")


# ── Top-level runner + CLI entry ──────────────────────────────────────────

_DEFAULT_CANARIES: tuple[Callable[[], CanaryResult], ...] = (
    check_config_loadable,
    check_runtime_imports,
    check_credential_pool_resolves,
    check_prompt_cache_snapshot,
    check_memory_writable,
)


def run_canaries(*, live: bool = False) -> CanaryReport:
    """Execute all canaries and return a populated report."""
    report = CanaryReport()
    for fn in _DEFAULT_CANARIES:
        report.add(_timed(fn))
    if live:
        report.add(_timed(check_live_api_ping))
    return report


_STATUS_MARK = {
    "PASS": "[成功]",
    "FAIL": "[失败]",
    "WARN": "[警告]",
    "SKIP": "[跳过]",
}


def _format_report(report: CanaryReport) -> str:
    lines: list[str] = ["", "BookwormPRO post-deploy canary", "─" * 40]
    for r in report.results:
        mark = _STATUS_MARK.get(r.status, r.status)
        lines.append(f"  {mark} {r.name:<22} {r.elapsed_ms:>5} ms  {r.detail}")
    lines.append("─" * 40)
    if report.failed:
        lines.append(
            f"  Result: {len(report.failed)} FAIL · "
            f"{len(report.warned)} WARN · {len(report.passed)} PASS"
        )
        lines.append("  Deploy is suspect — investigate failures above.")
    elif report.warned:
        lines.append(
            f"  Result: 0 FAIL · {len(report.warned)} WARN · "
            f"{len(report.passed)} PASS"
        )
        lines.append("  Non-fatal warnings — deploy is usable but worth fixing.")
    else:
        lines.append(f"  Result: all {len(report.passed)} canaries green")
    lines.append("")
    return "\n".join(lines)


def cmd_canary(args: Any) -> int:
    """CLI entry — runs canaries and prints the report."""
    live = bool(getattr(args, "live", False))
    report = run_canaries(live=live)
    print(_format_report(report))
    return report.exit_code
