"""Generate BookwormPRO banner.png — dark terminal style with gold text."""
from PIL import Image, ImageDraw, ImageFont
import os

W, H = 1145, 196
SCALE = 3  # 3x render then downscale for anti-aliasing
W2, H2 = W * SCALE, H * SCALE

BG = (8, 8, 8)
GOLD = (255, 200, 0)
GOLD_DARK = (180, 120, 0)
SHADOW = (40, 30, 10)

# Create canvas
img = Image.new("RGB", (W2, H2), BG)
draw = ImageDraw.Draw(img)

# Font
FD = r"C:\Windows\Fonts"
font_paths = [
    os.path.join(FD, "consola.ttf"),
    os.path.join(FD, "cour.ttf"),
    os.path.join(FD, "lucon.ttf"),
]
font = None
for fp in font_paths:
    if os.path.exists(fp):
        font = ImageFont.truetype(fp, 180)
        break
if font is None:
    font = ImageFont.load_default()

TEXT = "BOOKWORMPRO"

# Measure text
bbox = draw.textbbox((0, 0), TEXT, font=font)
tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
tx = (W2 - tw) // 2
ty = (H2 - th) // 2 - 10

# Multiple shadow layers for depth
offsets = [(8, 8), (6, 6), (4, 4), (2, 2)]
for ox, oy in offsets:
    draw.text((tx + ox, ty + oy), TEXT, fill=SHADOW, font=font)

# Inner dark outline
for ox, oy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
    draw.text((tx + ox, ty + oy), TEXT, fill=GOLD_DARK, font=font)

# Main text
draw.text((tx, ty), TEXT, fill=GOLD, font=font)

# Add subtle horizontal scan lines
for y in range(0, H2, 4):
    overlay = Image.new("RGBA", (W2, 1), (0, 0, 0, 30))
    img.paste(overlay, (0, y), overlay)

# Downscale
img = img.resize((W, H), Image.LANCZOS)

# Save
out = os.path.join(os.path.dirname(__file__), "..", "assets", "banner.png")
img.save(out, "PNG", quality=95)
print(f"Banner saved: {out} ({W}x{H})")
