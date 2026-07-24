#!/usr/bin/env python3
"""Generate the GitHub social preview image (1280x640).

Set it at: Settings → General → Social preview → Upload an image.
在 Settings → General → Social preview 上传。

Shown when the repo link is shared on X / Slack / WeChat etc.
分享仓库链接时显示的大图。
"""
import os, sys, io
from PIL import Image, ImageDraw, ImageFont
import cairosvg

INK="#09141A"; PANEL="#0E1A20"; LINE="#22414C"
TEXT="#E9E5D9"; DIM="#9CB1B7"; MUTE="#6B848C"
GOLD="#D9A441"; TEAL="#3FAE8C"; CORAL="#E36A48"; AZURE="#5FA8E0"

FONTS = ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
         "/System/Library/Fonts/PingFang.ttc", "C:/Windows/Fonts/msyh.ttc"]
FP = next((p for p in FONTS if os.path.exists(p)), None)
if not FP:
    sys.exit("✗ No CJK font found — install fonts-noto-cjk")

_c = {}
def F(sz, bold=False):
    k = (sz, bold)
    if k not in _c:
        _c[k] = ImageFont.truetype(FP, sz, index=2 if bold else 0)
    return _c[k]

W, H = 1280, 640
im = Image.new("RGB", (W, H), INK)
d = ImageDraw.Draw(im)

# subtle top accent
d.rectangle([0, 0, W, 5], fill=GOLD)

# logo
here = os.path.dirname(os.path.abspath(__file__))
svg = os.path.join(here, "..", "..", "apps", "shell", "src-tauri", "icons", "icon.svg")
if os.path.exists(svg):
    logo = Image.open(io.BytesIO(cairosvg.svg2png(url=svg, output_width=104, output_height=104))).convert("RGBA")
    im.paste(logo, (72, 66), logo)

d.text((208, 74), "F3-OpenScience", font=F(52, True), fill=TEXT)
d.text((212, 138), "an open-source research agent you can sign your name to",
       font=F(20), fill=MUTE)

# headline — the positioning, both languages
d.text((72, 226), "Sign your name to it —", font=F(44, True), fill=TEXT)
d.text((72, 284), "without narrowing what you can reach", font=F(44, True), fill=GOLD)
d.text((74, 352), "敢署名,且不因此变窄", font=F(34, True), fill=DIM)

# the distinguishing claim
d.rounded_rectangle([72, 414, W-72, 486], radius=10, fill=PANEL, outline=LINE, width=1)
d.text((96, 430), "Every \"verify + remember\" system quietly narrows itself.",
       font=F(19), fill=DIM)
d.text((96, 456), "所有「校验 + 记忆」的系统都会悄悄变窄 —— 我们把这条路堵上了。",
       font=F(19), fill=TEXT)

# metric chips
chips = [("0 hallucinated citations", TEAL), ("0 false-rejection rate", GOLD),
         ("14 test suites", AZURE), ("Apache-2.0", MUTE)]
x = 72
for label, col in chips:
    w = int(d.textlength(label, font=F(17))) + 30
    d.rounded_rectangle([x, 522, x + w, 562], radius=8, outline=col, width=1)
    d.text((x + 15, 532), label, font=F(17), fill=col)
    x += w + 14

d.text((72, 588), "github.com/MedocMay/F3-OpenScience", font=F(16), fill=MUTE)

out = os.path.join(here, "social-preview.png")
im.save(out)
print("✓", os.path.relpath(out, here), im.size)
