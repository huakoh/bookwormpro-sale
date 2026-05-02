# Gateway Hardening

BookwormPRO Gateway 健壮性加固文档。覆盖 14 个维度的架构决策、配置指南和故障排查。

## 模块概览

| 模块 | 文件 | 职责 |
|------|------|------|
| 熔断器 | `agent/circuit_breaker.py` | CLOSED→OPEN→HALF_OPEN 状态机，5次连续失败熔断 |
| 连接池复用 | `run_agent.py` `_get_or_create_pooled_http_client()` | 按 provider 缓存 httpx.Client，减少 TLS 握手 |
| 响应校验 | `agent/response_validator.py` | JSON Schema 结构校验，防 provider 格式变更 |
| 健康探活 | `agent/provider_health.py` | GET /models 探活，dead→自动熔断联动 |
| DNS 缓存 | `agent/dns_resolver.py` | TTL 感知缓存，连接错误时强制刷新 |
| 内存背压 | `run_agent.py` 流式循环 | 512KB 响应体上限，超限截断 |
| 优雅关闭 | `run_agent.py` `drain()` | 停止新请求→等待进行中→超时强关 |
| 指标采集 | `agent/metrics_store.py` | P50/P95/P99 延迟、成功率、熔断次数 |
| SSRF 加固 | `agent/auxiliary_client.py` | 用户信息拒绝、IDNA 编码、IPv6 检测 |
| 配置校验 | `bwm_cli/config.py` | dry-run 校验 → 原子降级 |

## 配置

在 `~/.bookwormpro/config.yaml` 中添加 `gateway:` 段覆盖默认值：

```yaml
gateway:
  circuit_breaker:
    failure_threshold: 5
    recovery_seconds: 60
    max_recovery_seconds: 300
  health_probe:
    cooldown_seconds: 30
    probe_timeout: 5
    dead_threshold: 3
  connection_pool:
    max_connections: 20
    max_keepalive: 10
    keepalive_expiry: 30
  memory_backpressure:
    max_response_bytes: 524288
  graceful_drain:
    max_wait_seconds: 25
  dns_cache:
    default_ttl: 300
    min_ttl: 30
    max_ttl: 600
```

## CLI 命令

```
/metrics        显示可读格式
/metrics json   显示 JSON 格式
/metrics watch  实时刷新（TODO）
```

输出示例：
```
Gateway Metrics
==================================================
Uptime: 3600s
SSE leaks: 0

🟢 openrouter
   Calls: 150 (148 ok, 2 fail)
   Success rate: 98.7%
   Latency: avg=450ms p50=0.25s p99=2.0s

🔴 anthropic
   Calls: 10 (0 ok, 10 fail)
   Circuit trips: 2

Circuit Breaker Status
------------------------------
✅ openrouter: closed (failures=0, trips=0)
🔴 anthropic: open (failures=5, trips=2)
```

## 故障排查

### Provider 持续熔断

1. 检查电路状态：`from agent.circuit_breaker import status as cb; cb('openrouter')`
2. 手动重置：`from agent.circuit_breaker import reset; reset('openrouter')`
3. 查看健康状态：`from agent.provider_health import status as hs; hs('openrouter')`
4. 手动探活：`from agent.provider_health import probe; probe('openrouter', base_url='...')`

### DNS 缓存过期

当前实现使用 300s 默认 TTL。连接错误时自动失效。手动失效：

```python
from agent.dns_resolver import invalidate_provider
invalidate_provider('api.openai.com', 443)
```

### 内存背压触发

响应超过 512KB 时截断并设置 `finish_reason='length'`。日志中搜索：
```
Response size cap reached
```

### 优雅关闭超时

Drain 默认等待 25s。可通过 `gateway.graceful_drain.max_wait_seconds` 调整。

## 性能基准

运行: `python tests/benchmarks/test_gateway_benchmarks.py`

| 指标 | 目标 | 实测 |
|------|------|------|
| 电路检查 | <1ms | ~114µs |
| 响应校验 | <500µs | ~0.3µs |
| DNS 缓存命中 | 95%+ | 98% |
| 指标写入 | 50K+ ops/s | 1.5M ops/s |
| 配置校验 | <200µs | ~0.3µs |

## 集成测试

运行: `python tests/integration/test_gateway_hardening.py`

7 项测试覆盖：熔断器→指标流、响应校验、DNS 缓存、优雅关闭、指标快照、配置校验、全链路。
