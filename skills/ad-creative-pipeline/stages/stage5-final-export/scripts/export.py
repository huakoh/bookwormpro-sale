"""
Stage 5: Final Export — 多平台多尺寸导出
═══════════════════════════════════════════
功能: 智能裁剪 + 缩放 + 格式转换 + 文件大小检查
输入: 审批通过的图片 + 目标平台
输出: 按平台尺寸导出的 PNG 文件
"""

import json
import sys
from pathlib import Path
from PIL import Image

# 添加 shared 到 path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "shared"))
from security import ensure_sandboxed

# ── 加载平台规范 ──
def _load_platform_specs():
    path = Path(__file__).parent.parent.parent.parent / "stages" / "stage2-design-direction" / "references" / "platform-specs.json"
    with open(path) as f:
        return json.load(f)

PLATFORM_SPECS = _load_platform_specs()


# ── 智能裁剪 ──
def smart_crop_resize(img: Image.Image, target_w: int, target_h: int,
                      safe_top: int = 0, safe_bottom: int = 0) -> Image.Image:
    """
    智能裁剪+缩放。优先中心裁剪，避开安全区域。
    """
    orig_w, orig_h = img.size
    target_ratio = target_w / target_h
    orig_ratio = orig_w / orig_h

    if abs(orig_ratio - target_ratio) < 0.02:
        # 比例接近，直接缩放
        return img.resize((target_w, target_h), Image.LANCZOS)

    if orig_ratio > target_ratio:
        # 原图更宽 → 裁左右
        new_w = int(orig_h * target_ratio)
        left = (orig_w - new_w) // 2
        img = img.crop((left, 0, left + new_w, orig_h))
    else:
        # 原图更高 → 裁上下，避开安全区域
        new_h = int(orig_w / target_ratio)
        top = safe_top
        bottom = orig_h - safe_bottom
        available_h = bottom - top
        if available_h >= new_h:
            # 安全区域内足够
            top = top + (available_h - new_h) // 2
        else:
            # 安全区域冲突，居中裁剪
            top = (orig_h - new_h) // 2
        img = img.crop((0, top, orig_w, top + new_h))

    return img.resize((target_w, target_h), Image.LANCZOS)


# ── 主导出函数 ──
def export_all(image_paths: list[dict], platforms: list[str],
               output_dir: str, quality: int = 95) -> tuple[list[dict], dict]:
    """
    导出所有审批通过的图片到多平台多尺寸

    Args:
        image_paths: [{id, path, concept_id}, ...]
        platforms: ["wechat_moment", "linkedin", ...]
        output_dir: 输出目录
        quality: PNG 压缩质量 (0-100)

    Returns:
        (exports_list, summary_dict)
    """
    # 沙箱验证
    export_dir = ensure_sandboxed(Path(output_dir) / "exports")
    export_dir.mkdir(parents=True, exist_ok=True)

    results = []
    total_files = 0
    total_size_kb = 0

    for img_info in image_paths:
        img_path = img_info.get("path", "")
        if not img_path or not Path(img_path).exists():
            continue

        img = Image.open(img_path).convert("RGB")

        for platform in platforms:
            specs = PLATFORM_SPECS.get(platform, [])
            if not specs:
                continue

            for spec in specs:
                safe_top = spec.get("safe_top_px", 0)
                safe_bottom = spec.get("safe_bottom_px", 0)
                max_size_kb = spec.get("max_size_kb", 5000)

                exported = smart_crop_resize(
                    img.copy(),
                    spec["width"], spec["height"],
                    safe_top, safe_bottom
                )

                filename = f"{img_info['id']}_{platform}_{spec['name']}.png"
                filepath = export_dir / filename
                exported.save(filepath, "PNG", optimize=True)

                file_size_kb = round(filepath.stat().st_size / 1024, 1)

                # 文件大小检查
                if file_size_kb > max_size_kb:
                    # 降质重试
                    exported.save(filepath, "PNG", optimize=True, quality=80)
                    file_size_kb = round(filepath.stat().st_size / 1024, 1)

                results.append({
                    "image_id": img_info["id"],
                    "concept_id": img_info.get("concept_id", ""),
                    "platform": platform,
                    "format_name": spec["name"],
                    "path": str(filepath),
                    "dimensions": f'{spec["width"]}x{spec["height"]}',
                    "format": "PNG",
                    "file_size_kb": file_size_kb,
                    "size_warning": file_size_kb > max_size_kb
                })

                total_files += 1
                total_size_kb += file_size_kb

    return results, {
        "total_files": total_files,
        "total_size_kb": round(total_size_kb, 1),
        "total_size_mb": round(total_size_kb / 1024, 1),
        "export_dir": str(export_dir),
        "platforms": platforms
    }


# ── CLI ──
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True, help="JSON file with image list")
    ap.add_argument("--platforms", required=True, help="Comma-separated platforms")
    ap.add_argument("--output", required=True, help="Output directory")
    args = ap.parse_args()

    with open(args.images) as f:
        images = json.load(f)

    platforms = [p.strip() for p in args.platforms.split(",")]
    results, summary = export_all(images, platforms, args.output)

    print(f"✅ 导出完成: {summary['total_files']} 文件, {summary['total_size_mb']}MB")
    print(f"📁 {summary['export_dir']}")
    for r in results:
        warning = " ⚠️ 超限" if r.get("size_warning") else ""
        print(f"  {r['dimensions']} | {r['platform']}/{r['format_name']} | {r['file_size_kb']}KB{warning}")
