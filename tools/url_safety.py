"""URL safety checks — blocks requests to private/internal network addresses.

Prevents SSRF (Server-Side Request Forgery) where a malicious prompt or
skill could trick the agent into fetching internal resources like cloud
metadata endpoints (169.254.169.254), localhost services, or private
network hosts.

The check can be globally disabled via ``security.allow_private_urls: true``
in config.yaml for environments where DNS resolves external domains to
private/benchmark-range IPs (OpenWrt routers, corporate proxies, VPNs
that use 198.18.0.0/15 or 100.64.0.0/10).  Even when disabled, cloud
metadata hostnames (metadata.google.internal, 169.254.169.254) are
**always** blocked — those are never legitimate agent targets.

DNS-rebinding mitigation (TOCTOU):
  ``resolve_and_validate(url)`` resolves the hostname once, validates the IP,
  and returns the resolved IP together with the original URL so callers can
  construct a direct-IP request (bypassing a second OS-level DNS resolution).
  This closes the TTL=0 rebinding window at the application layer.
  Callers that use httpx should pass the resolved IP in the Host header and
  connect to the IP directly, e.g. via ``_SSRF_TRANSPORT``.

  For a fully kernel-level fix (e.g. in a multi-tenant gateway), an egress
  proxy such as Stripe Smokescreen or Python's ``trusty`` library is
  recommended in addition.

  - Redirect-based bypass is mitigated by httpx event hooks that re-validate
    each redirect target in vision_tools, gateway platform adapters, and
    media cache helpers. Web tools use third-party SDKs (Firecrawl/Tavily)
    where redirect handling is on their servers.
"""

import ipaddress
import logging
import os
import socket
from typing import Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Hostnames that should always be blocked regardless of IP resolution
# or any config toggle.  These are cloud metadata endpoints that an
# attacker could use to steal instance credentials.
_BLOCKED_HOSTNAMES = frozenset({
    "metadata.google.internal",
    "metadata.goog",
})

# IPs and networks that should always be blocked regardless of the
# allow_private_urls toggle.  These are cloud metadata / credential
# endpoints — the #1 SSRF target — and the link-local range where
# they all live.
_ALWAYS_BLOCKED_IPS = frozenset({
    ipaddress.ip_address("169.254.169.254"),  # AWS/GCP/Azure/DO/Oracle metadata
    ipaddress.ip_address("169.254.170.2"),     # AWS ECS task metadata (task IAM creds)
    ipaddress.ip_address("169.254.169.253"),   # Azure IMDS wire server
    ipaddress.ip_address("fd00:ec2::254"),     # AWS metadata (IPv6)
    ipaddress.ip_address("100.100.100.200"),   # Alibaba Cloud metadata
})
_ALWAYS_BLOCKED_NETWORKS = (
    ipaddress.ip_network("169.254.0.0/16"),    # Entire link-local range (no legit agent target)
)

# Exact HTTPS hostnames allowed to resolve to private/benchmark-space IPs.
# This is intentionally narrow: QQ media downloads can legitimately resolve
# to 198.18.0.0/15 behind local proxy/benchmark infrastructure.
_TRUSTED_PRIVATE_IP_HOSTS = frozenset({
    "multimedia.nt.qq.com.cn",
})

# 100.64.0.0/10 (CGNAT / Shared Address Space, RFC 6598) is NOT covered by
# ipaddress.is_private — it returns False for both is_private and is_global.
# Must be blocked explicitly. Used by carrier-grade NAT, Tailscale/WireGuard
# VPNs, and some cloud internal networks.
_CGNAT_NETWORK = ipaddress.ip_network("100.64.0.0/10")

# ---------------------------------------------------------------------------
# Global toggle: allow private/internal IP resolution
# ---------------------------------------------------------------------------
# Cached after first read so we don't hit the filesystem on every URL check.
_allow_private_resolved = False
_cached_allow_private: bool = False


def _global_allow_private_urls() -> bool:
    """Return True when the user has opted out of private-IP blocking.

    Checks (in priority order):
    1. ``BOOKWORMPRO_ALLOW_PRIVATE_URLS`` env var  (``true``/``1``/``yes``)
    2. ``security.allow_private_urls`` in config.yaml
    3. ``browser.allow_private_urls`` in config.yaml  (legacy / backward compat)

    Result is cached for the process lifetime.
    """
    global _allow_private_resolved, _cached_allow_private
    if _allow_private_resolved:
        return _cached_allow_private

    _allow_private_resolved = True
    _cached_allow_private = False  # safe default

    # 1. Env var override (highest priority)
    env_val = os.getenv("BOOKWORMPRO_ALLOW_PRIVATE_URLS", "").strip().lower()
    if env_val in ("true", "1", "yes"):
        _cached_allow_private = True
        return _cached_allow_private
    if env_val in ("false", "0", "no"):
        # Explicit false — don't fall through to config
        return _cached_allow_private

    # 2. Config file
    try:
        from bwm_cli.config import read_raw_config
        cfg = read_raw_config()
        # security.allow_private_urls (preferred)
        sec = cfg.get("security", {})
        if isinstance(sec, dict) and sec.get("allow_private_urls"):
            _cached_allow_private = True
            return _cached_allow_private
        # browser.allow_private_urls (legacy fallback)
        browser = cfg.get("browser", {})
        if isinstance(browser, dict) and browser.get("allow_private_urls"):
            _cached_allow_private = True
            return _cached_allow_private
    except Exception:
        # Config unavailable (e.g. tests, early import) — keep default
        pass

    return _cached_allow_private


def _reset_allow_private_cache() -> None:
    """Reset the cached toggle — only for tests."""
    global _allow_private_resolved, _cached_allow_private
    _allow_private_resolved = False
    _cached_allow_private = False


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return True if the IP should be blocked for SSRF protection."""
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
        return True
    if ip.is_multicast or ip.is_unspecified:
        return True
    # CGNAT range not covered by is_private
    if ip in _CGNAT_NETWORK:
        return True
    return False


def _allows_private_ip_resolution(hostname: str, scheme: str) -> bool:
    """Return True when a trusted HTTPS hostname may bypass IP-class blocking."""
    return scheme == "https" and hostname in _TRUSTED_PRIVATE_IP_HOSTS


def _resolve_to_ip(hostname: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Resolve *hostname* to a list of IP address objects.

    Returns an empty list on DNS failure (caller should treat as blocked).
    Uses ``AF_UNSPEC`` so both IPv4 and IPv6 records are returned.
    """
    try:
        addr_info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror:
        return []
    ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for _family, _type, _proto, _canon, sockaddr in addr_info:
        ip_str = sockaddr[0]
        try:
            ips.append(ipaddress.ip_address(ip_str))
        except ValueError:
            continue
    return ips


def _validate_resolved_ip(
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
    hostname: str,
    scheme: str,
    allow_all_private: bool,
) -> bool:
    """Return True if *ip* is allowed for the given *hostname*/*scheme*.

    Centralises the per-IP block logic so both ``is_safe_url`` and
    ``resolve_and_validate`` share identical rules.
    """
    # Always-blocked IPs and link-local range — no toggle overrides these
    if ip in _ALWAYS_BLOCKED_IPS or any(ip in net for net in _ALWAYS_BLOCKED_NETWORKS):
        logger.warning(
            "Blocked request to cloud metadata address: %s -> %s",
            hostname, ip,
        )
        return False

    allow_private_ip = _allows_private_ip_resolution(hostname, scheme)
    if not allow_all_private and not allow_private_ip and _is_blocked_ip(ip):
        logger.warning(
            "Blocked request to private/internal address: %s -> %s",
            hostname, ip,
        )
        return False

    return True


def resolve_and_validate(url: str) -> Optional[Tuple[str, str]]:
    """Resolve *url*'s hostname to a validated IP and return ``(ip_str, url)``.

    This is the DNS-rebinding mitigation layer.  By resolving the hostname
    *once* and returning the resolved IP, callers can connect directly to
    the IP (pinning the connection to the validated address) rather than
    letting the OS re-resolve the name for the actual TCP connect — which
    would open a TTL=0 rebinding window.

    Usage pattern for httpx callers::

        result = resolve_and_validate("https://example.com/path")
        if result is None:
            raise ValueError("SSRF: URL blocked")
        resolved_ip, original_url = result
        # Connect to resolved_ip with Host header set to the original hostname.

    Returns:
        ``(resolved_ip_str, original_url)`` if the URL is safe.
        ``None`` if the URL is blocked (private IP, metadata endpoint, bad DNS,
        or any unexpected error).

    The ``allow_private_urls`` toggle and trusted-hostname whitelist are both
    respected, same as ``is_safe_url``.
    """
    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").strip().lower().rstrip(".")
        scheme = (parsed.scheme or "").strip().lower()

        if not hostname:
            return None

        # Always-blocked hostnames — no IP check needed
        if hostname in _BLOCKED_HOSTNAMES:
            logger.warning("Blocked request to internal hostname: %s", hostname)
            return None

        allow_all_private = _global_allow_private_urls()

        ips = _resolve_to_ip(hostname)
        if not ips:
            logger.warning("Blocked request — DNS resolution failed for: %s", hostname)
            return None

        # Validate every resolved IP; reject if any is blocked.
        for ip in ips:
            if not _validate_resolved_ip(ip, hostname, scheme, allow_all_private):
                return None

        # Return the first resolved IP as the canonical connect address.
        # Callers should use this IP for the actual connection to avoid
        # a second OS-level DNS resolution (the TOCTOU rebinding window).
        resolved_ip_str = str(ips[0])
        logger.debug("resolve_and_validate: %s -> %s (validated)", hostname, resolved_ip_str)
        return resolved_ip_str, url

    except Exception as exc:
        logger.warning("Blocked request — resolve_and_validate error for %s: %s", url, exc)
        return None


def is_safe_url(url: str) -> bool:
    """Return True if the URL target is not a private/internal address.

    Resolves the hostname to an IP and checks against private ranges.
    Fails closed: DNS errors and unexpected exceptions block the request.

    When ``security.allow_private_urls`` is enabled (or the env var
    ``BOOKWORMPRO_ALLOW_PRIVATE_URLS=true``), private-IP blocking is skipped.
    Cloud metadata endpoints (169.254.169.254, metadata.google.internal)
    remain blocked regardless — they are never legitimate agent targets.
    """
    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").strip().lower().rstrip(".")
        scheme = (parsed.scheme or "").strip().lower()
        if not hostname:
            return False

        # Block known internal hostnames — ALWAYS, even with toggle on
        if hostname in _BLOCKED_HOSTNAMES:
            logger.warning("Blocked request to internal hostname: %s", hostname)
            return False

        # Check the global toggle AFTER blocking metadata hostnames
        allow_all_private = _global_allow_private_urls()

        allow_private_ip = _allows_private_ip_resolution(hostname, scheme)

        # Resolve hostname once and validate every returned IP.
        # Using _resolve_to_ip + _validate_resolved_ip ensures is_safe_url
        # and resolve_and_validate share identical block logic.
        ips = _resolve_to_ip(hostname)
        if not ips:
            # DNS resolution failed — fail closed.
            logger.warning("Blocked request — DNS resolution failed for: %s", hostname)
            return False

        for ip in ips:
            if not _validate_resolved_ip(ip, hostname, scheme, allow_all_private):
                return False

        if allow_all_private:
            logger.debug(
                "Allowing private/internal resolution (security.allow_private_urls=true): %s",
                hostname,
            )
        elif allow_private_ip:
            logger.debug(
                "Allowing trusted hostname despite private/internal resolution: %s",
                hostname,
            )

        return True

    except Exception as exc:
        # Fail closed on unexpected errors — don't let parsing edge cases
        # become SSRF bypass vectors
        logger.warning("Blocked request — URL safety check error for %s: %s", url, exc)
        return False


# ---------------------------------------------------------------------------
# XSS href safety — scheme allowlist (separate from SSRF protection above)
# ---------------------------------------------------------------------------

# Schemes safe to render as clickable <a href="..."> links.
# javascript:/data:/vbscript: and similar are intentionally excluded.
_SAFE_HREF_SCHEMES = frozenset({"https", "http", "mailto", "tel"})


def is_safe_href(url: str) -> bool:
    """Check whether *url* is safe to render as a clickable hyperlink.

    Unlike ``is_safe_url()`` which guards against SSRF (server-side
    requests to internal infrastructure), this function defends against
    client-side XSS via dangerous URL schemes
    (``javascript:``, ``data:``, ``vbscript:``, etc.).

    Rules
    -----
    - Empty / non-string input → False.
    - Relative paths (``/foo/bar``) and anchor links (``#section``) → True
      (no scheme means the browser keeps the current origin).
    - Scheme present → must be in ``_SAFE_HREF_SCHEMES`` allowlist.
    - Any parse error → False (fail closed).

    This function does **not** perform DNS resolution or IP-class checks;
    pair it with ``is_safe_url()`` / ``resolve_and_validate()`` when the
    server also fetches the URL.
    """
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    scheme = (parsed.scheme or "").strip().lower()
    if not scheme:
        # Relative URL (starts with /) or anchor (#section) — safe
        return url.startswith(("/", "#"))
    return scheme in _SAFE_HREF_SCHEMES
