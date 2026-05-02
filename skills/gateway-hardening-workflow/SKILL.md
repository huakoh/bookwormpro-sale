---
name: gateway-hardening-workflow
description: Systematic approach for hardening a multi-provider API gateway. Use when asked to harden gateway robustness or audit API proxy resilience.
category: devops
triggers:
  - "加固 Gateway"
  - "Gateway 健壮性"
  - "harden gateway"
  - "API proxy robustness"
---

# Gateway Hardening Workflow

## When to use
When asked to "加固 Gateway 健壮性" or harden any API gateway/proxy layer.

## 12-Dimension Framework
1. Connection resilience (retry + backoff, circuit breaker, connection pool)
2. Graceful degradation (health check, fallback chain)
3. Backpressure & rate limiting
4. SSE stream protection
5. Timeout layering (connect, TTFB, chunk, total)
6. Observability (traceId, P50/P99, availability)
7. Memory backpressure (highWaterMark)
8. DNS cache control (TTL-aware, invalidation on errors)
9. Response format change protection (schema validation)
10. Graceful shutdown (drain pattern)
11. SSRF hardening (userinfo, IDNA, IPv6)
12. Config hot-reload atomic swap

## Pattern
1. Audit: map all 12 dimensions (done/missing)
2. Prioritize: high-impact/low-risk first
3. Build standalone modules, then integrate
4. Add os.getenv feature flags for gray release
5. Integration tests + benchmarks
6. Architecture docs + rollback guide

## Key Decisions
- File-based state (JSON + atomic write) for cross-process modules
- Guard clause pattern for flags (early return, not nested ifs)
- Per-provider config (pool limits, thresholds)
- Master switch: HARDENING_DISABLED=1

## Pitfalls
- Windows f-strings with \n: use chr(10).join()
- CRLF vs patch tool: use Python scripts for bulk edits
- try/except indentation when wrapping existing blocks
