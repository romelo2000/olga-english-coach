#!/usr/bin/env python3
"""Generate app icon: blue rounded square with white 'O' and 'EN' badge."""
from PIL import Image, ImageDraw, ImageFont
import os

size = 512
img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)
margin = 20
radius = 110
draw.rounded_rectangle([margin, margin, size - margin, size - margin], radius=radius, fill=(37, 99, 235, 255))
for i in range(60):
    alpha = 60 - i
    if alpha <= 0:
        break
    r = 180 - i * 2
    draw.ellipse([160 - r, 160 - r, 160 + r, 160 + r], fill=(59, 130, 246, alpha))
try:
    font_large = ImageFont.truetype('/System/Library/Fonts/SFNS.ttf', 280)
except Exception:
    try:
        font_large = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 280)
    except Exception:
        font_large = ImageFont.load_default()
text = 'O'
bbox = draw.textbbox((0, 0), text, font=font_large)
tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
x = (size - tw) // 2 - bbox[0]
y = (size - th) // 2 - bbox[1] - 10
draw.text((x + 3, y + 3), text, fill=(0, 0, 0, 60), font=font_large)
draw.text((x, y), text, fill=(255, 255, 255, 255), font=font_large)
try:
    font_small = ImageFont.truetype('/System/Library/Fonts/SFNS.ttf', 56)
except Exception:
    try:
        font_small = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 56)
    except Exception:
        font_small = ImageFont.load_default()
badge_text = 'EN'
bbox2 = draw.textbbox((0, 0), badge_text, font=font_small)
bw, bh = bbox2[2] - bbox2[0], bbox2[3] - bbox2[1]
bx = (size - bw) // 2 - bbox2[0]
by = size - 90
draw.rounded_rectangle([bx - 12, by - 6, bx + bw + 12, by + bh + 6], radius=12, fill=(255, 255, 255, 230))
draw.text((bx, by), badge_text, fill=(37, 99, 235, 255), font=font_small)
out_path = os.path.join(os.path.dirname(__file__), 'assets', 'icon.png')
img.save(out_path, 'PNG')
print(f'Icon saved: {os.path.getsize(out_path)} bytes at {out_path}')
