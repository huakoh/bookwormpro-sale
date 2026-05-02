---
name: bookwormpro-provider-health-probe
description: >
  BookwormPRO LLM provider health probe — discover all configured providers
  (auth.json + .env), probe each with HTTP GET, log results, trip circuit
  breakers for dead providers. Triggers: provider health, probe providers,
  check API endpoints, provider status.
version: 1.0.0
author: BookwormPRO (2026-05-02 实战验证)
tags: [health-check, providers, circuit-breaker, diagnostics, cron]
category: system-tools
maturity: stable
cost_level: medium
safety:
  level: low
  permissions: [read_file, terminal, write_file]
---

# BookwormPRO Provider Health Probe

Probes all configured LLM providers via HTTP GET to their base URL,
detecting dead providers before API calls fail. Designed as both a
cron job and a manual diagnostic.

## Trigger Conditions

- "check providers" / "provider health" / "probe providers"
- "API endpoint status" / "are my LLM backends up?"
- Scheduled cron for proactive liveness detection

## Provider Discovery

Providers are discovered from two sources:

1. **auth.json** — `credential_pool` entries with `auth_type: api_key` and `base_url`
2. **.env** — `<PROVIDER>_BASE_URL` entries (ignored if already in auth.json)

Non-LLM entries (weixin, weixin_cdn, etc.) are included but flagged as platform endpoints,
not LLM providers.

## Execution

```bash
cd C:/Users/BOOKWORMPRO_USER/BookwormPRO && python scripts/provider_health_probe.py
```

The script:
1. Discovers all providers from auth.json + .env
2. Calls `agent.provider_health.probe(provider, base_url, force=True)` for each
3. If DEAD: trips circuit breaker via `agent.circuit_breaker.report_failure()`
4. Saves report to `~/.bookwormpro/debug/provider_health_report.json`
5. Appends to `~/.bookwormpro/debug/provider_health.log`

## Output

```
Provider       Status     Latency    Circuit    Base URL
────────       ──────     ───────    ───────    ────────
deepseek       HEALTHY    150ms      CLOSED     api.deepseek.com/v1
openrouter     HEALTHY    1114ms     CLOSED     openrouter.ai/api/v1
...

[成功] HEALTHY: 7  [警告] DEGRADED: 0  [失败] DEAD: 0
```

## Copilot False-Positive

GitHub Copilot's API (`https://api.githubcopilot.com`) does not expose a
standard REST `/models` endpoint:
- `GET /models` → HTTP 400
- `HEAD /` → HTTP 404

The `provider_health._build_probe_url()` function has no copilot-specific
probe path, so copilot always fails the probe. This is a probe limitation,
not a provider outage. Copilot uses ACP subprocess transport, not HTTP.

**If copilot shows DEGRADED**: reset with:
```python
from agent.provider_health import reset as health_reset
health_reset('copilot')
```

## Health States

| State | Meaning | Action |
|-------|---------|--------|
| HEALTHY | Probe succeeded, circuit CLOSED | None |
| DEGRADED | 1-2 consecutive probe failures | Watch; auto-recovers on next success |
| DEAD | 3+ consecutive failures | Circuit auto-tripped; check provider |
| UNKNOWN | Never probed or manually reset | Next probe will determine |

## Circuit Breaker Integration

- `provider_health.probe()` auto-trips circuit breaker when DEAD detected
- `provider_health.probe()` auto-resets circuit breaker when HEALTHY restored
- The script additionally calls `circuit_breaker.report_failure()` for certainty

## Report Files

- `~/.bookwormpro/debug/provider_health_report.json` — latest structured report
- `~/.bookwormpro/debug/provider_health.log` — append-only log
- `~/.bookwormpro/health/{provider}.json` — per-provider health state
- `~/.bookwormpro/circuits/{provider}.json` — per-provider circuit state

## Related Skills

- `bookwormpro-five-pillar-health-check` — Cron/MCP/Agent/Skills/Routing health
- `bookwormpro-diagnostic-patterns` — diagnostic pitfalls and patterns
- `bookwormpro-system-health-check` — full five-pillar audit
