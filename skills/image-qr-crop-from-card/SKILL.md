---
name: image-qr-crop-from-card
description: >
  从名片/卡片类图片中精确裁剪二维码。当用户需要从企业微信名片、宣传卡片、
  或其他带彩色背景的卡片中提取纯二维码图片时使用。触发词：裁剪二维码、
  提取QR码、企业微信码裁剪、卡片码提取。
allowed-tools: Read, Write, Bash, Grep
maturity: stable
cost_level: medium
---

# 从卡片中精确裁剪二维码

## ⚠️ 致命警告：WeCom/微信二维码不可经 PIL 处理

**此技能仅适用于普通二维码的视觉裁剪。如果是企业微信/微信二维码——立即停止，加载 `wechat-qrcode-lossless-handling` 技能。**

原因：WeCom 二维码中心嵌入 30-40% 头像，已用尽纠错余量。PIL 的任何处理（crop+save、format conversion、resize）都会改变像素值，导致扫码永久失效。唯一安全方案：使用原始文件，通过 CSS 控制显示尺寸。

## 触发条件

- 用户提供带彩色背景的名片/卡片图片，需要提取其中的二维码
- 二维码周围有蓝色/深色卡片背景
- 需要纯白底、无边角料残留的干净二维码
- **仅适用于不要求可扫码的展示用二维码，或非 WeCom 的普通 QR 码**

## 方法：暴力参数搜索 + 四角验证

直接按比例裁剪不可靠——蓝边极易残留。正确流程：

### Step 1: 上传原图到服务器

```bash
scp "源文件路径" root@服务器:/tmp/qr-raw.jpg
```

### Step 2: 暴力搜索最佳裁剪参数

```python
from PIL import Image
img = Image.open('/tmp/qr-raw.jpg')
w, h = img.size
cx = w // 2
base_cy = int(h * 0.39)  # 二维码通常在卡片上 39% 处

found = False
for size in [400, 420, 380, 360, 340]:  # 从大到小试
    for y_shift in [0, -10, -20, 10, -30, -40]:  # 微调垂直位置
        cy = base_cy + y_shift
        left = cx - size // 2
        top = cy - size // 2

        cropped = img.crop((left, top, left + size, top + size))
        gray = cropped.convert('L')
        px = gray.load()

        # 关键：四角必须是白色 (>200)，否则有蓝边残留
        corners_ok = all(
            px[x, y] > 200
            for x, y in [(2, 2), (size - 3, 2), (2, size - 3), (size - 3, size - 3)]
        )

        if corners_ok:
            cropped.save('output.png', 'PNG')
            print(f'✓ size={size}, y_shift={y_shift}')
            found = True
            break
    if found:
        break
```

### Step 3: 验证裁剪结果

下载裁剪图到本地，用 vision_analyze 确认：
- 背景纯白
- 无蓝色边框
- 无文字
- 四角定位图案完整

### Step 4: 部署

```bash
# PNG 格式保证二维码清晰度
cp output.png /网站目录/assets/images/qr-code.png
```

## 常见陷阱

| 陷阱 | 症状 | 解决 |
|------|------|------|
| 比例估算裁剪 | 蓝边残留 | 改用四角像素检测 |
| 从中心扫描白区 | 掉入嵌入头像 | 改用暴力参数搜索 |
| 用 JPG 格式 | 二维码模糊 | 必须用 PNG 保证清晰度 |
| size 太小 | 切掉定位角 | 从 420 开始递减 |
| y_shift 不对 | 上下蓝边 | 尝试 -40 到 +10 |

## 为什么不用其他方法

- **OpenCV 轮廓检测**: 嵌入头像干扰轮廓
- **边缘检测**: 卡片装饰框干扰
- **比例估算**: 不可靠，易残留
- **手动裁剪**: 慢且不可重复

暴力搜索虽然"笨"，但最可靠——只要四角是白色（>200），就一定没有蓝边。
