---
name: bookwormpro-add-image-gen-provider
description: >
  为 BookwormPRO 新增图片生成提供商。覆盖 DashScope/Seedream/Gemini/gpt-image-2 四种 API 的
  接入流程、模型名、尺寸限制、返回格式差异、常见坑。触发词：接入生图API、
  新增image provider、Seedream、DashScope图片、Gemini生图、豆包生图。
category: devops
maturity: stable
cost_level: medium
last_updated: 2026-05-02
---

# BookwormPRO 图片生成 Provider 接入指南

## 四种 Provider 对比

| | Seedream 5.0 | DashScope | Gemini 2.5 Flash | gpt-image-2 |
|---|---|---|---|---|
| **厂商** | 字节/火山引擎 | 阿里云 | Google | OpenAI |
| **端点** | `ark.cn-beijing.volces.com/api/v3/images/generations` | SDK (`ImageSynthesis`) | `generativelanguage.googleapis.com/v1beta` | 中转站 `/v1/images/generations` |
| **格式** | OpenAI 兼容 (Bearer) | 异步 task → `url` | `generateContent` + `responseModalities` | OpenAI 兼容 |
| **模型名** | `doubao-seedream-5-0-260128` | `qwen-image-plus` | `gemini-2.5-flash-image` | `gpt-image-2` |
| **返回** | `b64_json` 或 `url` | `.url` (OSS签名URL) | `inlineData.data` (base64) | `b64_json` 或 `url` |
| **最小尺寸** | **3,686,400 像素** (≥1920×1920) | 无限制 | 无限制 | 无限制 |
| **并发** | 3 | **1** (>1触发429) | 免费tier: 1 | 3 (但中转站持续429) |
| **成本** | ¥0.02/张 | ¥0.04/张 | 免费tier用完需外币卡 | ~¥0.15/张 |
| **支付** | 国内企业认证 | 支付宝 | 外币卡 | 中转站支持支付宝 |
| **状态** | ✅ 推荐 | ✅ 可用 | ❌ 配额耗尽 | ❌ 中转站限流 |

## 接入 Seedream (火山引擎 ARK) — 推荐

### 获取 Key
https://console.volcengine.com/ark → API Key 管理
格式: `ark-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx-xxxxx`

### 模型列表
`GET https://ark.cn-beijing.volces.com/api/v3/models`
图片模型: `doubao-seedream-5-0-260128`, `doubao-seedream-4-5-251128`, `doubao-seedream-4-0-250828`

### 生成
```python
POST https://ark.cn-beijing.volces.com/api/v3/images/generations
{"model": "doubao-seedream-5-0-260128", "prompt": "...", "n": 1, "size": "1920x1920"}
# ⚠️ size 最低 3,686,400 像素! 推荐 1920x1920
```

## 接入 DashScope (阿里云)

```python
from dashscope import ImageSynthesis
response = ImageSynthesis.call(model="qwen-image-plus", prompt=prompt[:800], n=1, size="1024*1024")
# 异步轮询 → result.output.results[0].url  ← url非b64_json!
# ⚠️ 并发>1触发429, 800字符硬限制, 内容审核严格
```

## 接入 Gemini 2.5 Flash Image

```python
POST .../models/gemini-2.5-flash-image:generateContent?key={KEY}
{"contents":[{"parts":[{"text":"..."}]}],"generationConfig":{"responseModalities":["IMAGE","TEXT"]}}
# 结果: candidates[0].content.parts[].inlineData.data (base64)
# ⚠️ 不是 -preview (已废弃Jan 2026), 免费tier用完需外币卡
```

## Provider 回退链

```python
fallback_map = {"seedream": "dashscope", "dashscope": "seedream", "gpt-image-2": "seedream"}
```

## Windows 环境变量

```powershell
$env:SEEDREAM_API_KEY="ark-xxx"    # PowerShell
$env:DASHSCOPE_API_KEY="sk-xxx"
# 持久化: ~/.bookwormpro/.env
```

## 实战坑

1. **Seedream 最低像素 3,686,400 — 1920×1920 是唯一安全尺寸** ⚠️
   1920×1920=3,686,400 刚好踩线。任何其他尺寸(如1920×1008=1,935,360)直接 400 报错。
   **非正方形格式 workaround**: 先生成 1920×1920，再用 PIL `img.crop()` 裁切到目标尺寸。
   ```python
   img = Image.open("generated_1920x1920.png")
   target_h = 1008
   top = (1920 - target_h) // 2
   img = img.crop((0, top, 1920, top + target_h))  # → 1920x1008
   ```

2. **AI水印无法通过prompt消除 — 必须PIL后处理** ⚠️
   即使prompt写"无AI生成水印无文字标记"，Seedream 仍可能在右下角生成微小"AI生成"文字。
   **解决方案**: 内容感知填充——取水印上方同尺寸区域像素覆盖。
   ```python
   wm_w, wm_h = int(w*0.10), int(h*0.05)  # 水印约占右下角10%宽×5%高
   wm_x, wm_y = w - wm_w, h - wm_h
   source = img.crop((wm_x, wm_y - wm_h, w, wm_y))
   img.paste(source, (wm_x, wm_y))
   ```

3. **ARK Key 格式: 5段UUID，共50+字符** ⚠️
   格式: `ark-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx-xxxxx`
   记忆可能截断(如只存首段`ark-a7d4c36a`)。如遇 401 `AuthenticationError: The API key format is incorrect`，
   从 session 历史恢复完整 key: `session_search("SEEDREAM_API_KEY")`，在 `request_dump` 中查找。

4. DashScope 返回**url**非b64_json — `result.output.results[0].url` (OSS签名URL,需requests下载)
5. DashScope 800字符硬截断 — 超长直接拒绝,需`prompt[:800]`
6. bww.your-domain.com 中转站 gpt-image-2 持续429不可用 — 上游负载饱和,已废弃
7. DashScope 内容审核: "药品"、"GSP认证"等医疗词汇触发 `ContentFilteredError` — 需 sanitize prompt。食品类无此问题
8. Seedream 模型名: `doubao-seedream-5-0-260128` (非 lite, 非 -preview)
7. Google Gemini 免费 tier `limit: 0` 需外币卡升级,模型名 `gemini-2.5-flash-image` (非 `-preview`,Jan 2026已废弃)
8. **Seedream AI水印去除**: 生成图片右下角常有"AI生成"微小水印。像素填充法(取水印上方区域覆盖)不够彻底；推荐物理裁切法: 裁掉右4%×下3%再resize回原尺寸，彻底消除
9. **非标准尺寸生成**: 如需要16:9横幅(1920×1008)但低于368万像素限制→先生成1920²再居中裁剪
10. **ARK Key格式**: 完整key为 `ark-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx-xxxxx` 5段UUID格式, 记忆/存储时易被截断仅存首段
10. **部署同步验证**: 本地更新后 `scp` 到服务器，用 `requests.head(server_url)` 检查 `Last-Modified` / `Content-Length` 确认同步。Windows 路径需用 Python subprocess 逐文件 scp，不支持 glob 通配符。
11. **单 ARK Key 双用途**: 同一 key 同时支持生图 (`doubao-seedream-5-0-260128` at `/api/v3/images/generations`) 和视觉评审 (`doubao-seed-1-6-vision-250815` at `/api/v3/chat/completions`)。已有封装: `ad-creative-pipeline/shared/critic_vision.py` 提供 `critique_image()` 和 `batch_critique()`，四维评分每张≈15s。
12. **Prompt 占位符陷阱**: 描述 "空位/占位符/隔板/spacer" 会被 Seedream 理解为实际物体生成。修复: 正面描述 "紧密排列/完整填充/无空位/无间隔物"。
