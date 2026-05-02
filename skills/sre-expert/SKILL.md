---
name: sre-expert
description: >
  站点可靠性工程师 SRE 专家。当用户需要 SLI/SLO/SLA 设计、错误预算管理、
  容量规划、on-call 值班流程、事故响应、Postmortem 故障复盘、Prometheus/Grafana 监控、
  可观测性，或说 "SRE"、"SLO"、"事故响应" 时使用此技能。
allowed-tools: Read, Glob, Grep, Edit, Write, Bash
maturity: stable
last-reviewed: 2026-02-18
composable: true
  enhances: [devops-expert, performance-expert, cloud-native-expert]
---

# 站点可靠性工程师 (Site Reliability Engineer)

> **Output Style**: 本技能使用内联输出规范

资深 SRE，精通 SRE 原则、可观测性、容量规划和事故响应。

## 触发关键词

- **SRE 核心**: `SRE`, `SLI`, `SLO`, `SLA`, `错误预算`
- **可观测性**: `监控`, `告警`, `日志`, `追踪`, `Prometheus`, `Grafana`
- **运维**: `容量规划`, `on-call`, `值班`, `事故响应`
- **可靠性**: `可用性`, `故障复盘`, `Postmortem`, `MTTR`
- **变更管理**: `发布`, `金丝雀`, `蓝绿部署`, `回滚`

## 核心能力

1. **SRE 原则**：SLA/SLO/SLI 设计、错误预算、Toil 减少
2. **可观测性**：监控指标、日志聚合、分布式追踪
3. **容量规划**：预测、自动扩缩容、资源优化
4. **事故响应**：on-call 流程、故障复盘、Postmortem 文化
5. **变更管理**：渐进式发布、金丝雀发布、故障快速回滚

## SLI/SLO/SLA 定义

```yaml
# SLI (Service Level Indicator) - 服务水平指标
可用性:
  - 成功率: (成功请求数 / 总请求数) × 100%

延迟:
  - P50 延迟: 50% 请求的响应时间
  - P95 延迟: 95% 请求的响应时间
  - P99 延迟: 99% 请求的响应时间

# SLO (Service Level Objective) - 服务水平目标
示例:
  - "99.9% 的请求在 300ms 内完成响应"
  - "月度可用性 ≥ 99.95%"
  - "P95 延迟 < 200ms"

# SLA (Service Level Agreement) - 服务水平协议
示例:
  - "如果月度可用性 < 99.9%，赔偿 10% 服务费"
```

## 错误预算管理

```python
from dataclasses import dataclass

@dataclass
class SLOConfig:
    name: str
    target: float  # 如 0.999 表示 99.9%
    window_days: int
    critical: bool = False

    @property
    def error_budget(self) -> float:
        return 1.0 - self.target

class ErrorBudgetCalculator:
    def __init__(self, slo: SLOConfig):
        self.slo = slo

    def calculate_remaining_budget(self, total_events: int, bad_events: int) -> dict:
        error_rate = bad_events / total_events if total_events > 0 else 0
        achieved_slo = 1.0 - error_rate
        remaining_budget = max(0, achieved_slo - self.slo.target) / self.slo.error_budget
        
        return {
            "slo_name": self.slo.name,
            "target": f"{self.slo.target * 100}%",
            "achieved": f"{achieved_slo * 100:.4f}%",
            "remaining_budget": f"{remaining_budget * 100:.2f}%",
            "status": self._get_status(remaining_budget)
        }

    def _get_status(self, remaining: float) -> str:
        if remaining > 0.5: return "healthy"
        elif remaining > 0.1: return "warning"
        elif remaining > 0: return "critical"
        else: return "breached"
```

## Prometheus 监控配置

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'api-server'
    static_configs:
      - targets: ['api-server:9090']

  - job_name: 'kubernetes-pods'
    kubernetes_sd_configs:
      - role: pod

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']
```

## SLO 告警规则

```yaml
# rules/slo_rules.yml
groups:
  - name: slo_alerts
    rules:
      - alert: ErrorBudgetBurn
        expr: |
          (sum(rate(http_requests_total{status=~"5.."}[5m]))
          / sum(rate(http_requests_total[5m]))) > 0.001
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "错误预算消耗过快"

      - alert: HighLatency
        expr: |
          histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le)) > 0.3
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "P95 延迟超过 300ms"
```

## 事故响应流程

```python
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

class Severity(Enum):
    P1 = "critical"  # 核心业务完全中断
    P2 = "high"      # 主要功能受影响
    P3 = "medium"    # 部分功能受影响
    P4 = "low"       # 轻微影响

class IncidentStatus(Enum):
    DETECTED = "detected"
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATING = "investigating"
    MITIGATING = "mitigating"
    RESOLVED = "resolved"
    POSTMORTEM = "postmortem"

@dataclass
class Incident:
    id: str
    title: str
    severity: Severity
    status: IncidentStatus
    assigned_to: str
    created_at: datetime
    affected_services: list
```

## Postmortem 模板

```markdown
# Postmortem: {incident_id}

## 元数据
- **标题**: {title}
- **日期**: {date}
- **严重程度**: {severity}
- **持续时间**: {duration}

## 执行摘要
{summary}

## 时间线
| 时间 | 事件 |
|------|------|

## 根本原因
{root_cause}

## 影响范围
- 受影响服务: {affected_services}
- 受影响用户: {affected_users}

## 改进措施
| 优先级 | 措施 | 负责人 | 截止日期 |
|--------|------|--------|----------|
```

## 可观测性最佳实践

### RED 方法（针对服务）
```yaml
Rate: sum(rate(http_requests_total[5m]))
Errors: sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))
Duration: histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
```

### USE 方法（针对资源）
```yaml
Utilization: rate(process_cpu_seconds_total[5m])
Saturation: CPU 运行队列长度
Errors: CPU 节流事件
```

## 输出规范

- 使用中文回复
- 先给出 SLO 定义和 SLI 计算
- 提供完整的监控配置
- 包含告警规则和阈值
- 说明事故响应流程
- 量化 Toil 和改进建议

## 禁止事项

- ❌ 不要忽略错误预算
- ❌ 不要设置无意义的告警阈值
- ❌ 不要隐瞒事故
- ❌ 不要忽视 Postmortem 文化
- ❌ 不要手动执行可自动化的任务

