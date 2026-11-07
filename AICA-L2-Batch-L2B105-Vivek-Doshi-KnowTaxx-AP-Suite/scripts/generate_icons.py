"""Draw the PWA icons and favicon with Pillow. Run: python scripts/generate_icons.py"""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "app" / "static" / "icons"
NAVY, GOLD, WHITE = (30, 58, 110), (232, 160, 32), (255, 255, 255)


def draw(size):
    scale = 4  # draw large, shrink for smooth edges
    s = size * scale
    image = Image.new("RGB", (s, s), NAVY)
    d = ImageDraw.Draw(image)
    w = max(2, int(s * 0.03))
    # Open book page behind the K
    d.rounded_rectangle((s * .17, s * .2, s * .33, s * .8), radius=int(s * .03), outline=GOLD, width=w)
    for y in (.32, .44, .56):
        d.line((s * .21, s * y, s * .29, s * y), fill=GOLD, width=max(1, w // 2))
    # The K
    k = int(s * .085)
    d.line((s * .42, s * .2, s * .42, s * .8), fill=WHITE, width=k)
    d.line((s * .42, s * .54, s * .74, s * .2), fill=WHITE, width=k)
    d.line((s * .5, s * .46, s * .78, s * .8), fill=WHITE, width=k)
    # Gold check swoosh
    c = int(s * .05)
    d.line((s * .62, s * .13, s * .69, s * .2), fill=GOLD, width=c)
    d.line((s * .69, s * .2, s * .86, s * .06), fill=GOLD, width=c)
    return image.resize((size, size), Image.LANCZOS)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    draw(192).save(OUT / "icon-192.png")
    draw(512).save(OUT / "icon-512.png")
    draw(256).save(OUT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    print("Icons written to", OUT)


if __name__ == "__main__":
    main()
