"""Provider circuit breaker — prevents cascading failure.



Implements the standard CLOSED → OPEN → HALF_OPEN state machine,

with file-based state sharing across all sessions (CLI, gateway, cron).



States:

    CLOSED     — normal operation, failures increment counter

    OPEN       — all requests rejected immediately

    HALF_OPEN  — one probe request allowed; success → CLOSED, failure → OPEN



Integration:

    Before API call:  circuit_breaker.allow(provider)  → bool

    After success:    circuit_breaker.report_success(provider)

    After failure:    circuit_breaker.report_failure(provider, error)



Follows the same file-based atomic-write pattern as nous_rate_guard.py

so circuit state is visible across concurrent processes.

"""



from __future__ import annotations



import json

import logging

import os

import tempfile

import time

from dataclasses import dataclass, field

from enum import Enum

from typing import Any, Dict, Optional



logger = logging.getLogger(__name__)



_STATE_SUBDIR = "circuits"

_DEFAULT_THRESHOLD = 5          # consecutive failures to trip

_DEFAULT_RECOVERY = 60.0        # seconds before HALF_OPEN probe

_DEFAULT_MAX_DELAY = 300.0      # cap for exponential recovery extension





class CircuitState(Enum):

    CLOSED = "closed"

    OPEN = "open"

    HALF_OPEN = "half_open"





@dataclass

class CircuitRecord:

    provider: str

    state: CircuitState = CircuitState.CLOSED

    failure_count: int = 0

    consecutive_failures: int = 0

    total_failures: int = 0

    total_successes: int = 0

    trip_count: int = 0

    last_failure_time: float = 0.0

    last_success_time: float = 0.0

    opened_at: float = 0.0

    recovery_until: float = 0.0

    threshold: int = _DEFAULT_THRESHOLD

    recovery_seconds: float = _DEFAULT_RECOVERY

    last_error_code: Optional[int] = None

    last_error_reason: str = ""

    extra: Dict[str, Any] = field(default_factory=dict)





# ── Error patterns that should NOT trip the breaker ─────────────────────

# These indicate client-side or request-specific issues, not provider health.

_BREAKER_SKIP_PATTERNS = frozenset({

    "context_overflow",        # request too large — not provider's fault

    "payload_too_large",       # 413 — request too large

    "format_error",            # 400 bad request — client error

    "thinking_signature",      # Anthropic internal quirk

    "long_context_tier",       # Anthropic tier gate

    "model_not_found",         # wrong model name — client error

    "auth",                     # 401/403 — credential issue, not provider

    "auth_permanent",
    "empty_response",          # model returned empty — not provider fault

})





def _state_path(provider: str) -> str:

    """Return the path to the circuit state file for a provider."""

    try:

        from bwm_constants import get_hermes_home

        base = get_hermes_home()

    except ImportError:

        base = os.path.join(os.path.expanduser("~"), ".bookwormpro")

    safe_name = provider.replace("/", "_").replace("\\", "_").replace(":", "_")

    return os.path.join(base, _STATE_SUBDIR, f"{safe_name}.json")





def _load_record(provider: str) -> CircuitRecord:

    """Load circuit state from file, returning a fresh record if missing."""

    path = _state_path(provider)

    try:

        with open(path) as f:

            data = json.load(f)

        return CircuitRecord(

            provider=provider,

            state=CircuitState(data.get("state", "closed")),

            failure_count=data.get("failure_count", 0),

            consecutive_failures=data.get("consecutive_failures", 0),

            total_failures=data.get("total_failures", 0),

            total_successes=data.get("total_successes", 0),

            trip_count=data.get("trip_count", 0),

            last_failure_time=data.get("last_failure_time", 0.0),

            last_success_time=data.get("last_success_time", 0.0),

            opened_at=data.get("opened_at", 0.0),

            recovery_until=data.get("recovery_until", 0.0),

            threshold=data.get("threshold", _DEFAULT_THRESHOLD),

            recovery_seconds=data.get("recovery_seconds", _DEFAULT_RECOVERY),

            last_error_code=data.get("last_error_code"),

            last_error_reason=data.get("last_error_reason", ""),

            extra=data.get("extra", {}),

        )

    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError, ValueError):

        return CircuitRecord(provider=provider)





def _save_record(record: CircuitRecord) -> None:

    """Atomically write circuit state to file."""

    path = _state_path(record.provider)

    try:

        state_dir = os.path.dirname(path)

        os.makedirs(state_dir, exist_ok=True)



        state = {

            "state": record.state.value,

            "failure_count": record.failure_count,

            "consecutive_failures": record.consecutive_failures,

            "total_failures": record.total_failures,

            "total_successes": record.total_successes,

            "trip_count": record.trip_count,

            "last_failure_time": record.last_failure_time,

            "last_success_time": record.last_success_time,

            "opened_at": record.opened_at,

            "recovery_until": record.recovery_until,

            "threshold": record.threshold,

            "recovery_seconds": record.recovery_seconds,

            "last_error_code": record.last_error_code,

            "last_error_reason": record.last_error_reason,

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

        logger.debug("Failed to save circuit state for %s: %s", record.provider, exc)





def allow(provider: str) -> bool:

    """Check if a request to this provider should be allowed.



    Returns True if the circuit is CLOSED or HALF_OPEN (probe allowed).

    Returns False if the circuit is OPEN and hasn't recovered yet.



    Call this BEFORE every API request to the provider.

    """

    record = _load_record(provider)



    if record.state == CircuitState.CLOSED:

        return True



    if record.state == CircuitState.OPEN:

        now = time.time()

        if now >= record.recovery_until:

            # Transition to HALF_OPEN for probing

            record.state = CircuitState.HALF_OPEN

            _save_record(record)

            logger.info(

                "Circuit HALF_OPEN for %s — allowing probe request "

                "(trip #%d, was OPEN for %.0fs)",

                provider, record.trip_count, now - record.opened_at,

            )

            return True

        # Still in cooldown

        remaining = record.recovery_until - now

        logger.debug(

            "Circuit OPEN for %s — rejecting request "

            "(%.0fs remaining, trip #%d, last error: %s %s)",

            provider, remaining, record.trip_count,

            record.last_error_code, record.last_error_reason,

        )

        return False



    # HALF_OPEN — allow the probe

    return True





def report_success(provider: str) -> None:

    """Report a successful API call, resetting the circuit to CLOSED.



    Call this AFTER every successful API response.

    """

    record = _load_record(provider)

    now = time.time()



    previous_state = record.state



    record.state = CircuitState.CLOSED

    record.failure_count = 0

    record.consecutive_failures = 0

    record.total_successes += 1

    record.last_success_time = now



    _save_record(record)



    if previous_state != CircuitState.CLOSED:

        logger.info(

            "Circuit CLOSED for %s after successful request "

            "(was %s, %d total successes, %d total failures)",

            provider, previous_state.value,

            record.total_successes, record.total_failures,

        )





def report_failure(

    provider: str,

    error: Optional[Exception] = None,

    *,

    reason: str = "",

    status_code: Optional[int] = None,

) -> None:

    """Report a failed API call, possibly tripping the circuit.



    Call this AFTER every failed API response.



    Args:

        provider: Provider name (e.g. 'openrouter', 'anthropic').

        error: The exception from the API call (optional).

        reason: Classified failover reason from error_classifier.py.

        status_code: HTTP status code if available.

    """

    record = _load_record(provider)

    now = time.time()



    # Do NOT trip on client-side or request-specific errors

    if reason in _BREAKER_SKIP_PATTERNS:

        logger.debug(

            "Circuit breaker skipping %s failure (reason=%s, not provider fault)",

            provider, reason,

        )

        return



    record.failure_count += 1

    record.consecutive_failures += 1

    record.total_failures += 1

    record.last_failure_time = now

    record.last_error_code = status_code

    record.last_error_reason = reason or ""



    if record.state == CircuitState.HALF_OPEN:

        # Probe failed — back to OPEN with extended recovery

        record.trip_count += 1

        record.state = CircuitState.OPEN

        # Exponential backoff for recovery: 60s → 120s → 240s → cap at 300s

        record.recovery_seconds = min(

            record.recovery_seconds * 2.0,

            _DEFAULT_MAX_DELAY,

        )

        record.opened_at = now

        record.recovery_until = now + record.recovery_seconds

        _save_record(record)

        logger.warning(

            "Circuit RE-OPENED for %s — probe failed "

            "(trip #%d, recovery=%.0fs, error=%s %s)",

            provider, record.trip_count,

            record.recovery_seconds, status_code, reason,

        )

        return



    if record.state == CircuitState.CLOSED:

        if record.consecutive_failures >= record.threshold:

            # Trip the circuit

            record.trip_count += 1

            record.state = CircuitState.OPEN

            record.opened_at = now

            # First trip: standard recovery. Subsequent: exponential.

            if record.trip_count == 1:

                record.recovery_seconds = _DEFAULT_RECOVERY

            record.recovery_until = now + record.recovery_seconds

            _save_record(record)

            logger.warning(

                "Circuit OPENED for %s — %d consecutive failures "

                "(trip #%d, recovery=%.0fs, threshold=%d, last error=%s %s)",

                provider, record.consecutive_failures,

                record.trip_count, record.recovery_seconds,

                record.threshold, status_code, reason,

            )

        else:

            _save_record(record)

            logger.debug(

                "Circuit %s failures=%d/%d for %s (error=%s %s)",

                record.state.value, record.consecutive_failures,

                record.threshold, provider, status_code, reason,

            )

        return



    # OPEN state — just record the failure

    _save_record(record)





def reset(provider: str) -> None:

    """Manually reset the circuit breaker to CLOSED state."""

    record = _load_record(provider)

    record.state = CircuitState.CLOSED

    record.failure_count = 0

    record.consecutive_failures = 0

    record.last_error_code = None

    record.last_error_reason = ""

    record.recovery_until = 0.0

    _save_record(record)

    logger.info("Circuit manually RESET for %s", provider)





def status(provider: str) -> CircuitRecord:

    """Return the current circuit state for a provider (read-only)."""

    return _load_record(provider)





def is_open(provider: str) -> bool:

    """Check if circuit is currently OPEN (blocking all requests)."""

    return not allow(provider)

