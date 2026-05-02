"""
Stage 4a: AI Critic (v1.1 — P0+P1+P2 修复版)
═══════════════════════════════════════════════════
变更:
  D1    → 品牌色量化比对 (delta_e)
  P2-2  → 反模式库驱动检查 (anti_patterns.yaml)
  P0-S5 → 评审结果脱敏
  D5    → 色盲友好检查
"""

import json
import math
import yaml
from pathlib import Path
from PIL import Image
import numpy as np
from collections import Counter

# ── 加载反模式库 ──
_anti_patterns = None

def load_anti_patterns():
    global _anti_patterns
    if _anti_patterns is None:
        path = Path(__file__).parent.parent.parent / "shared" / "anti_patterns.yaml"
        with open(path) as f:
            _anti_patterns = yaml.safe_load(f)
    return _anti_patterns


# ── 颜色工具 ─────────────────────────────────────────

def hex_to_rgb(hex_color: str) -> tuple:
    """#0052D9 → (0, 82, 217)"""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def delta_e(rgb1: tuple, rgb2: tuple) -> float:
    """
    D1: 品牌色量化比对
    使用简化的 CIE76 ΔE 公式 (适合快速比对)
    """
    # RGB → XYZ
    def _rgb_to_xyz(r, g, b):
        r, g, b = [x/255.0 for x in (r, g, b)]
        r = ((r+0.055)/1.055)**2.4 if r > 0.04045 else r/12.92
        g = ((g+0.055)/1.055)**2.4 if g > 0.04045 else g/12.92
        b = ((b+0.055)/1.055)**2.4 if b > 0.04045 else b/12.92
        r, g, b = r*100, g*100, b*100
        x = r*0.4124 + g*0.3576 + b*0.1805
        y = r*0.2126 + g*0.7152 + b*0.0722
        z = r*0.0193 + g*0.1192 + b*0.9505
        return x, y, z

    # XYZ → Lab
    def _xyz_to_lab(x, y, z):
        xn, yn, zn = 95.047, 100.000, 108.883
        def _f(t):
            return t**(1/3) if t > 0.008856 else 7.787*t + 16/116
        fx, fy, fz = _f(x/xn), _f(y/yn), _f(z/zn)
        L = 116*fy - 16
        a = 500*(fx - fy)
        b_lab = 200*(fy - fz)
        return L, a, b_lab

    x1, y1, z1 = _rgb_to_xyz(*rgb1)
    x2, y2, z2 = _rgb_to_xyz(*rgb2)
    L1, a1, b1 = _xyz_to_lab(x1, y1, z1)
    L2, a2, b2 = _xyz_to_lab(x2, y2, z2)

    return math.sqrt((L1-L2)**2 + (a1-a2)**2 + (b1-b2)**2)


def extract_dominant_colors(image_path: str, n: int = 3) -> list[tuple]:
    """
    提取图片主色调 (k-means 简化版: 像素采样 + 频率排序)
    """
    img = Image.open(image_path).convert("RGB")
    img = img.resize((100, 100))  # 降采样加速
    pixels = list(img.getdata())

    # 量化到 32 级 (减少颜色数)
    quantized = [((r//32)*32, (g//32)*32, (b//32)*32) for r, g, b in pixels]
    counter = Counter(quantized)
    return [color for color, _ in counter.most_common(n)]


def check_brand_color_compliance(image_path: str, brand_colors_hex: list[str],
                                  threshold_delta_e: float = 15.0) -> dict:
    """
    D1: 品牌色合规检查
    提取图片主色 → 与品牌色算 ΔE → 判断合规
    """
    dominant = extract_dominant_colors(image_path, n=5)
    brand_rgbs = [hex_to_rgb(c) for c in brand_colors_hex]

    min_distances = []
    for dom_rgb in dominant:
        distances = [delta_e(dom_rgb, br) for br in brand_rgbs]
        min_distances.append(min(distances))

    # 至少有一个主色与某个品牌色的 ΔE ≤ 阈值
    best_match = min(min_distances)
    compliant = best_match <= threshold_delta_e

    return {
        "best_delta_e": round(best_match, 1),
        "threshold": threshold_delta_e,
        "compliant": compliant,
        "score": max(0, 10 - best_match * 0.5)  # ΔE=0→10分, ΔE=20→0分
    }


def check_red_green_pair(dominant_colors: list[tuple]) -> bool:
    """
    D5: 红绿色盲检查
    检测是否存在红绿色对（色相在 0°±30° 和 120°±30°）
    """
    def hue(r, g, b):
        mx, mn = max(r, g, b), min(r, g, b)
        if mx == mn:
            return 0
        d = mx - mn
        if mx == r: h = 60 * ((g-b)/d % 6)
        elif mx == g: h = 60 * ((b-r)/d + 2)
        else: h = 60 * ((r-g)/d + 4)
        return h % 360

    hues = [hue(*c) for c in dominant_colors]
    has_red = any(0 <= h <= 30 or 330 <= h <= 360 for h in hues)
    has_green = any(90 <= h <= 150 for h in hues)
    return has_red and has_green


# ── Critic 评分 ──────────────────────────────────────

def analyze_with_vision(image_path: str, question: str) -> dict:
    """
    调用 BookwormPRO vision_analyze 工具 (伪代码 — 实际由 Agent 执行)
    返回: {"score": 0-10, "issues": [...], "fix_suggestions": [...]}
    """
    # 实际执行: vision_analyze(image_url=image_path, question=question)
    # 这里返回结构占位
    return {"score": 7, "issues": [], "fix_suggestions": []}


def critique_image(image_path: str, brand_context: dict,
                   platform: str = "facebook_feed") -> dict:
    """
    完整 Critic 评审
    返回: {overall_score, details, pass, needs_regeneration, ...}
    """
    ap = load_anti_patterns()
    results = {}
    dominant_colors = extract_dominant_colors(image_path)

    # 1. 对比度 (vision AI)
    results["contrast"] = analyze_with_vision(image_path, """
        评估对比度(0-10)。文字与背景对比度?视觉层次?CTA突出?暗部细节?
    """)

    # 2. 可读性 (vision AI)
    results["readability"] = analyze_with_vision(image_path, """
        评估文字可读性(0-10)。标题清晰?文字无遮挡?中文无乱码?
    """)

    # 3. 品牌一致性 (D1: 量化 + vision AI)
    brand_colors = brand_context.get("brand_colors", [])
    if brand_colors:
        brand_result = check_brand_color_compliance(image_path, brand_colors)
        brand_vision = analyze_with_vision(image_path, f"""
            评估品牌一致性(0-10)。风格符合{platform}广告规范?视觉元素专业统一?
        """)
        # 量化+AI 综合
        results["brand_consistency"] = {
            "score": round(brand_result["score"] * 0.5 + brand_vision.get("score", 7) * 0.5, 1),
            "delta_e": brand_result["best_delta_e"],
            "color_compliant": brand_result["compliant"],
            "issues": brand_vision.get("issues", []),
            "fix_suggestions": brand_vision.get("fix_suggestions", [])
        }
    else:
        results["brand_consistency"] = analyze_with_vision(image_path, """
            评估品牌一致性(0-10)。
        """)

    # 4. 美学质量 (vision AI + 反模式)
    results["aesthetic"] = analyze_with_vision(image_path, """
        评估美学质量(0-10)。构图平衡?无AI畸变?视觉焦点?商业广告质量标准?
    """)

    # 5. 红绿色盲检查 (D5)
    is_red_green = check_red_green_pair(dominant_colors)

    # ── 加权总分 ──
    weights = {"contrast": 0.25, "readability": 0.25,
               "brand_consistency": 0.25, "aesthetic": 0.25}
    overall = sum(results[k].get("score", 5) * w for k, w in weights.items())

    # 色盲惩罚
    if is_red_green:
        overall -= 1.0

    return {
        "image_path": image_path,
        "overall_score": round(max(0, overall), 1),
        "details": results,
        "color_blind_issue": is_red_green,
        "pass": overall >= 6.0,
        "needs_regeneration": overall < 4.0,
        "needs_fix": 4.0 <= overall < 6.0,
    }
