---
name: seedream-generation-review-workflow
description: >
  Seedream 5.0 图片生成 + doubao-vision 自动评审完整工作流。
  当用户需要用 Seedream/火山引擎生图并进行质量评审时使用。
  覆盖: ARK key 格式陷阱、critic_vision 复用、水印去除、
  prompt 优化（避免占位符/空白区域）、单 ARK key 双用途。
  触发词: Seedream生图、豆包生图、火山引擎生图、曲奇图、
  产品图生成、AI评审、图片精修。
safety:
  level: medium
  permissions: [read_file, write_file, terminal]
maturity: stable
cost_level: medium
last_updated: 2026-05-02
dependencies:
  - requests
  - Pillow
---

# Seedream 生图 + 评审工作流

> 基于 D-阿洛酮糖曲奇 7 图项目实战验证

## 关键发现

### 1. ARK Key 完整格式 (记忆截断陷阱)

```
❌ 记忆截断:  ark-XXXX                         (只有首段，导致 401)
✅ 完整 key:  ark-YOUR-KEY-HERE  (5段 UUID)
```

记忆工具可能截断长 key。**永远从 session 历史或 .env 获取完整 key**，
不要信任内存中的截断版本。

### 2. 单 ARK Key 双用途 (生成 + 评审共用)

同一 ARK key 同时支持:
- **Seedream 5.0 生图**: `POST /api/v3/images/generations` (model: `doubao-seedream-5-0-260128`)
- **doubao vision 评审**: `POST /api/v3/chat/completions` (model: `doubao-seed-1-6-vision-250815`)

评审模块已存在于 `ad-creative-pipeline/shared/critic_vision.py`:
```python
from critic_vision import critique_image, batch_critique
# 一枪四维评审: contrast/composition/aesthetics/commercial
# 每次调用一个 API request，返回 {overall_score, pass, issues, ...}
```

### 3. Seedream 水印问题 (无法通过 prompt 消除)

Seedream 在部分图片右下角添加 "AI生成" 小字水印。
**在 prompt 中添加 "无AI生成水印" 无效**（Seedream 不支持 negative prompt）。

**PIL 水印去除方案** (已验证):
```python
def remove_watermark(img_path):
    img = Image.open(img_path).convert("RGB")
    w, h = img.size
    wm_w = int(w * 0.10)   # 水印约占右下角 10% 宽度
    wm_h = int(h * 0.05)   # 水印约占 5% 高度
    wm_x, wm_y = w - wm_w, h - wm_h
    # 用水印上方像素覆盖
    source = img.crop((wm_x, wm_y - wm_h, w, wm_y))
    img.paste(source, (wm_x, wm_y))
    return img
```

### 4. Prompt 工程: 避免"占位符"描述

```
❌ "中央留方形空位，放置白色半透明隔板"  → AI 生成空白方块 (7.5分)
✅ "中央也是饼干无任何空位或间隔物"      → 自然填充 (7.8分)
```

描述"空位/占位符/隔板/ spacer"会被 Seedream 理解为实际物体并生成。
改为正面描述"紧密排列/完整填充/无空位"。

## 完整工作流

```
Step 1: 分析参照图 (vision model / Qwen-VL)
   ↓
Step 2: 设计 Prompt (≤800 chars, 中文, 去占位符描述)
   ↓
Step 3: Seedream 批量生成 (串行, 间隔 2s, 3次重试)
   ↓
Step 4: critic_vision 四维评审 (contrast/composition/aesthetics/commercial)
   ├── ≥6.0: 通过
   ├── 4.0-6.0: PIL auto_refine (对比度/亮度/锐化)
   └── <4.0: 重生成
   ↓
Step 5: 水印去除 + 多尺寸导出
```

## Seedream API 速查

```python
POST https://ark.cn-beijing.volces.com/api/v3/images/generations
Authorization: Bearer ark-xxx-xxx-xxx-xxx-xxx
Body: {
  "model": "doubao-seedream-5-0-260128",
  "prompt": "中文描述, ≤800 chars",
  "n": 1,
  "size": "1920x1920",          # 最低 3,686,400 px
  "response_format": "b64_json"  # 或 "url"
}
# 返回: {"data":[{"b64_json":"..."}]}
# 耗时: 20-35s/张
# 成本: ~¥0.02/张
```

## doubao Vision 评审速查

```python
POST https://ark.cn-beijing.volces.com/api/v3/chat/completions
Authorization: Bearer {SAME_ARK_KEY}
Body: {
  "model": "doubao-seed-1-6-vision-250815",
  "messages": [{"role":"user","content":[
    {"type":"image_url","image_url":{"url":"data:image/png;base64,..."}},
    {"type":"text","text":"评估这张图0-10分: contrast/composition/aesthetics/commercial"}
  ]}],
  "max_tokens": 500
}
# 耗时: 15-25s/张
# 成本: 含在 ARK 额度内
```

## 多尺寸导出规格

| 用途 | 尺寸 | 格式 |
|------|------|------|
| 电商主图 | 1200×1200 | JPEG 92% |
| 淘宝天猫 | 800×800 | JPEG 92% |
| Instagram | 1080×1080 | JPEG 92% |
| 微信朋友圈 | 1080×1080 | JPEG 92% |
| 缩略图 | 400×400 | JPEG 92% |
| 原图 | 1920×1920 | PNG |

## 已知限制

- Seedream "AI生成"水印无法通过 prompt 消除 → PIL 后处理
- Seedream 不支持 negative prompt → 用正面描述替代否定
- ARK key 在记忆系统中可能截断 → 从 session/.env 获取
- doubao vision 单次调用 ~15s，批量 7 图约 150s
- critic_vision.py 一次调用的 token 消耗约等同于一次 Seedream 生成

## 实战数据 (D-阿洛酮糖曲奇)

| 指标 | 数值 |
|------|------|
| 7图生成 | 205s, ¥0.14 |
| 7图评审 | 152s |
| 多尺寸导出 | 42 文件, 6.7MB |
| 水印修复 | 3 张 |
| 重生成优化 | 1 张 |
| 总分范围 | 7.5-9.0/10 |

## 形状参照对比 (双图 vision 评审)

当需要确保生成的图片与参照款在形状/款式上一致时:

```python
# 双图对比: 参照图 + 目标图 → doubao vision 评估形状相似度
question = """对比两张食品产品图中的曲奇/饼干形状:
- 参考图是花型圆形曲奇，有8-10瓣放射状星形花边纹路
- 目标图的曲奇形状是否与参考图一致？（圆形且有花瓣纹路？）
- 给形状相似度0-10分
返回纯JSON: {"shape_match":分, "notes":"简评"}"""

# 请求中放入两张图
messages=[{"role":"user","content":[
    {"type":"image_url","image_url":{"url":"data:image/png;base64,{ref_b64}"}},
    {"type":"image_url","image_url":{"url":"data:image/png;base64,{target_b64}"}},
    {"type":"text","text":question}
]}]
```

实战: 以 cookie_03 花型圆曲奇为参照，其余 6 图对比得到 0-9 分，
圆花型款式 (04:9分, 07:8分) 与方曲奇款式 (01/02/05/06:0-2分) 自动区分。
