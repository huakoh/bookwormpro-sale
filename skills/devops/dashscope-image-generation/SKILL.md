---
name: dashscope-image-generation
description: >
  DashScope (通义万相) 图片生成实战指南。
  当用户需要用 DashScope/通义万相生成图片、广告图、产品图时使用。
  覆盖 API 调用格式、限流处理、内容审核、Prompt 工程等全部踩坑经验。
safety:
  level: medium
  permissions: [read_file, write_file, terminal]
maturity: stable
cost_level: low
last-reviewed: 2026-05-02
dependencies:
  - dashscope (pip install dashscope)
  - Pillow
  - requests
---

# DashScope 图片生成实战指南

> 通义万相 qwen-image-plus · ¥0.04/张 · 国内直连 · 支付宝
> 基于真实踩坑：url 非 b64_json · 429 限流 · 内容审核 · 800字符限制

## 快速开始

```python
import os, time, requests
from dashscope import ImageSynthesis

# 1. API Key
API_KEY = os.environ["DASHSCOPE_API_KEY"]

# 2. 调用（异步模式）
response = ImageSynthesis.call(
    model="qwen-image-plus",
    prompt="你的中文描述",  # 中文 prompt，≤800 字符
    n=1,
    size="1024*1024",
    api_key=API_KEY
)

# 3. 轮询等待 + 下载
task_id = response.output.task_id
for _ in range(30):
    time.sleep(2)
    result = ImageSynthesis.fetch(task_id, api_key=API_KEY)
    if result.output.task_status == "SUCCEEDED":
        # ⚠️ 关键：返回 url 非 b64_json
        img_url = result.output.results[0].url
        image_bytes = requests.get(img_url, timeout=30).content
        with open("output.png", "wb") as f:
            f.write(image_bytes)
        break
```

## 致命踩坑 (实战验证)

### 1. 返回格式：url 非 b64_json ⚠️

```python
# ❌ 错误 — 这样会 KeyError
b64 = result.output.results[0]["b64_image"]

# ✅ 正确 — DashScope 返回 oss URL
url = result.output.results[0].url
image_bytes = requests.get(url, timeout=30).content
```

### 2. 并发限流 (429 Throttling.RateQuota) ⚠️

```
并发请求 > 1 → 立即 429
```

**解决方案：**
- 串行调用，每次间隔 2-3 秒
- `MAX_CONCURRENT = 1`（不要用 ThreadPoolExecutor）
- 加 429 重试逻辑：等待 `delay * (attempt + 1)` 秒

```python
for attempt in range(3):
    response = ImageSynthesis.call(...)
    if response.status_code == 429:
        if attempt < 2:
            time.sleep(3 * (attempt + 1))
            continue
        raise RuntimeError("Rate limited after 3 retries")
    break
```

### 3. 内容安全审核 (Content Filter) ⚠️

特定词汇组合会触发拦截：
- "药品" + "认证" → "Output data may contain inappropriate content"
- "GSP" + "药品" → 被拦截

**解决方案：**
- 避免在 prompt 中同时出现"药品"和合规/认证类词汇
- 用"医疗物资"、"健康产品"等中性词替代
- 侧重视觉描述，不提敏感行业术语
- 拦截后自动重试 sanitized prompt

### 4. Prompt 800 字符限制

```python
prompt = prompt[:800]  # 硬截断会切在句子中间

# 智能截断：在完整句子边界截断
def truncate_at_sentence(text, max_chars=800):
    if len(text) <= max_chars:
        return text
    for delimiter in ["。", "！", "？"]:
        idx = text[:max_chars].rfind(delimiter)
        if idx > max_chars * 0.7:
            return text[:idx + 1]
    return text[:max_chars - 3] + "..."
```

### 5. 不支持 Negative Prompt

无 `negative_prompt` 参数。通过正面描述规避：
- "无文字" → "纯色金色表面无任何文字字母或标志"
- "无畸变" → "自然光影，真实质感，专业摄影"

## 费用

| 模型 | 尺寸 | 每张成本 |
|------|------|---------|
| qwen-image-plus | 1024×1024 | ¥0.04 |
| qwen-image-plus | 720×1280 | ¥0.04 |
| qwen-image-max | 1024×1024 | ¥0.12 |

## 生成耗时

| 阶段 | 耗时 |
|------|------|
| API 调用 | ~1s |
| 任务轮询 | 5-15s |
| 图片下载 | ~1s |
| **总计** | **~8-17s/张** |

## Prompt 工程建议

### 好的 Prompt 结构
```
[风格描述] + [主体/产品描述] + [构图/位置] + [色调/光影] + [质量要求]

例: "温暖关怀风格，暖橙渐变背景，柔和光晕效果。
     手掌托起一粒白色药丸，药丸内部显示温度曲线。
     标题在手掌上方，CTA在右下角。
     4K商业摄影质感，自然光影。"
```

### 避免
- "无文字" — AI 理解能力弱，尽量不依赖否定描述
- 抽象概念 — "高端感"、"品质感" 应替换为具体视觉元素
- 过长的英文 — 中文 prompt 效果更好

## API Key 获取

1. https://dashscope.aliyun.com/
2. 开通"模型服务灵积" → 通义万相
3. 获取 API Key
4. `export DASHSCOPE_API_KEY=sk-xxx`

## 已知限制

- 中文文字渲染不精确（可能模糊/乱码）
- 不支持 ControlNet / Inpainting
- 不支持 seed 固定（无法复现）
- 颜色精确度有限（品牌色仅粗略匹配）
- 免费额度有限，超出后按量付费
