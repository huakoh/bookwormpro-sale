"""
auth_credential_store.py — Real CredentialStore backed by bwm_cli.auth primitives.

Part of P2-2 layer violation fix (2026-05-06), Phase 2.

Usage:
    from bwm_cli.auth_credential_store import AuthCredentialStore
    store = AuthCredentialStore()
    with store.auth_store_lock():
        pool = store.read_credential_pool("deepseek")

Design:
    - Wraps existing bwm_cli.auth functions (zero new persistence logic)
    - All public API; private _* functions accessed via explicit imports
    - Thread-safe via _auth_store_lock (fcntl/msvcrt cross-process)
    - Compatible with auth_encryption (transparent AES-256-GCM)
"""

from __future__ import annotations

import copy
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

from bwm_cli.credential_store import (
    AuthStore,
    CredentialStore,
    PoolEntry,
    ProviderState,
)

# ── Import bwm_cli.auth internals (this is the ONLY module that does this
#    outside of auth.py itself; all other code goes through CredentialStore) ─

from bwm_cli.auth import (  # noqa: E402
    _auth_store_lock,
    _load_auth_store,
    _save_auth_store,
    _load_provider_state,
    _save_provider_state,
    read_credential_pool,
    write_credential_pool,
    is_source_suppressed,
    is_provider_explicitly_configured,
)


class AuthCredentialStore(CredentialStore):
    """Production CredentialStore wrapping bwm_cli.auth persistence.

    This is the default store used at runtime.  All method calls delegate
    directly to the existing auth.py primitives — zero new logic, just a
    protocol-compliant facade.

    Thread-safety is provided by ``_auth_store_lock`` (fcntl on POSIX,
    msvcrt on Windows).
    """

    # ── Lock ────────────────────────────────────────────────────────

    @contextmanager
    def auth_store_lock(self, timeout_seconds: float = 15.0):
        """Acquire the cross-process advisory lock."""
        with _auth_store_lock(timeout_seconds):
            yield

    # ── Auth store read / write ─────────────────────────────────────

    def load_auth_store(self) -> AuthStore:
        return _load_auth_store()

    def save_auth_store(self, store: AuthStore) -> None:
        _save_auth_store(store)

    # ── Provider state ──────────────────────────────────────────────

    def load_provider_state(self, provider_id: str) -> Optional[ProviderState]:
        store = _load_auth_store()
        return _load_provider_state(store, provider_id)

    def save_provider_state(
        self, provider_id: str, state: ProviderState
    ) -> None:
        store = _load_auth_store()
        _save_provider_state(store, provider_id, state)
        _save_auth_store(store)

    # ── Credential pool ─────────────────────────────────────────────

    def read_credential_pool(
        self, provider_id: Optional[str] = None
    ) -> Dict[str, List[PoolEntry]]:
        # The original read_credential_pool returns inconsistent types:
        #   read_credential_pool()       → Dict[str, List]  (whole pool)
        #   read_credential_pool("x")   → List[PoolEntry]   (one provider's entries)
        # We normalize to always return Dict[str, List].
        raw = read_credential_pool(provider_id)
        if provider_id is not None:
            # raw is a list — wrap it
            return {provider_id: copy.deepcopy(raw)}
        return copy.deepcopy(raw) if isinstance(raw, dict) else {}

    def write_credential_pool(
        self, provider_id: str, entries: List[PoolEntry]
    ) -> None:
        write_credential_pool(provider_id, entries)

    # ── Source management ───────────────────────────────────────────

    def is_source_suppressed(self, provider_id: str, source: str) -> bool:
        return is_source_suppressed(provider_id, source)

    # ── Provider configuration ──────────────────────────────────────

    def is_provider_explicitly_configured(self, provider_id: str) -> bool:
        return is_provider_explicitly_configured(provider_id)
