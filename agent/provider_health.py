"""Provider health probing — proactive liveness detection.

Probes each provider with a lightweight HTTP request (GET /models or
HEAD to base URL) to detect dead providers BEFORE API calls fail.
Results are stored in shared files so all sessions see the same state.

Health states:
    healthy   — probe succeeded within cooldown window
    degraded  — one probe failed, retrying
    dead      — 3+ consecutive probe failures, circuit auto-tripped

Integration with circuit_breaker:
    When health probe detects 'dead', it trips the circuit breaker
    to prevent retry amplification.  When a probe succeeds, it resets
    the circuit to CLOSED.

Probe cooldown: 30s between probes per provider (avoids adding latency
to every API call).

Probe endpoints by provider:
    OpenAI-compatible: GET {base_url}/models  (returns 200 or 401)
    Anthropic:         GET {base_url}/v1/messages/models (or HEAD)
    All:               HEAD {base_url}  (fastest fallback)
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

_STATE_SUBDIR = "health"
_PROBE_COOLDOWN = 30.0        # seconds between probes per provider
_PROBE_TIMEOUT = 5.0           # HTTP request timeout
_DEAD_THRESHOLD = 3            # consecutive failures to mark dead


class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DEAD = "dead"
    UNKNOWN = "unknown"


@dataclass
class HealthRecord:
    provider: str
    status: HealthStatus = HealthStatus.UNKNOWN
    last_check: float = 0.0
    last_success: float = 0.0
    last_latency_ms: float = 0.0
    consecutive_failures: int = 0
    total_probes: int = 0
    total_failures: int = 0
    last_error: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


def _state_path(provider: str) -> str:
    """Return the path to the health state file for a provider."""
    try:
        from bwm_constants import get_hermes_home
        base = get_hermes_home()
    except ImportError:
        base = os.path.join(os.path.expanduser("~"), ".bookwormpro")
    safe_name = provider.replace("/", "_").replace("\\", "_").replace(":", "_")
    return os.path.join(base, _STATE_SUBDIR, f"{safe_name}.json")


def _load_record(provider: str) -> HealthRecord:
    """Load health state from file."""
    path = _state_path(provider)
    try:
        with open(path) as f:
            data = json.load(f)
        return HealthRecord(
            provider=provider,
            status=HealthStatus(data.get("status", "unknown")),
            last_check=data.get("last_check", 0.0),
            last_success=data.get("last_success", 0.0),
            last_latency_ms=data.get("last_latency_ms", 0.0),
            consecutive_failures=data.get("consecutive_failures", 0),
            total_probes=data.get("total_probes", 0),
            total_failures=data.get("total_failures", 0),
            last_error=data.get("last_error", ""),
            extra=data.get("extra", {}),
        )
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return HealthRecord(provider=provider)


def _save_record(record: HealthRecord) -> None:
    """Atomically write health state to file."""
    path = _state_path(record.provider)
    try:
        state_dir = os.path.dirname(path)
        os.makedirs(state_dir, exist_ok=True)

        state = {
            "status": record.status.value,
            "last_check": record.last_check,
            "last_success": record.last_success,
            "last_latency_ms": record.last_latency_ms,
            "consecutive_failures": record.consecutive_failures,
            "total_probes": record.total_probes,
            "total_failures": record.total_failures,
            "last_error": record.last_error,
            "written_at": time.time(),
        }

        fd, tmp_path = tempfile.mkstemp(dir=state_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(state, f)
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except Exception as exc:
        logger.debug("Failed to save health state for %s: %s", record.provider, exc)


def _needs_probe(provider: str) -> bool:
    """Check if enough time has passed since the last probe."""
    record = _load_record(provider)
    return (time.time() - record.last_check) >= _PROBE_COOLDOWN


def _build_probe_url(provider: str, base_url: str) -> Optional[str]:
    """Build the best probe URL for a provider."""
    if not base_url:
        return None

    base = base_url.rstrip("/")

    # Provider-specific probe paths
    _paths = {
        "anthropic": "/v1/messages/models",  # may not exist on all deployments
    }

    path = _paths.get(provider.lower(), "/models")
    return f"{base}{path}"


def _do_http_probe(url: str, timeout: float = _PROBE_TIMEOUT) -> Tuple[bool, float, str]:
    """Perform an HTTP probe and return (success, latency_ms, error).

    Uses httpx (proxy-aware via trust_env) instead of urllib to respect
    HTTPS_PROXY/HTTP_PROXY/ALL_PROXY env vars — critical for users behind
    proxies (e.g. Chinese users accessing blocked API endpoints).
    """
    try:
        import httpx
    except ImportError:
        # Fallback to urllib if httpx unavailable
        return _do_http_probe_urllib(url, timeout)

    start = time.time()
    try:
        # trust_env=True (default) reads HTTPS_PROXY/HTTP_PROXY/ALL_PROXY
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": "BookwormPRO-HealthProbe/1.0"})
            latency_ms = (time.time() - start) * 1000
            _capture_rate_limit_headers(dict(resp.headers))
            return True, latency_ms, ""
    except httpx.HTTPStatusError as e:
        latency_ms = (time.time() - start) * 1000
        if e.response.status_code in (401, 403, 404, 405):
            _capture_rate_limit_headers(dict(e.response.headers))
            return True, latency_ms, ""
        return False, latency_ms, f"HTTP {e.response.status_code}"
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as e:
        latency_ms = (time.time() - start) * 1000
        return False, latency_ms, str(e)
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        return False, latency_ms, str(e)


def _do_http_probe_urllib(url: str, timeout: float = _PROBE_TIMEOUT) -> Tuple[bool, float, str]:
    """Fallback HTTP probe using urllib (not proxy-aware)."""
    import urllib.request, urllib.error
    start = time.time()
    try:
        req = urllib.request.Request(url, method="GET")
        req.add_header("User-Agent", "BookwormPRO-HealthProbe/1.0")
        resp = urllib.request.urlopen(req, timeout=timeout)
        latency_ms = (time.time() - start) * 1000
        _capture_rate_limit_headers(dict(resp.headers))
        return True, latency_ms, ""
    except urllib.error.HTTPError as e:
        latency_ms = (time.time() - start) * 1000
        if e.code in (401, 403, 404, 405):
            return True, latency_ms, ""
        return False, latency_ms, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        latency_ms = (time.time() - start) * 1000
        return False, latency_ms, str(e.reason)
    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        return False, latency_ms, str(e)


# ── Rate limit capacity scoring ─────────────────────────────────────────

# Module-level store for rate limit info from probes
_rate_limit_store: dict = {}
_rate_limit_lock = __import__('threading').Lock()


def _capture_rate_limit_headers(headers: dict) -> None:
    """Parse x-ratelimit-* headers from probe response."""
    try:
        lowered = {k.lower(): v for k, v in headers.items()}
        remaining_rph = None
        remaining_rpm = None

        for k, v in lowered.items():
            if k == "x-ratelimit-remaining-requests-1h":
                remaining_rph = int(float(v))
            elif k == "x-ratelimit-remaining-requests":
                remaining_rpm = int(float(v))

        if remaining_rph is not None or remaining_rpm is not None:
            with _rate_limit_lock:
                _rate_limit_store["last_probe"] = {
                    "rph_remaining": remaining_rph,
                    "rpm_remaining": remaining_rpm,
                    "timestamp": __import__('time').time(),
                }
    except (ValueError, TypeError):
        pass


def get_provider_capacity_score() -> dict:
    """Return capacity score from last health probe.

    Returns dict with:
        rph_remaining: requests remaining in hour window (None if unknown)
        rpm_remaining: requests remaining in minute window
        score: 0-100 capacity score (higher = more available)
    """
    with _rate_limit_lock:
        if not _rate_limit_store:
            return {"rph_remaining": None, "rpm_remaining": None, "score": 50}
        last = _rate_limit_store.get("last_probe", {})
        rph = last.get("rph_remaining")
        rpm = last.get("rpm_remaining")

        # Score: weighted combo of RPH (weight 0.7) and RPM (weight 0.3)
        score = 50  # default: unknown
        if rph is not None and rpm is not None:
            # Normalize to 0-100 based on typical quota ranges
            rph_score = min(rph / 500.0 * 100, 100) if rph > 0 else 0
            rpm_score = min(rpm / 50.0 * 100, 100) if rpm > 0 else 0
            score = int(rph_score * 0.7 + rpm_score * 0.3)
        elif rph is not None:
            score = min(int(rph / 500.0 * 100), 100)
        elif rpm is not None:
            score = min(int(rpm / 50.0 * 100), 100)

        return {
            "rph_remaining": rph,
            "rpm_remaining": rpm,
            "score": score,
        }


def probe(provider: str, base_url: str = "", *, force: bool = False) -> HealthRecord:
    """Probe a provider's health.

    Args:
        provider: Provider name (e.g. 'openrouter').
        base_url: Provider's API base URL.
        force: If True, probe even if within cooldown window.

    Returns:
        Updated HealthRecord with probe results.
    """
    record = _load_record(provider)
    now = time.time()

    # Cooldown check (skip if recently probed)
    if not force and (now - record.last_check) < _PROBE_COOLDOWN:
        return record

    url = _build_probe_url(provider, base_url)
    if url is None:
        logger.debug("No probe URL for provider %s (no base_url)", provider)
        return record

    record.last_check = now
    record.total_probes += 1

    success, latency_ms, error = _do_http_probe(url)

    if success:
        previous_status = record.status
        record.status = HealthStatus.HEALTHY
        record.last_success = now
        record.last_latency_ms = latency_ms
        record.consecutive_failures = 0
        record.last_error = ""

        _save_record(record)

        # Auto-reset circuit breaker on successful probe
        if previous_status != HealthStatus.HEALTHY:
            try:
                from agent.circuit_breaker import reset as _cb_reset
                _cb_reset(provider)
                logger.info(
                    "Provider %s health RESTORED (%.0fms) — circuit reset",
                    provider, latency_ms,
                )
            except ImportError:
                pass
        else:
            logger.debug(
                "Provider %s health OK (%.0fms)", provider, latency_ms,
            )
    else:
        record.consecutive_failures += 1
        record.total_failures += 1
        record.last_error = error

        if record.consecutive_failures >= _DEAD_THRESHOLD:
            record.status = HealthStatus.DEAD
            _save_record(record)

            # Trip circuit breaker for dead provider
            try:
                from agent.circuit_breaker import report_failure as _cb_fail
                for _ in range(_DEAD_THRESHOLD):
                    _cb_fail(provider, reason="overloaded", error=None)
                logger.warning(
                    "Provider %s health DEAD after %d failures — circuit tripped (last: %s)",
                    provider, record.consecutive_failures, error,
                )
            except ImportError:
                pass
        elif record.consecutive_failures == 1:
            record.status = HealthStatus.DEGRADED
            _save_record(record)
            logger.info(
                "Provider %s health DEGRADED (1 failure: %s)",
                provider, error,
            )
        else:
            record.status = HealthStatus.DEGRADED
            _save_record(record)
            logger.debug(
                "Provider %s probe failed (%d/%d: %s, %.0fms)",
                provider, record.consecutive_failures,
                _DEAD_THRESHOLD, error, latency_ms,
            )

    return record


def check_before_call(provider: str, base_url: str = "") -> Optional[HealthRecord]:
    """Check provider health before an API call.

    Probes if cooldown has expired.  If provider is DEAD, returns
    the record so the caller can immediately fall back.

    Returns None if provider is healthy/unknown (call can proceed).
    Returns HealthRecord if provider is dead (call should be skipped).
    """
    record = probe(provider, base_url)

    if record.status == HealthStatus.DEAD:
        logger.debug(
            "Provider %s is DEAD — skipping API call (%d failures, last: %s)",
            provider, record.consecutive_failures, record.last_error,
        )
        return record

    return None


def status(provider: str) -> HealthRecord:
    """Return current health status (may trigger a probe if cooldown expired)."""
    return _load_record(provider)


def reset(provider: str) -> None:
    """Manually reset health state to UNKNOWN."""
    record = _load_record(provider)
    record.status = HealthStatus.UNKNOWN
    record.consecutive_failures = 0
    record.last_error = ""
    _save_record(record)
    logger.info("Health state RESET for %s", provider)
