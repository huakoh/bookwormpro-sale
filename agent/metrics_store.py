"""Lightweight observability metrics for Gateway operations.

Tracks key operational metrics without external dependencies:
    - Provider availability (healthy/degraded/dead ratio)
    - Circuit breaker trip count
    - API call latency (P50/P99 via streaming histogram)
    - SSE connection leak count
    - DNS refresh count

Metrics are stored in-memory with optional periodic flush to file.
Designed for zero-overhead in the hot path — all operations are O(1).
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_STATE_SUBDIR = "metrics"


# ── Histogram (streaming approximation for P50/P95/P99) ─────────────────

@dataclass
class _Histogram:
    """Streaming histogram with fixed quantile buckets.

    Tracks counts in pre-defined latency buckets (50ms, 100ms, 250ms, 500ms,
    1s, 2s, 5s, 10s, 30s, 60s+).  Quantile queries return the lower bound
    of the bucket containing the target percentile.
    """
    buckets: List[int] = field(default_factory=lambda: [0] * 11)
    _bucket_edges: tuple = (0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, float("inf"))
    total: int = 0
    total_ms: float = 0.0

    def record(self, latency_seconds: float) -> None:
        for i, edge in enumerate(self._bucket_edges):
            if latency_seconds <= edge:
                self.buckets[i] += 1
                break
        self.total += 1
        self.total_ms += latency_seconds * 1000

    @property
    def avg_ms(self) -> float:
        return self.total_ms / self.total if self.total > 0 else 0.0

    def quantile(self, pct: float) -> float:
        """Return approximate latency at given percentile (0-100)."""
        if self.total == 0:
            return 0.0
        target = int(self.total * pct / 100.0)
        cumulative = 0
        for i, count in enumerate(self.buckets):
            cumulative += count
            if cumulative >= target:
                return self._bucket_edges[min(i, len(self._bucket_edges) - 1)]
        return self._bucket_edges[-1]

    def to_dict(self) -> dict:
        return {
            "buckets": self.buckets,
            "total": self.total,
            "avg_ms": round(self.avg_ms, 1),
            "p50_s": round(self.quantile(50), 2),
            "p95_s": round(self.quantile(95), 2),
            "p99_s": round(self.quantile(99), 2),
        }


# ── Provider metrics ────────────────────────────────────────────────────

@dataclass
class ProviderMetrics:
    api_calls: int = 0
    api_successes: int = 0
    api_failures: int = 0
    circuit_trips: int = 0
    health_probes: int = 0
    health_failures: int = 0
    dns_refreshes: int = 0
    latency: _Histogram = field(default_factory=_Histogram)
    last_call: float = 0.0
    last_error: str = ""

    def to_dict(self) -> dict:
        return {
            "api_calls": self.api_calls,
            "api_successes": self.api_successes,
            "api_failures": self.api_failures,
            "success_rate": round(
                self.api_successes / max(self.api_calls, 1) * 100, 1
            ),
            "circuit_trips": self.circuit_trips,
            "health_probes": self.health_probes,
            "health_failures": self.health_failures,
            "dns_refreshes": self.dns_refreshes,
            "latency": self.latency.to_dict(),
            "last_call": self.last_call,
            "last_error": self.last_error[-100:] if self.last_error else "",
        }


# ── Global metrics store ────────────────────────────────────────────────

class MetricsStore:
    """Thread-safe in-memory metrics store with optional file persistence."""

    def __init__(self):
        self._providers: Dict[str, ProviderMetrics] = defaultdict(ProviderMetrics)
        self._lock = threading.Lock()
        self._sse_leaks: int = 0
        self._created_at: float = time.time()

    def record_api_call(
        self,
        provider: str,
        *,
        success: bool,
        latency_s: float,
        error: str = "",
    ) -> None:
        with self._lock:
            m = self._providers[provider]
            m.api_calls += 1
            if success:
                m.api_successes += 1
            else:
                m.api_failures += 1
                m.last_error = error
            m.latency.record(latency_s)
            m.last_call = time.time()

    def record_circuit_trip(self, provider: str) -> None:
        with self._lock:
            self._providers[provider].circuit_trips += 1

    def record_health_probe(self, provider: str, success: bool) -> None:
        with self._lock:
            m = self._providers[provider]
            m.health_probes += 1
            if not success:
                m.health_failures += 1

    def record_dns_refresh(self, provider: str) -> None:
        with self._lock:
            self._providers[provider].dns_refreshes += 1

    def record_sse_leak(self) -> None:
        with self._lock:
            self._sse_leaks += 1

    def get_provider_metrics(self, provider: str) -> ProviderMetrics:
        with self._lock:
            return self._providers[provider]

    def get_all_metrics(self) -> dict:
        with self._lock:
            return {
                "uptime_s": time.time() - self._created_at,
                "sse_leaks_detected": self._sse_leaks,
                "providers": {
                    p: m.to_dict() for p, m in self._providers.items()
                },
            }

    def snapshot(self) -> str:
        """Return JSON snapshot of all metrics."""
        return json.dumps(self.get_all_metrics(), indent=2)

    def flush_to_file(self) -> Optional[str]:
        """Write metrics snapshot to file. Returns file path or None."""
        try:
            from bwm_constants import get_hermes_home
            base = get_hermes_home()
        except ImportError:
            base = os.path.join(os.path.expanduser("~"), ".bookwormpro")

        state_dir = os.path.join(base, _STATE_SUBDIR)
        os.makedirs(state_dir, exist_ok=True)

        path = os.path.join(state_dir, "gateway_metrics.json")
        snapshot_data = self.get_all_metrics()
        snapshot_data["written_at"] = time.time()

        fd, tmp_path = tempfile.mkstemp(dir=state_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(snapshot_data, f, indent=2)
            os.replace(tmp_path, path)
            return path
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            return None


# ── Module-level singleton ──────────────────────────────────────────────

_store: Optional[MetricsStore] = None
_store_lock = threading.Lock()


def get_store() -> MetricsStore:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = MetricsStore()
    return _store


# ── Convenience functions (for integration points) ──────────────────────

def record_api_success(provider: str, latency_s: float) -> None:
    get_store().record_api_call(provider, success=True, latency_s=latency_s)


def record_api_failure(provider: str, latency_s: float = 0, error: str = "") -> None:
    get_store().record_api_call(provider, success=False, latency_s=latency_s, error=error)


def record_circuit_trip(provider: str) -> None:
    get_store().record_circuit_trip(provider)


def snapshot_json() -> str:
    return get_store().snapshot()
