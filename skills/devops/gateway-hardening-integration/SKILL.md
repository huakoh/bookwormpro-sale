---
name: gateway-hardening-integration
description: >
  Pattern for integrating gateway robustness modules into BookwormPRO's run_agent.py.
  Covers circuit breaker, health probe, DNS resolver, metrics, response validator, and
  connection pool modules. Each follows the same 6-point integration contract. Use when
  adding new gateway hardening modules or troubleshooting existing ones.
category: devops
---

# Gateway Hardening Integration Pattern

When adding any gateway hardening module to BookwormPRO, follow this
six-point integration contract in `run_agent.py`.

## Integration Contract (6 points)

Every module MUST integrate at these 6 points:

### 1. Import (top of file, near related imports)
```python
from agent.<module> import <function> as _<short_name>
```

### 2. Init (in AIAgent.__init__)
```python
self._<state> = {}
self._<lock> = threading.Lock()
```

### 3. Pre-API Gate (in retry loop, before API call)
Check conditions and skip/fail fast if blocked. Order:
1. Drain check (highest priority)
2. DNS warm-up (pre-resolve)
3. Health probe (lazy, cooldown-gated)
4. Circuit breaker

All gates must be wrapped in `try/except` to never crash the agent loop.

### 4. Post-Success (after `api_duration` calculation)
```python
try:
    _<module>_success(self.provider, ...)
except Exception:
    pass
```

### 5. Post-Failure (after `classify_api_error`, before debug log)
```python
try:
    _<module>_failure(self.provider, error=..., reason=..., ...)
except Exception:
    pass
```

### 6. Cleanup (in `close()`, step 6+)
```python
with self._<lock>:
    for item in self._<state>.values():
        item.close() / cleanup()
    self._<state>.clear()
```

## File-Based State (cross-process sharing)

For modules that need state visible across CLI/gateway/cron processes
(circuit breaker, health probe), use file-based storage in
`~/.bookwormpro/<subdir>/<provider>.json`:

```python
def _state_path(provider: str) -> str:
    base = os.path.join(os.path.expanduser("~"), ".bookwormpro")
    return os.path.join(base, "<subdir>", f"{provider}.json")

def _save_record(record):
    fd, tmp = tempfile.mkstemp(dir=state_dir, suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(state, f)
    os.replace(tmp, path)  # atomic
```

Pattern from `agent/nous_rate_guard.py` — follow exactly.

## Provider Keys

Use `provider` names consistently across all modules:
`anthropic`, `openrouter`, `deepseek`, `bookwormpro`, `qwen`, `xai`, `kimi`

For custom endpoints, use `hostname:port` or `custom:<name>`.

## Connection Pool Limits

Per-provider limits (in `_POOL_LIMITS`):
```
anthropic:   max_connections=5,  max_keepalive=3  (rate-limited)
deepseek:    max_connections=20, max_keepalive=10 (high capacity)
openrouter:  max_connections=15, max_keepalive=8
default:     max_connections=10, max_keepalive=5
```

## Windows-Specific Pitfalls

When editing `run_agent.py` (13K+ lines, ~670KB):
- NEVER use `patch` tool — always write a `.py` fix script
- f-string `\n` in target file: use `chr(10).join()` or quad-escaping
- After each edit, run `py_compile` before proceeding
- Use `repr()` to debug pattern matching failures

## Module Interaction Matrix

```
Circuit Breaker ←── Health Probe (auto-trip on DEAD)
Circuit Breaker →── Metrics Store (record trip count)
Health Probe    →── Circuit Breaker (auto-reset on HEALTHY)
DNS Resolver    ─── (independent, warmed before API calls)
Response Validator ─ (independent, gate between API response and processing)
Connection Pool ─── (independent, provides httpx.Client to OpenAI wrappers)
```

## Testing

Each new module must have:
1. Unit tests (7-12 items, standalone logic)
2. Integration test (1+ item in `tests/integration/test_gateway_hardening.py`)
3. Benchmark (1 item in `tests/benchmarks/test_gateway_benchmarks.py`)

Run before committing:
```bash
python -m py_compile agent/<module>.py run_agent.py
python tests/integration/test_gateway_hardening.py
```
