"""
fake_credential_store.py — In-memory CredentialStore for unit tests.

Part of P2-2 layer violation fix (2026-05-06).

Usage:
    from tests.agent.fake_credential_store import FakeCredentialStore

    store = FakeCredentialStore({
        "version": 1,
        "providers": {"anthropic": {"tokens": {"access_token": "test"}}},
        "credential_pool": {"deepseek": [{"id": "x", "access_token": "sk-test"}]},
    })

    with store.auth_store_lock():
        pool = store.read_credential_pool("deepseek")
        assert pool["deepseek"][0]["access_token"] == "sk-test"

Features:
    - In-memory dict storage (no filesystem)
    - Thread-safe via threading.Lock
    - Source suppression tracking
    - Configurable provider configuration state
"""

from __future__ import annotations

import copy
import threading
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Set

from bwm_cli.credential_store import (
    AuthStore,
    CredentialStore,
    PoolEntry,
    ProviderState,
)

# Sentinel for "not found" vs "found but None"
_NOT_FOUND = object()


class FakeCredentialStore(CredentialStore):
    """In-memory CredentialStore for unit tests.

    All data lives in :attr:`_store` (a dict mirroring auth.json structure).
    Thread-safe via :attr:`_lock`.

    Parameters:
        initial_data: Optional seed data (dict matching auth.json schema).
        configured_providers: Set of provider IDs considered "explicitly configured".
        suppressed_sources: Dict mapping provider_id → set of suppressed source names.
    """

    def __init__(
        self,
        initial_data: Optional[Dict[str, Any]] = None,
        configured_providers: Optional[Set[str]] = None,
        suppressed_sources: Optional[Dict[str, Set[str]]] = None,
    ):
        self._lock = threading.Lock()
        self._store = copy.deepcopy(initial_data) if initial_data else {
            "version": 1,
            "providers": {},
        }
        self._configured_providers = configured_providers or set()
        self._suppressed = suppressed_sources or {}

    # ── Lock ────────────────────────────────────────────────────────

    @contextmanager
    def auth_store_lock(self, timeout_seconds: float = 15.0):
        """Acquire the in-memory lock (no cross-process, threads only)."""
        acquired = self._lock.acquire(timeout=timeout_seconds)
        if not acquired:
            raise TimeoutError("FakeCredentialStore lock timeout")
        try:
            yield
        finally:
            self._lock.release()

    # ── Auth store read / write ─────────────────────────────────────

    def load_auth_store(self) -> AuthStore:
        return copy.deepcopy(self._store)

    def save_auth_store(self, store: AuthStore) -> None:
        self._store = copy.deepcopy(store)

    # ── Provider state ──────────────────────────────────────────────

    def load_provider_state(self, provider_id: str) -> Optional[ProviderState]:
        providers = self._store.get("providers", {})
        state = providers.get(provider_id, _NOT_FOUND)
        if state is _NOT_FOUND:
            return None
        return copy.deepcopy(state)

    def save_provider_state(
        self, provider_id: str, state: ProviderState
    ) -> None:
        if "providers" not in self._store:
            self._store["providers"] = {}
        self._store["providers"][provider_id] = copy.deepcopy(state)

    # ── Credential pool ─────────────────────────────────────────────

    def read_credential_pool(
        self, provider_id: Optional[str] = None
    ) -> Dict[str, List[PoolEntry]]:
        pool = self._store.get("credential_pool", {})
        pool = copy.deepcopy(pool)
        if provider_id is not None:
            entries = pool.get(provider_id, [])
            return {provider_id: entries}
        return pool

    def write_credential_pool(
        self, provider_id: str, entries: List[PoolEntry]
    ) -> None:
        if "credential_pool" not in self._store:
            self._store["credential_pool"] = {}
        self._store["credential_pool"][provider_id] = copy.deepcopy(entries)

    # ── Source management ───────────────────────────────────────────

    def is_source_suppressed(self, provider_id: str, source: str) -> bool:
        suppressed = self._suppressed.get(provider_id, set())
        return source in suppressed

    def suppress_source(self, provider_id: str, source: str) -> None:
        """Mark *source* as suppressed for *provider_id*."""
        if provider_id not in self._suppressed:
            self._suppressed[provider_id] = set()
        self._suppressed[provider_id].add(source)

    # ── Provider configuration ──────────────────────────────────────

    def is_provider_explicitly_configured(self, provider_id: str) -> bool:
        return provider_id in self._configured_providers

    def mark_provider_configured(self, provider_id: str) -> None:
        """Mark *provider_id* as explicitly configured."""
        self._configured_providers.add(provider_id)
