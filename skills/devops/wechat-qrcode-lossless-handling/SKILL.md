---
name: wechat-qrcode-lossless-handling
description: >
  Handle WeChat/WeCom QR code images without breaking scanability.
  When users need to crop, resize, or embed WeChat/WeCom QR codes
  from cards or screenshots into websites. Trigger: 二维码、扫码、
  QR code、企业微信、WeCom、微信二维码、裁剪二维码。
maturity: stable
cost_level: low
---

# WeChat/WeCom QR Code Lossless Handling

## Golden Rule

**NEVER process WeChat/WeCom QR codes through PIL/Pillow or ImageMagick.**

These QR codes contain embedded avatars and use high-density encoding.
Any pixel change from re-encoding (even JPEG→PNG conversion) can break
scanability. The embedded avatar reduces error-correction headroom.

## When to Process vs Not

| Action | OK? | Notes |
|--------|-----|-------|
| Use original file as-is | ✅ | Always works |
| Lossless JPEG crop (jpegtran) | ✅ | No re-encoding |
| PIL crop + save as PNG | ❌ | Pixel changes break QR |
| PIL resize (any filter) | ❌ | Interpolation kills data |
| ImageMagick convert | ❌ | Always re-encodes |
| CSS display resize only | ✅ | Browser scaling is fine |

## How to Use a WeCom QR Code

```bash
# 1. Upload original file directly - NO PROCESSING
scp "original-wecom-card.jpg" server:/path/to/assets/wecom-qr.jpg

# 2. Display with CSS sizing only
<img src="wecom-qr.jpg" style="max-width:200px; height:auto;">
```

## If Cropping is Mandatory

Use `jpegtran` for lossless crop (only if JPEG source):
```bash
jpegtran -crop WxH+X+Y -outfile cropped.jpg original.jpg
```

## Failed Approaches (Don't Repeat)

- ❌ PIL `.crop()` + `.save('PNG')` → breaks QR (pixel shift from JPEG decode path)
- ❌ PIL `.resize(600,600, LANCZOS)` → smooths QR edges, kills scan
- ❌ PIL `.resize(600,600, NEAREST)` → slightly better, still breaks
- ❌ `convert -resize` with ImageMagick → always re-encodes
- ❌ Any format conversion (JPG→PNG, PNG→JPG) → guaranteed break
- ❌ Brute-force parameter search for crop + PIL save → crop visually perfect but QR unreadable

**Real case (2026-05-01)**: WeCom card 1320×2868, 6 PIL crop attempts — all four corners white, visually flawless. None scannable. Final fix: used original JPEG directly with CSS sizing only. 420×420 crop found via brute-force at y_shift=-30 — still broken by PIL decode→encode pipeline.

## Key Insight

WeCom QR codes embed a 30-40% avatar in the center. This uses up most
of the error correction capacity (Level H ≈ 30%). Any additional pixel
changes push beyond recoverable limits. Original file = only safe approach.
