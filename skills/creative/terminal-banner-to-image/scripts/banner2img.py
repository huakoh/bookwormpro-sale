#!/usr/bin/env python3
"""Terminal Banner → 4:3 Image
   将代码文字横幅（ASCII art + CJK 混排）渲染为高分辨率 PNG。
   自动适配字号、检测 CJK 字体、逐字符对齐。
   Usage: python banner2img.py <banner.txt> [--size WxH] [--output PATH] [--bg R,G,B] [--theme bookworm|gold|matrix]
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import sys, os

def load_banner(path_or_text):
    if os.path.isfile(path_or_text):
        with open(path_or_text, 'r', encoding='utf-8') as f:
            return f.read()
    return path_or_text

def find_cjk_font(font_dir=r"C:\Windows\Fonts", size=22):
    candidates = [
        "simsun.ttc", "simhei.ttf", "msyh.ttc",
        "Noto Sans SC (TrueType).otf", "NotoSansSC-VF.ttf",
    ]
    for name in candidates:
        p = os.path.join(font_dir, name) if os.path.isdir(font_dir) else name
        if not os.path.exists(p):
            continue
        try:
            font = ImageFont.truetype(p, size)
            font.getbbox('█')
            font.getbbox('向')
            return font, p, size
        except Exception:
            continue
    return ImageFont.load_default(), "default", 14

def is_cjk(ch):
    return ord(ch) > 127

def measure_font(font, test_ascii='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789',
                 test_cjk='向劳动国节日快乐幸福伟大光荣'):
    aw = max(font.getbbox(c)[2] - font.getbbox(c)[0] for c in test_ascii)
    cw = max(font.getbbox(c)[2] - font.getbbox(c)[0] for c in test_cjk) if test_cjk else aw * 2
    lh = font.getbbox("█")[3] - font.getbbox("█")[1] + 4
    return aw, cw, lh

def line_width(line, aw, cw):
    return sum(cw if is_cjk(ch) else aw for ch in line)

def auto_fit(lines, font_path, font_size, target_w):
    aw, cw, lh = measure_font(ImageFont.truetype(font_path, font_size))
    max_w = max(line_width(l, aw, cw) for l in lines)
    while max_w > target_w and font_size > 10:
        font_size -= 1
        f = ImageFont.truetype(font_path, font_size)
        aw, cw, lh = measure_font(f)
        max_w = max(line_width(l, aw, cw) for l in lines)
    return ImageFont.truetype(font_path, font_size), aw, cw, lh, max_w

# ── 主题预设 ──
THEMES = {
    "bookworm": {
        "bg": (10, 15, 28), "frame": (40, 116, 166), "inner": (31, 97, 141),
        "accent": (93, 173, 226), "body": (214, 234, 248), "sub": (160, 210, 240),
        "slogan": (255, 215, 0), "divider": (0, 206, 209),
    },
    "gold": {
        "bg": (20, 5, 5), "frame": (180, 120, 40), "inner": (140, 90, 30),
        "accent": (255, 215, 0), "body": (255, 250, 230), "sub": (220, 200, 140),
        "slogan": (255, 235, 120), "divider": (200, 160, 40),
    },
    "matrix": {
        "bg": (0, 8, 0), "frame": (0, 180, 0), "inner": (0, 140, 0),
        "accent": (0, 255, 0), "body": (180, 255, 180), "sub": (100, 200, 100),
        "slogan": (200, 255, 200), "divider": (0, 220, 0),
    },
}

def render(banner_text, W=1600, H=1200, theme="bookworm", output="banner.png",
           font_dir=r"C:\Windows\Fonts"):
    T = THEMES.get(theme, THEMES["bookworm"])

    lines = [l.rstrip() for l in banner_text.split('\n')]
    total_lines = len([l for l in lines if l.strip()])  # skip pure blanks

    font, font_path, fs = find_cjk_font(font_dir)
    font, aw, cw, lh, max_w = auto_fit(lines, font_path, fs, int(W * 0.94))

    text_h = lh * len(lines)
    ox, oy = (W - max_w) // 2, (H - text_h) // 2

    img = Image.new("RGB", (W, H), T["bg"])

    # Glow
    glow = Image.new("RGBA", (W, H), (0,0,0,0))
    gd = ImageDraw.Draw(glow)
    ac = T["accent"]
    for r in range(max(W,H)//2, 150, -1):
        a = int(6 * (1 - r/max(W,H)))
        if a <= 0: break
        gd.ellipse([W//2-r, H//2-r, W//2+r, H//2+r], fill=(ac[0],ac[1],ac[2],a))
    img.paste(Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB"))

    draw = ImageDraw.Draw(img)

    for row, line in enumerate(lines):
        y = oy + row * lh
        lw = line_width(line, aw, cw)
        x = ox + (max_w - lw) // 2

        for ch in line:
            # Color rules
            if ch in '╔╗╚╝║═':
                color = T["frame"]
            elif ch in '╭╮╰╯│─':
                color = T["inner"]
            elif ch in '█▄▀▌▐':
                color = T["accent"]
            elif ch == '✦':
                color = T["slogan"]
            elif is_cjk(ch):
                color = T["slogan"] if '✦' in line else T["body"]
            else:
                color = T["body"]

            draw.text((x, y), ch, font=font, fill=color)
            x += cw if is_cjk(ch) else aw

    os.makedirs(os.path.dirname(output) if os.path.dirname(output) else ".", exist_ok=True)
    img.save(output, "PNG")
    return output, W, H

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python banner2img.py <banner.txt> [--size WxH] [--output PATH] [--theme bookworm|gold|matrix]")
        sys.exit(1)

    banner_src = sys.argv[1]
    W, H = 1600, 1200
    output = "banner.png"
    theme = "bookworm"

    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--size" and i+1 < len(args):
            W, H = map(int, args[i+1].split("x"))
            i += 2
        elif args[i] == "--output" and i+1 < len(args):
            output = args[i+1]
            i += 2
        elif args[i] == "--theme" and i+1 < len(args):
            theme = args[i+1]
            i += 2
        else:
            i += 1

    banner = load_banner(banner_src)
    out, w, h = render(banner, W, H, theme, output)
    print(f"OK: {out}  ({w}×{h})  {os.path.getsize(out)/1024:.1f} KB")
