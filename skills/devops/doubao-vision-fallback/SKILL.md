---
name: doubao-vision-fallback
description: >
  When BookwormPRO's built-in vision_analyze tool returns 401, fall back to 
  doubao-seed-1-6-vision-250815 via direct ARK API call. Same ARK key as Seedream.
  Covers: screenshot analysis, image QA, watermark detection, layout auditing.
  Trigger: vision_analyze failed, 401 vision error, analyze screenshot, 
  视觉分析失败, doubao vision.
category: devops
maturity: stable
cost_level: low
last-reviewed: 2026-05-02
---

# Doubao Vision Fallback

When `vision_analyze` tool returns 401 (`User not found`), use the doubao vision model directly via ARK API. Shares the same authentication key as Seedream 5.0.

## When to Use

- `vision_analyze(image_url=...)` returns `401 - User not found`
- Need to analyze screenshots for layout auditing, watermark detection, design review
- Need to compare two images (e.g., shape matching against reference)

## Quick Start

```python
import base64, requests
from pathlib import Path

ARK_KEY = "ark-YOUR-KEY-HERE
VISION_MODEL = "doubao-seed-1-6-vision-250815"

def analyze_image(image_path, question):
    b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
    r = requests.post(
        "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        json={
            "model": VISION_MODEL,
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                {"type": "text", "text": question}
            ]}],
            "max_tokens": 500
        },
        headers={"Authorization": f"Bearer {ARK_KEY}", "Content-Type": "application/json"},
        timeout=30
    )
    return r.json()["choices"][0]["message"]["content"]
```

## Key Characteristics

| Feature | Value |
|---------|-------|
| Model | `doubao-seed-1-6-vision-250815` |
| Auth | Same ARK key as Seedream |
| Timeout | ~15-25s per call |
| Cost | ~¥0.01 per analysis |
| Max tokens | 500 (enough for structured feedback) |

## Use Cases

### 1. Screenshot Layout Audit
```
"详细描述这个网页的产品展示区/画廊布局：图片排列方式、大小比例、间距、整体视觉风格。"
```

### 2. Watermark Detection
```
"这张图片上能看到'AI生成'水印吗？水印在什么位置？"
```

### 3. Image Comparison (Shape Match)
Send TWO images + question. Use two `image_url` blocks in the content array:
```python
"messages": [{"role": "user", "content": [
    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{ref_b64}"}},
    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
    {"type": "text", "text": "对比两张图的曲奇形状，给0-10分相似度"}
]}]
```

### 4. Stage 4 Product Review
```
"评估这张广告/产品图，0-10分:
1) contrast: 主体与背景层次、文字可读对比度
2) composition: 构图是否平衡、视觉焦点是否清晰
3) aesthetics: 光线质感、色彩和谐度、AI畸变检测
4) commercial: 商业可用性、是否可直接用于官网
返回纯JSON: {\"contrast\":分,\"composition\":分,\"aesthetics\":分,\"commercial\":分,\"issues\":[\"问题1\"]}"
```

## Why Not Use Built-in vision_analyze

| Method | Status | Reason |
|--------|--------|--------|
| `vision_analyze(image_url=...)` | ❌ 401 | AUXILIARY_VISION_MODEL configured as `alibaba/qwen-vl-max` fails with "User not found" |
| Direct ARK doubao vision | ✅ Works | Same key as Seedream, same ARK platform |

## Important

- **Timeout**: Set `timeout=30` — images with high resolution may take longer
- **Rate limit**: Same ARK rate limits as Seedream — space calls by 1-2s
- **Chinese prompts**: Works well with Chinese questions
- **JSON parsing**: Model sometimes wraps JSON in ``` markers — strip before `json.loads()`
- **Image size**: Large 1920×1920 images work but take longer (>20s)

## Related Skills

- `seedream-website-image-pipeline` — uses this for Stage 3 review
- `seedream-watermark-removal` — vision helps detect remaining watermarks
