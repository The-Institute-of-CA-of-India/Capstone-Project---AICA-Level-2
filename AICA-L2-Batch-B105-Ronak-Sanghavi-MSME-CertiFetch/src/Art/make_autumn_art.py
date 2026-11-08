"""Paints the autumn artwork used by MSME CertiFetch. Run once; the app only reads the PNGs.
Needs numpy and Pillow. Output is deterministic."""
import math
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
LOGO_DIR = os.path.join(HERE, "..", "Logo")
GROUND = np.array([239, 243, 230], dtype=float)
rng = np.random.default_rng(1947)

MAPLE = [(0, -1), (.12, -.62), (.30, -.72), (.24, -.38), (.62, -.50), (.52, -.24), (.90, -.22),
         (.62, .12), (.70, .30), (.30, .24), (.22, .50), (.06, .38), (0, .40)]
BEECH = [(0, -1), (.16, -.80), (.30, -.52), (.38, -.18), (.34, .18), (.20, .50), (0, .72)]


def leaf(shape, size, tip, base, seed=0):
    """One painted leaf as RGBA: soft edge, two-tone wash, pale veins, mottling."""
    S = size * 3
    r = np.random.default_rng(seed)
    half = [(S / 2 + x * S * .47, S / 2 + y * S * .47) for x, y in shape]
    mirror = [(S - x, y) for x, y in reversed(half[1:-1])]
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).polygon(half + mirror, fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(S * .012)).point(lambda v: 255 if v > 120 else 0)
    ys = np.linspace(0, 1, S)[:, None]
    xs = np.linspace(0, 1, S)[None, :]
    t = np.clip(ys * .75 + np.abs(xs - .5) * .5, 0, 1)[..., None]
    rgb = np.array(tip, float) * (1 - t) + np.array(base, float) * t
    mottling = np.array(Image.fromarray((r.random((S // 12, S // 12)) * 255).astype("uint8")).resize((S, S), Image.BICUBIC), float)[..., None] / 255
    rgb = np.clip(rgb * (.90 + mottling * .20), 0, 255)
    edge = np.array(mask.filter(ImageFilter.GaussianBlur(S * .03)), float)[..., None] / 255
    rgb = rgb * (.80 + .20 * np.clip(edge * 1.5 - .4, 0, 1))
    img = Image.fromarray(rgb.astype("uint8"), "RGB")
    d = ImageDraw.Draw(img, "RGBA")
    cx, top, bottom = S / 2, S * .03, S * .98
    vein = (255, 240, 205, 120)
    d.line([(cx, top + S * .06), (cx, bottom)], fill=(112, 66, 34, 255), width=max(2, S // 70))
    for k in range(1, 5):
        y = S * (.22 + k * .13)
        reach = S * (.34 - k * .03)
        for sign in (-1, 1):
            d.line([(cx, y), (cx + sign * reach, y - S * .16)], fill=vein, width=max(1, S // 130))
    img.putalpha(mask)
    return img.resize((size, size), Image.LANCZOS)


def lerp(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def paint_scene(W=2800, H=380):
    y, x = np.mgrid[0:H, 0:W].astype(float)
    u, v = x / W, y / H
    sky_a, sky_b, sky_c = np.array([214, 232, 226.]), np.array([250, 232, 200.]), np.array([249, 200, 142.])
    t = u[..., None]
    img = np.where(t < .6, sky_a + (sky_b - sky_a) * (t / .6), sky_b + (sky_c - sky_b) * ((t - .6) / .4))
    glow = np.exp(-(((u - .80) / .17) ** 2 + ((v - .42) / .55) ** 2))[..., None]
    img = img + (np.array([255, 226, 170.]) - img) * glow * .75
    scene = Image.fromarray(np.clip(img, 0, 255).astype("uint8"), "RGB").convert("RGBA")

    for layer, (base_y, colours, rmin, rmax, blur, opacity, count) in enumerate([
        (.60, [(190, 200, 170), (214, 190, 140), (222, 168, 120)], 26, 62, 17, 120, 420),
        (.74, [(150, 172, 112), (219, 158, 62), (205, 110, 58), (178, 74, 48)], 20, 50, 9, 175, 520),
    ]):
        canopy = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(canopy)
        for _ in range(count):
            cx = rng.uniform(-40, W + 40)
            ridge = H * base_y + 16 * math.sin(cx * .004 + layer) + 9 * math.sin(cx * .013)
            cy = ridge + rng.uniform(-14, 40)
            r = rng.uniform(rmin, rmax)
            c = colours[rng.integers(len(colours))]
            d.ellipse((cx - r * 1.15, cy - r, cx + r * 1.15, cy + r), fill=(*c, opacity))
        soft = canopy.filter(ImageFilter.GaussianBlur(blur))
        clear = np.clip((u - .30) / .24, 0, 1)
        clear = clear * clear * (3 - 2 * clear)
        layer_alpha = np.asarray(soft.getchannel("A"), float) * clear
        soft.putalpha(Image.fromarray(layer_alpha.astype("uint8"), "L"))
        scene.alpha_composite(soft)

    # Breeze: long tapering currents that curl at the end
    wind = Image.new("RGBA", (W * 2, H * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(wind)
    for (x0, y0, length, amp, curl) in [(1000, 72, 1200, 20, 1), (1240, 176, 1300, 15, -1), (1560, 42, 700, 10, -1)]:
        pts = []
        for i in range(161):
            p = i / 160
            px = x0 + length * p
            py = y0 + amp * math.sin(p * math.pi * 2.3)
            pts.append((px, py))
        ex, ey = pts[-1]
        for i in range(1, 70):
            a = i / 69 * 4.6
            rad = 44 * (1 - i / 90)
            pts.append((ex + rad * math.sin(a), ey + curl * (rad - rad * math.cos(a))))
        for i in range(len(pts) - 1):
            p = i / (len(pts) - 1)
            w = 1.5 + 3.2 * math.sin(p * math.pi)
            alpha = int(150 * math.sin(p * math.pi) ** .6)
            d.line([(pts[i][0] * 2, pts[i][1] * 2), (pts[i + 1][0] * 2, pts[i + 1][1] * 2)], fill=(255, 255, 250, alpha), width=max(1, int(w * 2)))
    scene.alpha_composite(wind.resize((W, H), Image.LANCZOS))

    # Maple bough reaching in from the top right
    bough = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(bough)
    def curve(p0, p1, p2, w0, w1, n=420):
        pts = []
        for i in range(n + 1):
            s = i / n
            q = (((1 - s) ** 2 * p0[0] + 2 * (1 - s) * s * p1[0] + s * s * p2[0]),
                 ((1 - s) ** 2 * p0[1] + 2 * (1 - s) * s * p1[1] + s * s * p2[1]))
            pts.append(q)
            r = (w0 + (w1 - w0) * s) / 2
            d.ellipse((q[0] - r, q[1] - r, q[0] + r, q[1] + r), fill=(92, 62, 44, 255))
        return pts
    main = curve((W + 30, -24), (W - 260, 130), (W - 790, 96), 26, 4)
    arms = [curve(main[int(f * 420)], (main[int(f * 420)][0] - dx * .5, main[int(f * 420)][1] + dy * 1.15), (main[int(f * 420)][0] - dx, main[int(f * 420)][1] + dy), 8, 2, 240)
            for f, dx, dy in [(.28, 170, 170), (.46, 250, -66), (.62, 230, 118), (.80, 150, 66)]]
    palette = [((214, 62, 34), (150, 38, 36)), ((232, 118, 34), (190, 62, 30)), ((240, 170, 52), (216, 104, 28)), ((196, 54, 44), (120, 34, 40))]
    anchors = main[20:][::4] + [p for a in arms for p in a[60:][::8]]
    order = rng.permutation(len(anchors))[:60]
    for k, idx in enumerate(order):
        ax, ay = anchors[idx]
        size = int(rng.uniform(54, 112))
        tip, base = palette[rng.integers(len(palette))]
        art = leaf(MAPLE, size, tip, base, seed=int(k)).rotate(rng.uniform(100, 260), resample=Image.BICUBIC, expand=True)
        off = rng.normal(0, 18, 2)
        bough.alpha_composite(art, (max(0, int(ax - art.width / 2 + off[0])), max(0, int(ay - art.height / 2 + off[1] + 24))))
    shadow = bough.filter(ImageFilter.GaussianBlur(7))
    tint = Image.new("RGBA", bough.size, (120, 72, 40, 0))
    tint.putalpha(shadow.getchannel("A").point(lambda a: int(a * .22)))
    scene.alpha_composite(tint, (5, 12))
    scene.alpha_composite(bough)

    # A few leaves already on the wind
    for seed, (lx, ly, size, rot, shape, cols) in enumerate([
        (1420, 112, 54, 40, MAPLE, palette[1]), (1640, 214, 70, 130, MAPLE, palette[0]), (1820, 92, 46, 220, BEECH, palette[2]),
        (1290, 196, 42, 300, BEECH, palette[1]), (1960, 248, 58, 80, MAPLE, palette[2]),
    ]):
        art = leaf(shape, size, cols[0], cols[1], seed=200 + seed).rotate(rot, resample=Image.BICUBIC, expand=True)
        scene.alpha_composite(art, (lx, ly))

    arr = np.asarray(scene.convert("RGB"), float)
    grain = rng.normal(0, 2.2, (H, W, 1))
    arr = np.clip(arr + grain, 0, 255)
    ramp = np.clip((v - .58) / .40, 0, 1)[..., None]
    ramp = ramp * ramp * (3 - 2 * ramp)
    final = arr * (1 - ramp) + GROUND * ramp
    Image.fromarray(final.astype("uint8"), "RGB").save(os.path.join(HERE, "autumn_scene.png"), optimize=True)


def recolour_logo():
    """Keeps the logo's drawing and gives it autumn colours."""
    src = Image.open(os.path.join(LOGO_DIR, "msme_certifetch_logo.png")).convert("RGBA").resize((512, 512), Image.LANCZOS)
    a = np.asarray(src, float)
    rgb, alpha = a[..., :3], a[..., 3:]
    white = (rgb.min(axis=2, keepdims=True) / 255) ** 1.2
    y, x = np.mgrid[0:512, 0:512] / 511.
    t = ((x + y) / 2)[..., None]
    stops = [(0.0, (38, 84, 56)), (.42, (92, 124, 58)), (.66, (222, 140, 34)), (1.0, (200, 66, 26))]
    tone = np.zeros_like(rgb)
    for i in range(len(stops) - 1):
        (t0, c0), (t1, c1) = stops[i], stops[i + 1]
        m = (t >= t0) & (t <= t1)
        k = (t - t0) / (t1 - t0)
        col = np.array(c0, float) + (np.array(c1, float) - np.array(c0, float)) * k
        tone = np.where(m, col, tone)
    out = np.concatenate([np.clip(255 * white + tone * (1 - white), 0, 255), alpha], axis=2).astype("uint8")
    logo = Image.fromarray(out, "RGBA")
    logo.save(os.path.join(HERE, "autumn_logo.png"), optimize=True)
    logo.save(os.path.join(HERE, "autumn_icon.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


if __name__ == "__main__":
    paint_scene()
    leaf(MAPLE, 96, (214, 62, 34), (150, 38, 36), 301).save(os.path.join(HERE, "leaf_1.png"))
    leaf(MAPLE, 96, (240, 170, 52), (216, 104, 28), 302).save(os.path.join(HERE, "leaf_2.png"))
    leaf(BEECH, 96, (232, 118, 34), (190, 62, 30), 303).save(os.path.join(HERE, "leaf_3.png"))
    recolour_logo()
