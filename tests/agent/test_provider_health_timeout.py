"""Regression guard for the provider health-probe timeout.

Slow aggregating relays behind a proxy (e.g. bww.letcareme.com) legitimately
take 6-9s for the TLS handshake + /models response.  A 5s probe timeout turned
such a healthy-but-slow provider into repeated handshake timeouts → 3 failures
→ DEAD → circuit trip → silent fallback to another provider on every call.

The probe runs at most once per cooldown and is off the hot path, so the
ceiling must stay comfortably above real-world slow-relay latency.
"""

from agent import provider_health as ph


def test_probe_timeout_tolerates_slow_relay_handshake():
    # Must clear the observed ~6-9s slow-relay latency with margin. Anything
    # back down near the old 5s reintroduces the false-DEAD regression.
    assert ph._PROBE_TIMEOUT >= 10.0


def test_probe_signature_default_uses_module_timeout():
    # _do_http_probe must default to the module-level ceiling so the constant
    # is the single source of truth for both httpx and urllib probe paths.
    import inspect

    for fn in (ph._do_http_probe, ph._do_http_probe_urllib):
        default = inspect.signature(fn).parameters["timeout"].default
        assert default == ph._PROBE_TIMEOUT


def test_reachable_status_codes_treated_as_alive():
    # 401/403/404/405 mean "endpoint answered" — a slow but authenticated relay
    # that rejects the unauthenticated probe must still count as reachable, not
    # dead. This guards the intent alongside the raised timeout.
    src = __import__("inspect").getsource(ph._do_http_probe_urllib)
    assert "401" in src and "403" in src and "404" in src and "405" in src
