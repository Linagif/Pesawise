"""Generate the PesaWise app icons (needs Pillow, which ReportLab already installs).
Run from the project folder:  python tools/make_icons.py"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

INK, GOLD = (11, 46, 36), (242, 183, 5)
OUT = Path(__file__).resolve().parent.parent / "static" / "pwa"
FONT_CANDIDATES = ["DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                   "C:/Windows/Fonts/arialbd.ttf", "Arial Bold.ttf"]


def font(size):
    for name in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_icon(size, rounded=True, coin=0.30):
    """A gold coin with a 'P' on the dark-green brand colour. 'coin' is the coin radius as a share of the size
    (kept small enough for maskable icons, whose safe zone is the central 80%)."""
    scale = 4                                              # draw big, then shrink for smooth edges
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if rounded:
        d.rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.22), fill=INK)
    else:
        d.rectangle([0, 0, s, s], fill=INK)
    r, c = int(s * coin), s // 2
    d.ellipse([c - r, c - r, c + r, c + r], fill=GOLD)
    f = font(int(r * 1.35))
    d.text((c, c), "P", font=f, fill=INK, anchor="mm")
    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    draw_icon(192).save(OUT / "icon-192.png")
    draw_icon(512).save(OUT / "icon-512.png")
    draw_icon(512, rounded=False, coin=0.28).save(OUT / "icon-maskable-512.png")   # full-bleed, content in safe zone
    draw_icon(180, rounded=False).save(OUT / "apple-touch-icon.png")
    draw_icon(32).save(OUT / "favicon-32.png")
    print("icons written to", OUT)
