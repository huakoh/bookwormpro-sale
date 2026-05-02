# Gateway Hardening — Rollback & Feature Flags

快速禁用/回滚各加固模块的步骤。

## 逐模块禁用

### 熔断器
```bash
# 禁用: 设置环境变量
export BOOKWORMPRO_CIRCUIT_BREAKER_DISABLED=1

# 手动重置所有熔断器
python -c "
from agent.circuit_breaker import reset
for p in ['openrouter', 'anthropic', 'deepseek', 'bookwormpro']:
    reset(p)
"

# 回滚代码: git revert 熔断器相关提交
# 涉及文件: agent/circuit_breaker.py, run_agent.py (4处)
```

### 连接池复用
```bash
# 禁用: 回退到每次新建 Client
export BOOKWORMPRO_HTTP_POOL_DISABLED=1

# 清理残留连接池
python -c "
import os, glob
for f in glob.glob(os.path.expanduser('~/.bookwormpro/health/*.json')):
    os.unlink(f)
"

# 回滚代码: run_agent.py 中 _get_or_create_pooled_http_client → _build_keepalive_http_client
```

### 响应校验
```bash
# 禁用: 跳过深层校验
export BOOKWORMPRO_RESPONSE_VALIDATION_DISABLED=1

# 回滚代码: run_agent.py 中删除 _validate_response_schema 调用
```

### 健康探活
```bash
# 暂停 cron
cronjob pause <provider-health-probe-job-id>

# 禁用探活
export BOOKWORMPRO_HEALTH_PROBE_DISABLED=1

# 清理探活状态
rm ~/.bookwormpro/health/*.json
```

### DNS 缓存
```bash
# 禁用
export BOOKWORMPRO_DNS_CACHE_DISABLED=1

# 清理 DNS 缓存
python -c "from agent.dns_resolver import get_resolver; get_resolver().clear()"
```

### 内存背压
```bash
# 禁用 (设为极大值)
export BOOKWORMPRO_MAX_RESPONSE_BYTES=1073741824  # 1GB

# 回滚代码: run_agent.py 中删除 _MAX_RESPONSE_BYTES 检查块
```

### 优雅关闭
```bash
# 禁用 (设为 0)
export BOOKWORMPRO_DRAIN_MAX_WAIT=0

# 回滚代码: 删除 run_agent.py 中 _draining 检查块
```

### SSRF 加固
```bash
# 禁用
export BOOKWORMPRO_SSRF_VALIDATION_DISABLED=1

# 回滚代码: git checkout agent/auxiliary_client.py (恢复原 _validate_base_url)
```

### 配置校验
```bash
# 禁用
export BOOKWORMPRO_CONFIG_VALIDATION_DISABLED=1

# 回滚代码: bwm_cli/config.py 中删除 _validate_config_structure 调用
```

## 全部回滚

```bash
# 一键禁用所有加固模块
export BOOKWORMPRO_HARDENING_DISABLED=1

# 清理所有状态文件
rm -rf ~/.bookwormpro/circuits/
rm -rf ~/.bookwormpro/health/
rm -rf ~/.bookwormpro/metrics/

# 回滚代码
git log --oneline | grep -i "gateway.*harden\|circuit.*break\|health.*probe"
# 逐个 git revert <commit>
```

## 灰度发布建议

| 阶段 | 模块 | 观察指标 |
|------|------|---------|
| 1 | 响应校验 + SSRF 加固 | API 失败率无变化 |
| 2 | 连接池复用 + DNS 缓存 | P99 延迟下降 |
| 3 | 熔断器 + 健康探活 | provider 故障恢复时间 |
| 4 | 内存背压 + 优雅关闭 | OOM/连接泄露归零 |
| 5 | 可观测性 | `/metrics` 数据完整 |

## 应急联系方式

- 熔断器手动重置: `from agent.circuit_breaker import reset; reset('<provider>')`
- 查看全量指标: `python -c "from agent.metrics_store import snapshot_json; print(snapshot_json())"`
- 检查健康状态: `python -c "from agent.provider_health import status; print(status('<provider>'))"`


---

## 推荐灰度顺序

| 阶段 | 模块 | 理由 | 观察窗口 |
|------|------|------|---------|
| 1 | 响应校验 + SSRF | 纯防御，零性能影响 | 1天 |
| 2 | 连接池 + DNS | 降低 P99 延迟，不改变行为 | 2天 |
| 3 | 健康探活 + 熔断器 | 改变故障处理行为，需观察 | 3天 |
| 4 | 内存背压 + 优雅关闭 | 极端场景才触发 | 3天 |
| 5 | 全量启用 () | 长期运行 | 持续 |

### 灰度期间监控

```bash
# 每阶段执行
python -c "from agent.metrics_store import snapshot_json; print(snapshot_json())"

# 关注指标
# - success_rate: 不应下降超过 1%
# - circuit_trips: 正常应为 0
# - p99_s latency: 应低于阶段前
```

### 回滚触发条件

-  下降 > 2% → 回退当前阶段
-  > 3/小时 → 禁用熔断器
- 用户报障 请求被拒绝 增多 → 
