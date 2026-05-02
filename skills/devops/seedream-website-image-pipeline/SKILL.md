---
name: seedream-website-image-pipeline
description: >
  Seedream 5.0 生图→去水印→评审→导出→部署 的完整工作流。
  覆盖图片产品站全站图生成，适用于需要批量生成AI产品图并部署到 Nginx 服务器的场景。
  触发词：Seedream生图、曲奇图、产品图生成、AI产品照、全站图部署。
category: devops
maturity: stable
cost_level: medium
last_updated: 2026-05-02
---

# Seedream Website Image Pipeline

Seedream 5.0 生图到网站部署的完整五阶段流水线。

## 阶段总览

```
Prompt设计 → Seedream生成 → Vision评审 → 导出+去水印 → SCP部署
```

| 阶段 | 工具 | 耗时/图 | 成本/图 |
|------|------|---------|---------|
| 1. Prompt | LLM + 中文描述 | <5s | 0 |
| 2. 生成 | Seedream 5.0 (ARK) | 20-35s | ¥0.02 |
| 3. 评审 | doubao-seed-1-6-vision | 15-25s | ~¥0.01 |
| 4. 导出 | PIL resize/crop | <1s | 0 |
| 5. 部署 | SCP to Nginx | <3s | 0 |

## 阶段 1：Prompt 设计

### Seedream 5.0 调用

```python
POST https://ark.cn-beijing.volces.com/api/v3/images/generations
Authorization: Bearer {ARK_KEY}
{
  "model": "doubao-seedream-5-0-260128",
  "prompt": "中文描述...",
  "n": 1,
  "size": "1920x1920",       // 最低 3,686,400 像素
  "response_format": "b64_json"
}
```

### 关键限制

- **最低像素**: 3,686,400 (1920×1920 正好达标)
- **并发**: 1，超过触发 429；间隔 2-3s
- **模型名**: `doubao-seedream-5-0-260128` (非 lite/非 preview)
- **API Key 格式**: `ark-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx-xxxxx` (5段)
- **不支持**: negative_prompt, seed 固定, 精确颜色
- **费用**: ~¥0.02/张

### Prompt 最佳实践

```
[风格] + [主体描述] + [构图/角度] + [色调/光影] + [质量要求]

例: "高端商业食品摄影，正上方俯拍。圆形铁盒内整齐排列16块方形黄油曲奇饼干，
呈放射状花瓣布局。每块饼干约3厘米见方...柔和顶光照明，边缘高光，
阴影柔和。4K商业摄影质感，真实光影，自然质感。"
```

- 中文 prompt 效果更好
- 保留 800 字符以内
- 避免否定描述："无文字" → "无AI生成水印无文字标记"（效果有限）
- 食品类无内容审核拦截（不同于医疗类）

## 阶段 2：Vision 自动评审

使用同一 ARK key 调用豆包视觉模型：

```python
POST https://ark.cn-beijing.volces.com/api/v3/chat/completions
Authorization: Bearer {ARK_KEY}  # 与 Seedream 共用
{
  "model": "doubao-seed-1-6-vision-250815",
  "messages": [{"role": "user", "content": [
    {"type": "image_url", "image_url": {"url": "data:image/png;base64,{b64}"}},
    {"type": "text", "text": "评估这张广告/产品图，0-10分..."}
  ]}],
  "max_tokens": 500
}
```

四维评分: contrast(对比度) / composition(构图) / aesthetics(美学) / commercial(商业可用性)

- ≥6.0 → 通过
- 4.0-6.0 → 需 PIL 修复（对比度/亮度/锐化/饱和度）
- <4.0 → 需重新生成（修改 prompt 重跑）

## 阶段 3：水印去除

Seedream 图片右下角有 "AI生成" 微小水印。

**方法 1：像素覆盖**（不彻底）
```python
# 取水印上方区域覆盖
wm_w, wm_h = int(w * 0.12), int(h * 0.06)
source = img.crop((wm_x, wm_y - wm_h, w, wm_y))
img.paste(source, (wm_x, wm_y))
```

**方法 2：物理裁切**（推荐，彻底）
```python
# 裁掉右下角 4%宽 × 3%高，再缩回原尺寸
crop_right = int(w * 0.04)
crop_bottom = int(h * 0.03)
img = img.crop((0, 0, w - crop_right, h - crop_bottom))
img = img.resize((w, h), Image.LANCZOS)
```

> 方法2 更可靠，裁掉后拉伸填补，人眼不可感知

## 阶段 4：多尺寸导出

电商/社交媒体常用尺寸：

```python
SIZES = {
    "电商主图": (1200, 1200),
    "淘宝天猫": (800, 800),
    "Instagram": (1080, 1080),
    "微信朋友圈": (1080, 1080),
    "缩略图": (400, 400),
    "原图": (1920, 1920),
}
```

- 先居中裁切为正方形
- 再 LANCZOS 缩放到目标尺寸
- JPG quality=92 兼顾品质和文件大小
- 同时输出 PNG（母版）+ JPG（网站用）

## 阶段 5：部署到 Nginx

```bash
# 从 Windows 本地 SCP 到服务器
scp local.jpg root@{server_ip}:/var/www/{site}/assets/{name}.jpg

# 验证
curl -sI https://{domain}/assets/{name}.jpg | grep Last-Modified
```

### 部署后清缓存

- 浏览器: Ctrl+Shift+R
- Nginx: 默认无缓存（静态文件按 Last-Modified 协商）
- 无需重启 Nginx

## 字体策略（中国环境）

**推荐：系统字体栈**
```css
font-family: 'PingFang SC', 'Microsoft YaHei', 'Hiragino Sans GB', sans-serif;
```

- PingFang SC: Mac/iOS 默认中文字体
- Microsoft YaHei: Windows 默认中文字体
- 优势: 0 下载、100% 覆盖、秒加载、免费商用
- 避免: Google Fonts CDN（国内不稳定）、阿里巴巴普惠体（TTF 8MB/个太大）

## 常见坑

1. **OG 图尺寸**: Seedream 最低 1920²，需要 1920×1008 时先生成 1920² 再裁切
2. **CRLF 陷阱**: Windows 下 `patch` 工具报 "verification failed" 但实际已写入——用 `py_compile` 验证
3. **Screenshot URL 编码**: 中文路径 SCP 需用 Python Path 处理，不可直接 shell 传
4. **并发限制**: Seedream 严格串行，每张间隔 ≥2s
5. **内容审核**: 食品类无拦截，医疗词汇（"药品"+"GSP"）会触发

## 成本估算

| 项目 | 单价 | 备注 |
|------|------|------|
| Seedream 生图 | ¥0.02/张 | 1920×1920 |
| Vision 评审 | ~¥0.01/张 | 四维评分一次调用 |
| PIL 处理 | 0 | 本地计算 |
| SCP 部署 | 0 | SSH 复用 |
| **7图全流程** | **~¥0.21** | 生成+评审各7次 |
