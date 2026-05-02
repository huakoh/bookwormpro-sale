"""
BookwormPRO 图标生成 — 基于 quantum-logo-suite 设计语言
Seedream 5.0 生图 + doubao vision 评审 + 水印去除 + 多尺寸导出
"""

import base64, json, time, requests
from pathlib import Path
from datetime import datetime

# ═══════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════
ARK_KEY = "ark-a7d4c36a-3f75-4c34-9637-defde844c34c-75981"
ARK_BASE = "https://ark.cn-beijing.volces.com/api/v3"
OUTPUT_DIR = Path.home() / "bookwormpro-sale/assets/icons"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════════
# 设计语言 (from quantum-logo-suite)
# ═══════════════════════════════════════════════════
# Colors: gold #C8A050, teal #20E0C0, blue #4080FF, purple #A820E0
# Theme: Quantum rotation, bookworm, tech elegance
# Background: deep cosmic dark #06060C

ICONS = [
    {
        "name": "main-logo",
        "desc": "主应用图标 - 量子旋转书虫",
        "prompt": """
专业的AI应用图标设计，深色背景上的量子科技风格书虫logo：
- 中央是一个由发光的金色量子粒子旋转轨道组成的"书虫"抽象符号，形似翻开的书籍与虫体融合
- 轨道由多个发光的蓝紫色光点组成，呈椭圆形旋转路径，暗示量子纠缠
- 金色(#C8A050)为主色调，辅以青色(#20E0C0)和深蓝(#4080FF)渐变光晕
- 背景为深邃的太空黑(#06060C)，有微弱的星场粒子
- 整体风格：简洁、专业、科技感，适合作为软件图标
- 无文字、无边框、无多余装饰元素
- 正方形构图，1920x1920，高保真渲染
""",
    },
    {
        "name": "app-icon-simple",
        "desc": "简化应用图标 - 适合任务栏/托盘",
        "prompt": """
极简的软件应用图标，深色背景，量子书虫符号：
- 中心一个由金色光轨组成的简洁书虫轮廓符号，线条流畅
- 光轨为金色(#C8A050)渐变到青色(#20E0C0)
- 纯黑背景(#06060C)，无任何纹理
- 极简设计，仅3-4条光轨弧线构成书虫形态
- 正方形，适合缩小到64x64仍可识别
- 无文字，无多余元素
""",
    },
    {
        "name": "favicon",
        "desc": "网站 favicon - 16x16 可识别",
        "prompt": """
极其简洁的favicon图标，纯黑背景：
- 中心一个金色发光点，周围两条弧线光轨形成字母"B"的抽象形态
- 金色(#FFD040)发光，有微弱的青色光晕
- 纯黑背景
- 极其简约，确保缩小到16x16像素仍可辨认
- 无文字，无边框
""",
    },
]

# ═══════════════════════════════════════════════════
# Seedream API
# ═══════════════════════════════════════════════════
def generate_seedream(prompt, retries=3):
    """调用 Seedream 5.0 生图"""
    url = f"{ARK_BASE}/images/generations"
    headers = {"Authorization": f"Bearer {ARK_KEY}", "Content-Type": "application/json"}
    body = {
        "model": "doubao-seedream-5-0-260128",
        "prompt": prompt.strip()[:800],
        "n": 1,
        "size": "1920x1920",
        "response_format": "b64_json",
    }
    
    for attempt in range(retries):
        try:
            resp = requests.post(url, headers=headers, json=body, timeout=120)
            if resp.status_code == 200:
                data = resp.json()
                b64 = data["data"][0]["b64_json"]
                return base64.b64decode(b64)
            else:
                print(f"    Attempt {attempt+1}: HTTP {resp.status_code} - {resp.text[:100]}")
        except Exception as e:
            print(f"    Attempt {attempt+1}: {e}")
        if attempt < retries - 1:
            time.sleep(3)
    return None

# ═══════════════════════════════════════════════════
# doubao Vision 评审
# ═══════════════════════════════════════════════════
def review_with_vision(img_bytes, icon_name):
    """用 doubao vision 评审图标质量"""
    b64 = base64.b64encode(img_bytes).decode()
    url = f"{ARK_BASE}/chat/completions"
    headers = {"Authorization": f"Bearer {ARK_KEY}", "Content-Type": "application/json"}
    body = {
        "model": "doubao-seed-1-6-vision-250815",
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            {"type": "text", "text": f"""评估这张AI应用图标，从以下维度0-10分：
- 设计质量：构图/色彩/专业度
- 品牌识别：是否像"书虫+量子科技"主题
- 可缩放性：缩小后是否仍可辨认
- 商业可用性：是否适合作为软件产品图标

返回纯JSON: {{"design":分, "brand":分, "scalable":分, "commercial":分, "total":均分, "verdict":"PASS或REDO", "notes":"简评"}}"""},
        ]}],
        "max_tokens": 200,
    }
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=60)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        return f"Review failed: {resp.status_code}"
    except Exception as e:
        return f"Review error: {e}"

# ═══════════════════════════════════════════════════
# 水印去除 (PIL)
# ═══════════════════════════════════════════════════
def remove_watermark(img_bytes):
    """去除 Seedream 右下角 AI生成 水印"""
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        w, h = img.size
        wm_w = int(w * 0.10)
        wm_h = int(h * 0.05)
        wm_x, wm_y = w - wm_w, h - wm_h
        source = img.crop((wm_x, wm_y - wm_h, w, wm_y))
        img.paste(source, (wm_x, wm_y))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except ImportError:
        return img_bytes  # Pillow not available

# ═══════════════════════════════════════════════════
# 多尺寸导出
# ═══════════════════════════════════════════════════
def export_sizes(img_bytes, name):
    """导出多个尺寸"""
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
        sizes = {
            "512": 512, "256": 256, "128": 128,
            "64": 64, "48": 48, "32": 32, "16": 16,
        }
        results = {}
        for label, size in sizes.items():
            resized = img.resize((size, size), Image.LANCZOS)
            out_path = OUTPUT_DIR / f"{name}_{label}x{label}.png"
            resized.save(out_path, "PNG")
            results[label] = str(out_path)
        # 保留原图
        orig = OUTPUT_DIR / f"{name}_original.png"
        Image.open(io.BytesIO(img_bytes)).save(orig, "PNG")
        results["original"] = str(orig)
        return results
    except ImportError:
        out = OUTPUT_DIR / f"{name}_original.png"
        out.write_bytes(img_bytes)
        return {"original": str(out)}

# ═══════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════
def main():
    print("🎨 BookwormPRO 图标生成")
    print(f"   输出: {OUTPUT_DIR}\n")
    
    results = []
    for i, icon in enumerate(ICONS, 1):
        print(f"[{i}/{len(ICONS)}] {icon['name']} — {icon['desc']}")
        
        # 生成
        print("  🖼  Seedream 生图中...", end=" ", flush=True)
        img_bytes = generate_seedream(icon["prompt"])
        if not img_bytes:
            print("❌ 失败")
            continue
        print(f"✅ {len(img_bytes)//1024}KB")
        
        # 去水印
        img_bytes = remove_watermark(img_bytes)
        
        # 评审
        print("  🔍 评审中...", end=" ", flush=True)
        review = review_with_vision(img_bytes, icon["name"])
        print(review[:120])
        
        # 导出
        exported = export_sizes(img_bytes, icon["name"])
        print(f"  📦 导出 {len(exported)} 尺寸")
        for label, path in exported.items():
            print(f"     {label}: {path}")
        
        results.append({"icon": icon["name"], "files": exported, "review": review})
        time.sleep(2)  # API 间间隔
    
    # 汇总
    print(f"\n{'='*60}")
    print(f"生成完成: {len(results)}/{len(ICONS)} 个图标")
    for r in results:
        print(f"  {r['icon']}: {len(r['files'])} 文件")
    print(f"\n输出目录: {OUTPUT_DIR}")
    
    # 保存评审报告
    report = OUTPUT_DIR / "_review_report.json"
    report.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"评审报告: {report}")

if __name__ == "__main__":
    main()
