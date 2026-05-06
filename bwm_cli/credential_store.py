"""
credential_store.py — Abstract CredentialStore protocol for auth.json-backed persistence.

Part of P2-2 layer violation fix (2026-05-06).

Usage:
    from bwm_cli.credential_store import CredentialStore, AuthStore, PoolEntry, ProviderState

    def load_pool(provider: str, *, store: CredentialStore | None = None):
        store = store or _default_store()
        with store.auth_store_lock():
            return store.read_credential_pool(provider)

    # In tests:
    from tests.agent.fake_credential_store import FakeCredentialStore
    fake = FakeCredentialStore({"providers": {"test": {"api_key": "secret"}}})
    pool = load_pool("test", store=fake)

Design:
    - Storage-format agnostic (auth.json, encrypted auth.json, in-memory)
    - Thread-safe via auth_store_lock context manager
    - Agent layer imports ONLY this ABC, never bwm_cli.auth directly
    - Implementations in bwm_cli/ (AuthCredentialStore) and tests/ (FakeCredentialStore)
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

# ── Type aliases ────────────────────────────────────────────────────

AuthStore = Dict[str, Any]
"""Full contents of auth.json (version, providers, credential_pool, etc.)."""

ProviderState = Dict[str, Any]
"""Sub-dict under ``providers.<provider_id>`` (tokens, refresh state, etc.)."""

PoolEntry = Dict[str, Any]
"""Single credential entry in credential_pool.<provider_id>[]."""


class CredentialStore(ABC):
    """Abstract interface for auth.json-backed credential persistence.

    The agent layer consumes this interface via dependency injection, never
    importing ``bwm_cli.auth`` directly.  Real implementations live in
    ``bwm_cli/``; tests supply lightweight in-memory fakes.

    Every method that reads or writes the auth store MUST acquire the
    store-wide file lock before operating.  Callers receive the lock
    as a context manager.
    """

    # ── Lock ────────────────────────────────────────────────────────

    @abstractmethod
    @contextmanager
    def auth_store_lock(self, timeout_seconds: float = 15.0):
        """Acquire the cross-process advisory lock protecting auth.json.

        Yields nothing; the lock is held for the duration of the ``with``
        block.  Implementations may use ``fcntl`` (POSIX) or ``msvcrt``
        (Windows).
        """
        ...

    # ── Auth store read / write ─────────────────────────────────────

    @abstractmethod
    def load_auth_store(self) -> AuthStore:
        """Return the full contents of auth.json (or empty dict if missing)."""
        ...

    @abstractmethod
    def save_auth_store(self, store: AuthStore) -> None:
        """Atomically write *store* back to auth.json."""
        ...

    # ── Provider state ──────────────────────────────────────────────

    @abstractmethod
    def load_provider_state(self, provider_id: str) -> Optional[ProviderState]:
        """Extract the ``providers.<provider_id>`` sub-dict from the auth store.

        Returns ``None`` when the provider has no stored state.
        """
        ...

    @abstractmethod
    def save_provider_state(
        self, provider_id: str, state: ProviderState
    ) -> None:
        """Persist *state* under ``providers.<provider_id>``.

        Must be called while holding ``auth_store_lock``.
        """
        ...

    # ── Credential pool ─────────────────────────────────────────────

    @abstractmethod
    def read_credential_pool(
        self, provider_id: Optional[str] = None
    ) -> Dict[str, List[PoolEntry]]:
        """Read the ``credential_pool`` section of auth.json.

        When *provider_id* is ``None``, return the whole pool dict.
        Otherwise return ``{provider_id: [...]}`` (empty list if missing).
        """
        ...

    @abstractmethod
    def write_credential_pool(
        self, provider_id: str, entries: List[PoolEntry]
    ) -> None:
        """Write *entries* for *provider_id* into the credential pool.

        Must be called while holding ``auth_store_lock``.
        """
        ...

    # ── Source management ───────────────────────────────────────────

    @abstractmethod
    def is_source_suppressed(self, provider_id: str, source: str) -> bool:
        """Return ``True`` if *source* was removed by the user for *provider_id*.

        Suppressed sources are skipped during auto-seeding.
        """
        ...

    # ── Provider configuration ──────────────────────────────────────

    @abstractmethod
    def is_provider_explicitly_configured(self, provider_id: str) -> bool:
        """Return ``True`` if *provider_id* appears in config.yaml or .env.

        Used as a consent gate before auto-discovering external credentials
        (e.g. ``~/.claude/.credentials.json``).
        """
        ...


# ── Default store singleton (lazy, can be overridden) ───────────────

_default_store: Optional[CredentialStore] = None
_default_store_lock = threading.Lock()


def set_default_credential_store(store: CredentialStore) -> None:
    """Replace the process-wide default CredentialStore.

    Call before any agent code that uses credential_pool to route all
    auth.json access through *store* instead of ``bwm_cli.auth`` directly.
    """
    global _default_store
    with _default_store_lock:
        _default_store = store


def get_default_credential_store() -> CredentialStore:
    """Return the process-wide default CredentialStore.

    If no store has been set, lazily creates the real ``AuthCredentialStore``
    (which wraps ``bwm_cli.auth`` primitives).
    """
    global _default_store
    if _default_store is not None:
        return _default_store

    with _default_store_lock:
        if _default_store is not None:
            return _default_store

        # Lazy import to avoid circular dependency
        try:
            from bwm_cli.auth_credential_store import AuthCredentialStore
            _default_store = AuthCredentialStore()
        except ImportError:
            raise RuntimeError(
                "No CredentialStore configured. Either call "
                "set_default_credential_store(store) or ensure "
                "bwm_cli.auth_credential_store is importable."
            )
        return _default_store
