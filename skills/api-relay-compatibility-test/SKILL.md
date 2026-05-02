---
name: api-relay-compatibility-test
description: >
  中转站/Relay API 兼容性快速验证 — 在将任何 API 接入架构前，用最小载荷
  快速探测兼容性、限流、参数支持、延迟。避免"先设计架构再发现不可用"的返工。
  触发词：测中转站、验证 relay、API 兼容测试、relay compatibility test
category: devops
maturity: alpha
cost_level: low
last-reviewed: 2026-05-02
---

# API Relay 兼容性快速验证

## 何时使用

**在架构设计中引入任何中转站/Relay API 之前**，必须先跑此 Skill。不要基于"理论兼容"做架构决策。

典型场景：
- 新模型通过中转站接入（如 gpt-image-2 via bww.your-domain.com）
- 更换 API 网关/代理
- 评估"这个 Relay 能不能用"时

## 核心原则

> **理论兼容 ≠ 实际可用。架构决策必须在实测数据上做。**

## 四步验证法

### Step 1: 模型列表探测（30s）

验证 Relay 是否注册了目标模型：

```python
resp = requests.get(f"{base_url}/models", headers=auth_header, timeout=10)
models = [m["id"] for m in resp.json()["data"]]
target_exists = target_model in models
```

结果判断：
- `target_model in models` → 继续 Step 2
- 不在列表 → Relay 不支持此模型，立即放弃

### Step 2: 最小参数生成测试（2min，3次尝试）

用尽可能少的参数调用，逐步发现 Relay 对参数的限制：

```python
# 尝试 1: 完整参数
payload = {"model": target, "prompt": "test", "n": 1, "size": "256x256", "response_format": "b64_json"}

# 尝试 2: 去 response_format
payload = {"model": target, "prompt": "test", "n": 1, "size": "256x256"}

# 尝试 3: 最小参数
payload = {"model": target, "prompt": "test"}
```

每次记录：Status Code、错误消息、耗时。

### Step 3: 失败模式分类

将每次失败归入以下类别：

| 状态码 | 错误特征 | 含义 | 应对 |
|--------|---------|------|------|
| 200 | b64_json/url 存在 | 完全可用 | 直接集成 |
| 429 | "Unknown parameter" / "未知参数" | ⚠️ 不是真限流! Relay 不支持该参数 | 去掉那个参数后重试 Step 2 |
| 429 | "负载饱和" / "限流" / "RateLimit" | 并发配额耗尽 | 标记为"不可靠"，降级使用 |
| Timeout >30s | 无响应 | 排队或处理过慢 | 标记为"不可靠" |
| 401/403 | 鉴权错误 | Key 无权限 | 检查 Key 或放弃 |
| 404 | 端点不存在 | Relay 不暴露此端点 | 检查是否有替代端点或放弃 |

> ⚠️ **429 歧义陷阱**: 429 在 Relay 场景下有两种完全不同的含义。
> 如果错误消息是 "Unknown parameter" → **不是限流**，只是参数不支持，去掉重试即可。
> 如果错误消息是 "负载饱和"/"RateLimit" → 真限流，Relay 不可靠。
> **不要看到 429 就放弃，先读 error.message。**

### Step 4: 架构调整

根据 Step 3 的结论调整架构：

```
完全可用 → 作为 Primary Provider
参数受限 → 适配参数，作为 Secondary Provider
不可靠(限流/超时) → 作为 Optional/Fallback，不作为 Primary
不可用(404/403) → 放弃，寻找替代方案
```

## 本次实战教训

**案例**: gpt-image-2 via bww.your-domain.com

```
Step 1: ✅ 模型列表有 gpt-image-2
Step 2: ⚠️ response_format 参数被拒（429 "Unknown parameter"）
Step 2: ⚠️ 无 response_format 时超时 >60s
Step 2: ⚠️ 小尺寸请求触发限流（429 "上游负载已饱和"）
Step 3: → 分类为"不可靠"
Step 4: → 调整为 Optional 高质模式，DashScope 保持 Primary
```

**教训**: 如果先跑此 Skill 再做架构设计，就不会浪费 P0-P2 修复中大量代码围绕 gpt-image-2 展开。正确顺序是：**先验证 → 再设计 → 再编码**。

## 检验清单

```
[ ] /models 端点可达
[ ] 目标模型在列表中
[ ] 最小参数生成成功（200 + 图片返回）
[ ] 完整参数生成成功
[ ] 耗时 < 30s (广告图场景) 或 < 60s (高质量场景)
[ ] 连续 3 次成功 (证明非偶发)
[ ] 限流/超时频率 < 20%
[ ] 成本在预算内
```

以上 9 条全部通过 → 可以作为 Primary Provider。
