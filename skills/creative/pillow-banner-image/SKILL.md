---
name: pillow-banner-image
description: 用 Pillow 生成专业节日/活动横幅图片 — 红金/蓝系配色、2x超采样、CJK中文字体、渐变背景、4:3/16:9比例
version: 1.0.0
category: creative
---

# Pillow Banner Image Generator

用 Python Pillow 生成专业海报级横幅图片。核心技巧：2x 渲染 + LANCZOS 缩放消除锯齿；CJK 字体选择与宽度测量。

## 工作流程

### Step 1: 确定规格
- 常用比例: 4:3 (1600×1200), 16:9 (1920×1080)
- 始终 2x 渲染: SCALE=2, 最终 resize LANCZOS
- 配色方向: 红金(节日/庆典) 或 蓝系(科技/终端风格)

### Step 2: 字体选择

```python
FD = r"C:\Windows\Fonts"

# 中文首选 (支持 CJK + 等宽):
#   simsun.ttc    — 宋体, CJK 宽度 ≈ 1.6× ASCII, 可靠
#   simhei.ttf    — 黑体, 适合标题
#   msyh.ttc      — 微软雅黑, 现代感

# 英文等宽 (无 CJK):
#   consola.ttf   — Consolas, 终端风格

# 检测方法:
def F(name, sz, idx=0):
    p = os.path.join(FD, name)
    return ImageFont.truetype(p if os.path.exists(p) else name, sz, index=idx)
```

### Step 3: 渐变背景

```python
for y in range(H):
    r = y / H
    if r < 0.50:
        t = r / 0.50
        rr = int(TOP[0] + (MID[0]-TOP[0])*t)
        # ... same for gg, bb
    else:
        t = (r - 0.50) / 0.50
        rr = int(MID[0] + (BOT[0]-MID[0])*t)
    draw.line([(0, y), (W, y)], fill=(rr, gg, bb))
```

### Step 4: 中心光晕

```python
glow = Image.new("RGBA", (W, H), (0,0,0,0))
gd = ImageDraw.Draw(glow)
cx, cy = W//2, int(H*0.46)
for rd in range(max(W,H)//2, 80, -4):
    a = int(14 * (1 - rd/max(W,H))**1.6)
    if a <= 0: break
    gd.ellipse([cx-rd, cy-rd, cx+rd, cy+rd], fill=(255,215,0,a))
img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
```

### Step 5: 文字阴影效果

```python
# 描边阴影
for sx, sy in [(10,10),(6,6)]:
    draw.text((tx+sx, ty+sy), title, fill=DARK_SHD, font=font)
draw.text((tx, ty), title, fill=GOLD, font=font)
```

### Step 6: 最终缩放

```python
img = img.resize((W_TARGET, H_TARGET), Image.LANCZOS)
img.save("output.png", "PNG", quality=95)
```

## 关键踩坑

### CJK 字体 ≠ 等宽
SimSun 的 ASCII 宽度 ≈ 12px, CJK ≈ 19px (1.6×), 不是标准的 2×。
对于代码文字横幅, 需要逐字符测量宽度而非假设等宽。

```python
def line_width(line):
    w = 0
    for ch in line:
        if ord(ch) > 127:
            w += cjk_w
        else:
            w += ascii_w
    return w
```

### 纯拉丁字体不显示中文
Consolas / Courier New 等字体缺少 CJK 字形 → 中文变成 tofu (□)。
解决: 使用 SimSun / SimHei / Noto Sans SC

### Pillow patch 在 Windows 上常失败
文件锁 / CRLF 导致 patch 工具的 post-write verification 失败。
解决: 用 `python -c "..."` 字符串替换, 或直接重写整个文件。

### Playwright 需要预装浏览器
`playwright install` 下载 Chromium, 通常未预装。
备选: 直接用 Pillow (纯 Python, 零外部依赖)。

## 配色方案

### 红金 (节日/庆典)
```python
RED_DEEP  = (130, 10, 10)
RED_MID   = (175, 22, 22)
RED_DARK  = (18, 3, 3)
GOLD      = (255, 215, 0)
GOLD_LT   = (255, 240, 180)
GOLD_DIM  = (200, 160, 40)
WHITE     = (255, 252, 240)
```

### 蓝色 (科技/终端)
```python
BG        = (10, 15, 28)
FRAME     = (40, 116, 166)   # #2874A6
ACCENT    = (93, 173, 226)   # #5DADE2
BODY      = (214, 234, 248)  # #D6EAF8
```
