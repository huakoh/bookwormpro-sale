---
name: gateway-module-integration
description: >
  Standard 5-point injection pattern for adding robustness modules to
  BookwormPRO's run_agent.py (13K+ lines). Used by circuit_breaker,
  provider_health, dns_resolver, metrics_store, and graceful drain.
  When adding a new module that must intercept all API calls, follow
  this pattern exactly.
category: devops
---

# Gateway Module Integration Pattern

When adding a new robustness module that needs to intercept every API call
in `run_agent.py` (circuit breaker, health probe, DNS, metrics, drain),
there are exactly 5 integration points:

## The 5-Point Pattern

| # | Point | Lines from top | What |
|---|-------|---------------|------|
| 1 | Import | ~84 | `from agent.module import fn as _alias` |
| 2 | Pre-call guard | ~10060 | Check before API call, skip+fallback if blocked |
| 3 | Post-success | ~10180 | Record success after `api_duration` |
| 4 | Post-failure | ~10960 | Record failure after `classify_api_error()` |
| 5 | Cleanup | ~4340 | Clean resources in `close()` |

## Point 1: Import

Always use `_` prefix aliases to avoid shadowing and make integration points
greppable:

```python
from agent.new_module import check_fn as _mod_check, record_fn as _mod_record
```

## Point 2: Pre-call Guard

Insert **before** the API call (after rate limit guard, before `_reset_stream_delivery_tracking`).
MUST be wrapped in try/except to never crash the agent loop:

```python
try:
    if not _mod_check(self.provider):
        self._vprint(f'{self.log_prefix}[blocked] Provider blocked.', force=True)
        if self._try_activate_fallback():
            retry_count = 0
            continue
        # No fallback → return error
        self._persist_session(messages, conversation_history)
        return {
            'final_response': f'[blocked] Provider unavailable.',
            'messages': messages,
            'api_calls': api_call_count,
            'completed': False, 'failed': True,
        }
except Exception:
    pass  # Never let guard break the agent loop
```

## Point 3: Post-Success

Insert after `api_duration = time.time() - api_start_time`:

```python
try:
    _mod_record(self.provider, api_duration)
except Exception:
    pass
```

## Point 4: Post-Failure

Insert after `classify_api_error(...)` call:

```python
try:
    _mod_failure(self.provider, error=api_error, reason=classified.reason.value, status_code=status_code)
except Exception:
    pass
```

## Point 5: Cleanup

Insert in `close()` method, after existing cleanup steps:

```python
# N. Clean up module resources
try:
    with self._some_lock:
        resources = list(self._some_dict.values())
        self._some_dict.clear()
    for r in resources:
        try:
            r.close()
        except Exception:
            pass
except Exception:
    pass
```

## File-Based State Pattern

For modules that need cross-process state (circuit breaker, health probe),
follow the `nous_rate_guard.py` pattern:

```python
def _state_path(provider: str) -> str:
    try:
        from bwm_constants import get_hermes_home
        base = get_hermes_home()
    except ImportError:
        base = os.path.join(os.path.expanduser("~"), ".bookwormpro")
    return os.path.join(base, "subdir", f"{provider}.json")

def _save_record(record):
    fd, tmp_path = tempfile.mkstemp(dir=state_dir, suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(state, f)
    os.replace(tmp_path, path)  # atomic
```

## Adding to run_agent.py (13K+ lines)

1. Write ALL 5 edits in a SINGLE `.py` script
2. Use `content.replace(old_block, new_block, 1)` for each
3. Use `repr()` to debug failed matches
4. Always end with `py_compile.compile(target, doraise=True)`
5. Never use `patch` tool on files >5000 lines

## Testing

After integration:
1. `py_compile` — syntax check
2. Unit tests for the module itself
3. Integration test verifying the chain (circuit→metrics, health→circuit)

## Pitfalls

- **f-string `\n` in final_response blocks**: Use `chr(10)` instead of `\n`
- **Module-level constants vs class body**: Insert constants ABOVE `class AIAgent:`
- **Throttle checks**: Guard code must be O(1) — no network calls, no file I/O in hot path
- **Thread safety**: Use locks (`_lock = threading.Lock()`) for shared dicts
