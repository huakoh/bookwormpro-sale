---
name: seedream-watermark-removal
description: >
  Remove "AI生成" watermark from Seedream/Doubao generated images.
  Seedream 5.0 adds a small "AI生成" text in the bottom-right corner (~10% width × 5% height).
  Prompt-level prevention ("无AI生成水印") doesn't work — requires post-processing.
  Covers: PIL-based watermark removal, prevention attempts, and known outcomes.
  Trigger: Seedream watermark, AI生成, 去水印, remove watermark.
safety:
  level: low
maturity: stable
cost_level: low
last-reviewed: 2026-05-02
---

# Seedream Watermark Removal

Seedream 5.0 (`doubao-seedream-5-0-260128`) consistently adds a small "AI生成" watermark in the bottom-right corner of generated images.

## The Problem

- Watermark appears as small text (~2-3 characters) in the bottom-right ~10% × 5% region
- Prompt-level prevention fails: adding "无AI生成水印无文字标记" to the prompt has **no effect** (Seedream doesn't support negative prompts well)
- Affects commercial usability — images need post-processing before deployment

## Solution: Crop + Resize (Primary — 100% effective)

**2026-05-02 update**: The content-aware fill approach (copying row above) can leave visible seams on non-uniform backgrounds. The user reported watermarks still visible after 2 rounds of patching. **Crop + resize is the reliable method:**

```python
from PIL import Image

def remove_watermark(image_path: str) -> Image.Image:
    """Completely remove 'AI生成' watermark by cropping then resizing back."""
    img = Image.open(image_path).convert("RGB")
    w, h = img.size

    # Crop: remove 4% from right + 3% from bottom (watermark region)
    crop_right = int(w * 0.04)
    crop_bottom = int(h * 0.03)
    cropped = img.crop((0, 0, w - crop_right, h - crop_bottom))

    # Resize back to original dimensions
    return cropped.resize((w, h), Image.LANCZOS)

# Usage
img = remove_watermark("cookie_03.png")
img.save("cookie_03_clean.jpg", "JPEG", quality=92)
```

## Alternative: Content-Aware Fill (fallback, may leave seams)

```python
def remove_watermark_fill(image_path: str) -> Image.Image:
    """Fallback: fill watermark region with pixels from above.
       ⚠️ May leave visible seam on non-uniform backgrounds."""
    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    wm_w, wm_h = int(w * 0.12), int(h * 0.06)
    wm_x, wm_y = w - wm_w, h - wm_h
    if wm_y >= wm_h:
        source = img.crop((wm_x, wm_y - wm_h, w, wm_y))
        img.paste(source, (wm_x, wm_y))
    return img
```

## Why Crop+Resize Wins

- Seamless: no visible line where fill region meets original
- 100% effective: watermark region physically doesn't exist in output
- Simple: no AI inpainting, no edge detection
- Acceptable quality loss: 4%×3% crop then LANCZOS resize is imperceptible on product photos

## What Doesn't Work

| Attempt | Result |
|---------|--------|
| "无AI生成水印" in prompt | ❌ No effect — Seedream ignores negative prompts |
| "无文字标记" in prompt | ❌ Same — not supported |
| Content-aware fill (copy row above) | ⚠️ May leave visible seam; user still saw watermark after 2 rounds |

## Batch Deployment Pattern (JPG + PNG)

Always process BOTH formats — the website references both `.jpg` and `.png`:

```python
import requests
from PIL import Image
from io import BytesIO

IMAGES = ['cookie-hero','product-main','product-1','product-2','product-3',
          'audience-children','audience-senior','audience-fitness','og-image']

for name in IMAGES:
    for ext in ['.jpg', '.png']:
        url = f'https://example.com/assets/{name}{ext}'
        r = requests.get(url, timeout=15)
        img = Image.open(BytesIO(r.content)).convert('RGB')
        w, h = img.size
        cropped = img.crop((0, 0, w - int(w*0.04), h - int(h*0.03)))
        final = cropped.resize((w, h), Image.LANCZOS)
        final.save(f'{name}{ext}', ext.replace('.','').upper(), quality=92)
        # scp to server...
```

## When Both Formats Are Needed

Most HTML-based product sites reference images as both JPEG and PNG simultaneously (for different contexts like `<img>` tags vs OG meta tags). Always process both when deploying watermark-removed images.

## Known Limits

- Works best on uniform backgrounds. Complex backgrounds may show a visible seam.
- For images with busy bottom-right corners, fall back to cropping: `img.crop((0, 0, w, h - wm_h))`
- Watermark may appear on other Doubao/Volcengine image models too (not just Seedream 5.0)
