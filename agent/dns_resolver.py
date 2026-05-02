"""TTL-aware DNS resolver for provider endpoints.

Problem: System DNS resolvers may cache beyond TTL, causing extended
outages when a provider switches IPs.  Some resolvers ignore TTL
entirely, holding stale records for minutes.

Solution: Application-level DNS cache with TTL enforcement.
- Default TTL: 300s (5 min) for unknown records
- Force-refresh on connection errors (bypass TTL)
- IPv4/IPv6 dual-stack support
- Thread-safe

Zero external dependencies — uses only stdlib socket + threading.
"""

from __future__ import annotations

import logging
import socket
import threading
import time
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Default TTL when DNS doesn't provide one
_DEFAULT_TTL = 300  # 5 minutes
# Minimum TTL to enforce (some providers set 1s TTL which is excessive)
_MIN_TTL = 30       # 30 seconds
# Maximum TTL (to force periodic refresh even for long TTLs)
_MAX_TTL = 600      # 10 minutes


class _CacheEntry:
    """A cached DNS resolution result with TTL."""
    __slots__ = ('addresses', 'resolved_at', 'ttl', 'hostname')

    def __init__(self, addresses: List[Tuple[str, int]], ttl: float, hostname: str):
        self.addresses = addresses  # list of (ip, port) tuples
        self.resolved_at = time.time()
        self.ttl = max(_MIN_TTL, min(ttl, _MAX_TTL))
        self.hostname = hostname

    @property
    def expired(self) -> bool:
        return (time.time() - self.resolved_at) >= self.ttl

    @property
    def age(self) -> float:
        return time.time() - self.resolved_at


class DNSResolver:
    """Thread-safe DNS resolver with TTL-aware caching.

    Usage:
        resolver = DNSResolver()
        addresses = resolver.resolve('api.openai.com', 443)
        # ... make HTTP request ...
        # On connection error, force refresh:
        resolver.invalidate('api.openai.com')
        addresses = resolver.resolve('api.openai.com', 443, force=True)
    """

    def __init__(self):
        self._cache: Dict[str, _CacheEntry] = {}
        self._lock = threading.Lock()
        self._hits: int = 0
        self._misses: int = 0
        self._refreshes: int = 0

    @staticmethod
    def _proxy_active() -> bool:
        """Check if an HTTP/HTTPS proxy is configured in env vars."""
        import os as _os
        for key in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
            if _os.getenv(key, "").strip():
                return True
        return False

    def resolve(
        self,
        hostname: str,
        port: int = 443,
        *,
        force: bool = False,
    ) -> List[Tuple[str, int]]:
        """Resolve a hostname to (ip, port) tuples.

        When a proxy is active, DNS resolution is SKIPPED — the proxy
        handles DNS on its own.  Calling socket.getaddrinfo() would leak
        the user's IP via system DNS.

        Args:
            hostname: The hostname to resolve.
            port: The port number.
            force: If True, bypass cache.

        Returns:
            List of (ip, port) tuples, or empty list when proxy is active.
        """
        if not hostname:
            return []

        # Proxy is active: skip DNS to avoid IP leak. The proxy resolves.
        if self._proxy_active():
            return []

        key = f"{hostname}:{port}"

        # Check cache (unless forced)
        if not force:
            with self._lock:
                entry = self._cache.get(key)
                if entry is not None and not entry.expired:
                    self._hits += 1
                    logger.debug(
                        "DNS cache HIT for %s (age=%.0fs, ttl=%.0fs, %d addresses)",
                        hostname, entry.age, entry.ttl, len(entry.addresses),
                    )
                    return list(entry.addresses)

        # Resolve
        self._misses += 1
        if force:
            self._refreshes += 1
            logger.debug("DNS cache FORCE REFRESH for %s", hostname)

        try:
            addrs = socket.getaddrinfo(
                hostname, port,
                proto=socket.IPPROTO_TCP,
            )
        except socket.gaierror as e:
            logger.warning("DNS resolution failed for %s: %s", hostname, e)
            # Return cached addresses if available (even if expired)
            with self._lock:
                stale = self._cache.get(key)
                if stale is not None:
                    logger.info(
                        "DNS serving STALE cache for %s (age=%.0fs, TTL expired)",
                        hostname, stale.age,
                    )
                    return list(stale.addresses)
            return []

        # Extract (ip, port) and sort IPv4 first
        addresses: List[Tuple[str, int]] = []
        for family, _, _, _, sockaddr in addrs:
            ip = sockaddr[0]
            port_val = sockaddr[1]
            addresses.append((ip, port_val))

        # Sort: IPv4 first, then IPv6
        addresses.sort(key=lambda a: (':' in a[0], a[0]))

        # Cache with default TTL (socket.getaddrinfo doesn't return TTL)
        # DNS queries through system resolver have TTL embedded but not exposed.
        # We use a conservative default.
        entry = _CacheEntry(addresses=addresses, ttl=_DEFAULT_TTL, hostname=hostname)

        with self._lock:
            self._cache[key] = entry

        logger.debug(
            "DNS resolved %s → %d addresses (cached for %.0fs)",
            hostname, len(addresses), entry.ttl,
        )
        return addresses

    def invalidate(self, hostname: str, port: int = 443) -> None:
        """Force-remove a hostname from cache (e.g. after connection error)."""
        key = f"{hostname}:{port}"
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug("DNS cache INVALIDATED for %s", hostname)

    def get_stats(self) -> dict:
        """Return cache statistics."""
        with self._lock:
            return {
                "cache_size": len(self._cache),
                "hits": self._hits,
                "misses": self._misses,
                "refreshes": self._refreshes,
                "entries": {
                    key: {
                        "hostname": entry.hostname,
                        "age": entry.age,
                        "ttl": entry.ttl,
                        "address_count": len(entry.addresses),
                        "expired": entry.expired,
                    }
                    for key, entry in self._cache.items()
                },
            }

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.debug("DNS cache cleared (%d entries)", count)


# Module-level singleton for process-wide DNS caching
_resolver: Optional[DNSResolver] = None
_resolver_lock = threading.Lock()


def get_resolver() -> DNSResolver:
    """Get or create the module-level DNS resolver singleton."""
    global _resolver
    if _resolver is None:
        with _resolver_lock:
            if _resolver is None:
                _resolver = DNSResolver()
    return _resolver


def resolve_provider(
    hostname: str,
    port: int = 443,
    *,
    force: bool = False,
) -> List[Tuple[str, int]]:
    """Convenience: resolve using the singleton resolver."""
    return get_resolver().resolve(hostname, port, force=force)


def invalidate_provider(hostname: str, port: int = 443) -> None:
    """Convenience: invalidate a cached entry."""
    get_resolver().invalidate(hostname, port)
