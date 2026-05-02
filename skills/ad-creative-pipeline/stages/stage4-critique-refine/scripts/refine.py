"""
Stage 4b: Auto Refine (v1.1 — P0+P1+P2 修复版)
═══════════════════════════════════════════════════
PIL 基础修复: 对比度/亮度/锐化 + 低分标记重生成
"""

from PIL import Image, ImageFilter, ImageEnhance


def auto_refine(image_path: str, critic_result: dict, output_path: str) -> dict:
    """
    根据 Critic 评审结果自动修复
    """
    img = Image.open(image_path).convert("RGB")
    fixes_applied = []
    details = critic_result.get("details", {})

    # 1. 对比度修复
    contrast_detail = details.get("contrast", {})
    if contrast_detail.get("score", 10) < 6:
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.25)
        fixes_applied.append("contrast_enhance_1.25x")

    # 2. 亮度修复
    if contrast_detail.get("score", 10) < 5:
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(1.1)
        fixes_applied.append("brightness_enhance_1.1x")

    # 3. 锐化
    aesthetic_detail = details.get("aesthetic", {})
    if aesthetic_detail.get("score", 10) < 6:
        img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=80, threshold=3))
        fixes_applied.append("unsharp_mask")

    # 4. 色彩饱和度
    if aesthetic_detail.get("score", 10) < 5:
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(1.05)
        fixes_applied.append("saturation_enhance_1.05x")

    # 5. 低分标记
    if critic_result.get("overall_score", 10) < 4.0:
        fixes_applied.append("SCORE_TOO_LOW_RECOMMEND_REGENERATE")

    img.save(output_path, "PNG", quality=95)

    return {
        "original_path": image_path,
        "fixed_path": output_path,
        "fixes_applied": fixes_applied
    }
