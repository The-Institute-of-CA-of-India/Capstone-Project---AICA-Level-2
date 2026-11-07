"""Generates mukhota.ico (half mask, half notice page, on an indigo-teal tile) with Pillow."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

ASSETS = Path(__file__).resolve().parent / "assets"
ICON_PATH = ASSETS / "mukhota.ico"
PNG_PATH = ASSETS / "mukhota.png"

INDIGO = (40, 53, 147)
TEAL = (0, 150, 136)


NAVY = (30, 37, 99)
FOLD = (197, 202, 233)
INK = (17, 17, 17)


def build_icon_image(size: int = 256) -> Image.Image:
    """Left half a mask, right half a notice page with one line blacked out; drawn at 4x and downsampled."""
    S = size * 4

    def box(x0: float, y0: float, x1: float, y1: float) -> list[float]:
        return [S * x0, S * y0, S * x1, S * y1]

    def pts(*xy: float) -> list[tuple[float, float]]:
        return [(S * xy[i], S * xy[i + 1]) for i in range(0, len(xy), 2)]

    # Rounded tile with a diagonal indigo -> teal gradient.
    v = Image.linear_gradient("L").resize((S, S))
    grad = ImageChops.add(v, v.rotate(90), scale=2)  # 0 at top-left, 255 at bottom-right
    tile = Image.composite(Image.new("RGB", (S, S), TEAL), Image.new("RGB", (S, S), INDIGO), grad)
    tile_mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(tile_mask).rounded_rectangle(box(0, 0, 1, 1), radius=S * 0.22, fill=255)
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    img.paste(tile, (0, 0), tile_mask)

    # Left: half of a masquerade mask (upswept outer wing, almond eye, half a nose notch), cut at the centre line.
    mask_half = Image.new("L", (S, S), 0)
    m = ImageDraw.Draw(mask_half)
    m.ellipse(box(0.15, 0.36, 0.85, 0.68), fill=255)
    m.polygon(pts(0.10, 0.25, 0.36, 0.38, 0.18, 0.58, 0.15, 0.50), fill=255)
    m.rectangle(box(0.5, 0, 1, 1), fill=0)
    m.polygon(pts(0.44, 0.69, 0.5, 0.58, 0.5, 0.69), fill=0)
    # Almond eye: where two offset circles overlap.
    eye_a, eye_b = Image.new("L", (S, S), 0), Image.new("L", (S, S), 0)
    ImageDraw.Draw(eye_a).ellipse(box(0.20, 0.42, 0.46, 0.62), fill=255)
    ImageDraw.Draw(eye_b).ellipse(box(0.20, 0.36, 0.46, 0.56), fill=255)
    mask_half = ImageChops.subtract(mask_half, ImageChops.multiply(eye_a, eye_b))

    # Right: a notice page with a folded top corner.
    page = Image.new("L", (S, S), 0)
    p = ImageDraw.Draw(page)
    p.rounded_rectangle(box(0.5, 0.17, 0.82, 0.83), radius=S * 0.025, fill=255)
    p.rectangle(box(0.5, 0.17, 0.56, 0.83), fill=255)  # square edge where it meets the mask
    p.polygon(pts(0.71, 0.165, 0.825, 0.165, 0.825, 0.28), fill=0)

    white = Image.new("RGBA", (S, S), (255, 255, 255, 255))
    img.paste(white, (0, 0), ImageChops.lighter(mask_half, page))

    d = ImageDraw.Draw(img)
    d.polygon(pts(0.71, 0.17, 0.71, 0.28, 0.82, 0.28), fill=FOLD + (255,))
    # Text lines, with the second one redacted.
    w = S * 0.022
    for y, x1 in ((0.36, 0.66), (0.56, 0.74), (0.66, 0.70), (0.75, 0.64)):
        d.rounded_rectangle([S * 0.56, S * y - w / 2, S * x1, S * y + w / 2], radius=w / 2, fill=NAVY + (255,))
    d.rounded_rectangle(box(0.555, 0.425, 0.765, 0.485), radius=S * 0.008, fill=INK + (255,))
    return img.resize((size, size), Image.LANCZOS)


def ensure_icon(force: bool = False) -> Path:
    """Create mukhota.ico and mukhota.png if missing; returns the .ico path."""
    ASSETS.mkdir(parents=True, exist_ok=True)
    if force or not ICON_PATH.exists() or not PNG_PATH.exists():
        img = build_icon_image(256)
        img.save(PNG_PATH)
        img.save(ICON_PATH, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return ICON_PATH


if __name__ == "__main__":
    print(f"Icon written to {ensure_icon(force=True)}")
