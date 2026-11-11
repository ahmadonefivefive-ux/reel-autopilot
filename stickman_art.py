"""
Scene doodles for the stickman history pipeline.

Every scene is drawn from scratch with PIL - no external assets, no licensing
issues, one consistent hand-drawn look. Each doodle is a function of
(draw, w, h) and returns a PIL Image in charcoal on parchment with a
subtle vignette and film grain.
"""

import math
import random

from PIL import Image, ImageDraw, ImageFilter

W, H = 1080, 1920

CHARCOAL = (43, 33, 24)
CHARCOAL_SOFT = (66, 53, 40)
ACCENT = (184, 134, 11)      # old gold
TEAL = (43, 122, 127)        # old teal
PARCH_TOP = (245, 230, 200)
PARCH_BOT = (232, 213, 168)
PLATE = (28, 21, 15)
PLATE_EDGE = (90, 74, 55)


def parchment(seed=7):
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        t = y / H
        r = int(PARCH_TOP[0] + (PARCH_BOT[0] - PARCH_TOP[0]) * t)
        g = int(PARCH_TOP[1] + (PARCH_BOT[1] - PARCH_TOP[1]) * t)
        b = int(PARCH_TOP[2] + (PARCH_BOT[2] - PARCH_TOP[2]) * t)
        for x in range(W):
            px[x, y] = (r, g, b)
    # grain
    rng = random.Random(seed)
    for _ in range(2600):
        x, y = rng.randrange(W), rng.randrange(H)
        v = rng.randrange(-18, 19)
        r, g, b = px[x, y]
        px[x, y] = (max(0, min(255, r + v)), max(0, min(255, g + v)), max(0, min(255, b + v)))
    # vignette corners
    ov = Image.new("L", (W, H), 0)
    od = ImageDraw.Draw(ov)
    od.ellipse([-W * 0.55, -H * 0.45, W * 1.55, H * 1.45], fill=0)
    for i in range(6):
        pass
    # cheap vignette: darken edges with a radial multi-box
    vig = Image.new("L", (W, H), 0)
    vd = ImageDraw.Draw(vig)
    for i, alpha in enumerate([60, 46, 34, 22, 12, 6]):
        pad = int(i * 10)
        vd.rectangle([0, 0, W, pad], fill=alpha)
        vd.rectangle([0, H - pad, W, H], fill=alpha)
        vd.rectangle([0, 0, pad, H], fill=alpha)
        vd.rectangle([W - pad, 0, W, H], fill=alpha)
    img = Image.composite(Image.new("RGB", (W, H), (20, 14, 9)), img, vig)
    return img


def frame_edge(img):
    d = ImageDraw.Draw(img)
    d.rectangle([26, 26, W - 26, H - 26], outline=CHARCOAL, width=14)
    d.rectangle([48, 48, W - 48, H - 48], outline=(120, 96, 70), width=3)
    return img


def stick(d, x, y, s, pose, stroke=13, color=CHARCOAL):
    """Draw a stick figure. (x, y) = hip point, s = scale."""
    hr = int(46 * s)             # head radius
    hip_y = y
    shoulder_y = y - int(150 * s)
    head_y = shoulder_y - int(hr * 1.5)
    # legs
    if pose == "standing":
        d.line([(x, hip_y), (x - int(60 * s), hip_y + int(190 * s))], fill=color, width=stroke)
        d.line([(x, hip_y), (x + int(60 * s), hip_y + int(190 * s))], fill=color, width=stroke)
    elif pose == "walking":
        d.line([(x, hip_y), (x - int(90 * s), hip_y + int(185 * s))], fill=color, width=stroke)
        d.line([(x, hip_y), (x + int(110 * s), hip_y + int(150 * s))], fill=color, width=stroke)
    elif pose == "fallen":
        d.line([(x - int(160 * s), hip_y), (x + int(150 * s), hip_y)], fill=color, width=stroke)
        d.line([(x - int(80 * s), hip_y), (x - int(130 * s), hip_y - int(90 * s))], fill=color, width=stroke)
        d.line([(x + int(40 * s), hip_y), (x + int(120 * s), hip_y - int(110 * s))], fill=color, width=stroke)
        d.ellipse([x + int(170 * s), hip_y - int(40 * s), x + int(170 * s) + hr * 2, hip_y - int(40 * s) + hr * 2], outline=color, width=stroke)
        return
    elif pose == "pointing":
        d.line([(x, hip_y), (x - int(55 * s), hip_y + int(190 * s))], fill=color, width=stroke)
        d.line([(x, hip_y), (x + int(70 * s), hip_y + int(185 * s))], fill=color, width=stroke)
    # torso
    d.line([(x, hip_y), (x, shoulder_y)], fill=color, width=stroke)
    # head
    d.ellipse([x - hr, head_y - hr, x + hr, head_y + hr], outline=color, width=stroke)
    # arms
    if pose == "standing":
        d.line([(x, shoulder_y), (x - int(80 * s), shoulder_y + int(115 * s))], fill=color, width=stroke)
        d.line([(x, shoulder_y), (x + int(80 * s), shoulder_y + int(115 * s))], fill=color, width=stroke)
    elif pose == "walking":
        d.line([(x, shoulder_y), (x - int(95 * s), shoulder_y + int(90 * s))], fill=color, width=stroke)
        d.line([(x, shoulder_y), (x + int(95 * s), shoulder_y + int(130 * s))], fill=color, width=stroke)
    elif pose == "sword":
        d.line([(x, shoulder_y), (x - int(85 * s), shoulder_y + int(120 * s))], fill=color, width=stroke)
        d.line([(x, shoulder_y), (x + int(125 * s), shoulder_y - int(150 * s))], fill=color, width=stroke)
        blade_top = (x + int(125 * s), shoulder_y - int(150 * s))
        d.line([blade_top, (blade_top[0] + int(95 * s), blade_top[1] - int(125 * s))], fill=color, width=stroke // 2 + 3)
    elif pose == "pointing":
        d.line([(x, shoulder_y), (x - int(85 * s), shoulder_y + int(120 * s))], fill=color, width=stroke)
        d.line([(x, shoulder_y), (x + int(160 * s), shoulder_y - int(60 * s))], fill=color, width=stroke)
    elif pose == "shield":
        d.line([(x, shoulder_y), (x - int(85 * s), shoulder_y + int(110 * s))], fill=color, width=stroke)
        d.line([(x, shoulder_y), (x + int(105 * s), shoulder_y + int(60 * s))], fill=color, width=stroke)
        d.pieslice([x + int(60 * s), shoulder_y - int(40 * s), x + int(220 * s), shoulder_y + int(160 * s)],
                   start=280, end=80, fill=TEAL, outline=color, width=stroke // 2 + 2)
    elif pose == "staff":
        d.line([(x, shoulder_y), (x - int(85 * s), shoulder_y + int(110 * s))], fill=color, width=stroke)
        d.line([(x, shoulder_y), (x + int(120 * s), shoulder_y + int(30 * s))], fill=color, width=stroke)
        d.line([(x + int(150 * s), shoulder_y - int(220 * s)), (x + int(150 * s), shoulder_y + int(190 * s))], fill=color, width=stroke // 2 + 3)
    return


def horse(d, x, y, s, color=CHARCOAL):
    stroke = 12
    # barrel (solid silhouette)
    d.ellipse([x - 180 * s, y - 105 * s, x + 110 * s, y + 80 * s], fill=color)
    # legs
    for lx, slant in [(-135, -20), (-70, -5), (15, 5), (85, 20)]:
        d.line([(x + lx * s, y + 60 * s), (x + (lx + slant) * s, y + 215 * s)], fill=color, width=stroke)
    # neck (solid tapered wedge)
    d.polygon([(x + 95 * s, y - 85 * s), (x + 205 * s, y - 225 * s),
               (x + 235 * s, y - 190 * s), (x + 125 * s, y - 30 * s)], fill=color)
    # head (long solid block with muzzle)
    d.polygon([(x + 195 * s, y - 240 * s), (x + 330 * s, y - 205 * s),
               (x + 345 * s, y - 155 * s), (x + 225 * s, y - 160 * s)], fill=color)
    # eye
    d.ellipse([x + 262 * s, y - 222 * s, x + 284 * s, y - 200 * s], fill=PARCH_TOP)
    # ear
    d.polygon([(x + 205 * s, y - 225 * s), (x + 225 * s, y - 262 * s), (x + 232 * s, y - 205 * s)], fill=color)
    # mane strip
    d.line([(x + 118 * s, y - 108 * s), (x + 212 * s, y - 218 * s)], fill=PARCH_TOP, width=8)


def doodle(img, kind):
    d = ImageDraw.Draw(img)
    cx = W // 2
    ground = 1240
    # ground line everywhere
    d.line([(80, ground), (W - 80, ground)], fill=CHARCOAL, width=10)
    d.line([(80, ground + 26), (W - 80, ground + 26)], fill=CHARCOAL_SOFT, width=4)

    if kind == "horse":
        horse(d, cx, ground, 1.15)
        stick(d, cx - 10, ground - 155, 0.82, "sword", stroke=10)

    elif kind == "horse_ride":
        horse(d, cx, ground, 1.15)
        stick(d, cx - 10, ground - 155, 0.78, "standing", stroke=10)

    elif kind == "battle":
        stick(d, cx - 250, ground, 1.0, "sword")
        stick(d, cx + 250, ground, 1.0, "sword")
        cx0, cy0 = cx, ground - 260
        for dx, dy in [(0, -1), (0.8, -0.6), (0.8, 0.6), (0, 1), (-0.8, 0.6), (-0.8, -0.6)]:
            d.line([(cx0, cy0), (cx0 + int(95 * dx), cy0 + int(95 * dy))], fill=ACCENT, width=8)

    elif kind == "wall":
        d.rectangle([cx - 330, ground - 420, cx + 330, ground], outline=CHARCOAL, width=13)
        for yy in range(ground - 420, ground, 70):
            d.line([(cx - 330, yy), (cx + 330, yy)], fill=CHARCOAL, width=7)
        for xx in range(cx - 330, cx + 330, 110):
            off = 0 if ((xx + ground) // 70) % 2 else 55
            d.line([(xx + off, ground - 420), (xx + off, ground)], fill=CHARCOAL, width=7)
        d.rectangle([cx - 60, ground - 150, cx + 60, ground], outline=CHARCOAL, width=11)
        stick(d, cx - 240, ground - 442, 0.52, "sword", stroke=7)

    elif kind == "sail":
        d.polygon([(cx - 330, ground), (cx + 330, ground), (cx + 200, ground - 120), (cx - 200, ground - 120)], outline=CHARCOAL, fill=PARCH_TOP, width=13)
        d.line([(cx, ground - 120), (cx, ground - 560)], fill=CHARCOAL, width=13)
        d.polygon([(cx + 12, ground - 545), (cx + 12, ground - 160), (cx + 235, ground - 160)], fill=CHARCOAL_SOFT, outline=CHARCOAL)
        for wy in (ground + 40, ground + 80):
            for xx in range(120, W - 120, 120):
                d.arc([xx, wy - 22, xx + 80, wy + 22], start=200, end=340, fill=TEAL, width=8)

    elif kind == "map":
        d.rounded_rectangle([cx - 400, ground - 560, cx + 400, ground - 40], radius=34, outline=CHARCOAL, width=11, fill=PARCH_TOP)
        d.line([(cx - 300, ground - 160), (cx - 80, ground - 380), (cx + 120, ground - 220), (cx + 330, ground - 470)], fill=CHARCOAL_SOFT, width=9)
        d.ellipse([cx - 340, ground - 200, cx - 260, ground - 120], outline=CHARCOAL, width=9)
        d.ellipse([cx + 260, ground - 520, cx + 340, ground - 440], outline=CHARCOAL, width=9)
        d.polygon([(cx + 330, ground - 470), (cx + 235, ground - 425), (cx + 300, ground - 380)], fill=ACCENT)

    elif kind == "crown":
        zigzag = [(cx - 260, ground), (cx - 260, ground - 260), (cx - 180, ground - 150), (cx - 90, ground - 380),
                  (cx, ground - 190), (cx + 90, ground - 380), (cx + 180, ground - 150), (cx + 260, ground - 260),
                  (cx + 260, ground)]
        d.polygon(zigzag, fill=ACCENT, outline=CHARCOAL)
        d.rectangle([cx - 260, ground, cx + 260, ground + 60], outline=CHARCOAL, fill=ACCENT, width=10)
        for dx in (-180, 0, 180):
            d.ellipse([cx + dx - 32, ground - 130, cx + dx + 32, ground - 66], fill=CHARCOAL)

    elif kind == "pyramid":
        d.polygon([(cx - 400, ground), (cx, ground - 520), (cx + 400, ground)], outline=CHARCOAL, width=13)
        for yy in range(ground - 80, ground - 500, -60):
            half = int((ground - yy) * 400 / 520)
            d.line([(cx - half, yy), (cx + half, yy)], fill=CHARCOAL, width=6)
        d.ellipse([cx + 300, 120, cx + 440, 260], outline=ACCENT, width=10)

    elif kind == "palm":
        d.line([(cx - 40, ground), (cx - 15, ground - 300), (cx - 45, ground - 640)], fill=CHARCOAL, width=26)
        for yy in (ground - 150, ground - 275, ground - 400, ground - 520):
            d.line([(cx - 66, yy), (cx + 14, yy)], fill=PARCH_TOP, width=7)
        crown = (cx - 45, ground - 640)
        for ang, ln in [(-155, 250), (-115, 315), (-62, 330), (-10, 290), (30, 250), (70, 185)]:
            a = math.radians(ang)
            ex, ey = crown[0] + math.cos(a) * ln, crown[1] + math.sin(a) * ln * 0.72
            d.line([crown, (ex, ey)], fill=CHARCOAL, width=23)
            d.line([(ex, ey), (ex, ey + 62)], fill=CHARCOAL, width=17)

    elif kind == "arch":
        for dx in (-260, 0, 260):
            d.rectangle([cx + dx - 130, ground - 460, cx + dx + 130, ground], outline=CHARCOAL, width=12)
            d.pieslice([cx + dx - 130, ground - 640, cx + dx + 130, ground - 300], start=180, end=360, outline=CHARCOAL, width=12)
        d.rectangle([cx - 450, ground - 640, cx + 450, ground - 540], fill=CHARCOAL_SOFT, outline=CHARCOAL)

    elif kind == "book":
        d.polygon([(cx - 300, ground - 60), (cx - 10, ground - 130), (cx - 10, ground - 430), (cx - 300, ground - 360)], fill=PARCH_TOP, outline=CHARCOAL, width=10)
        d.polygon([(cx + 300, ground - 60), (cx + 10, ground - 130), (cx + 10, ground - 430), (cx + 300, ground - 360)], fill=PARCH_TOP, outline=CHARCOAL, width=10)
        for dy in (0, 60, 120, 180):
            d.line([(cx - 260, ground - 140 - dy), (cx - 40, ground - 195 - dy)], fill=CHARCOAL_SOFT, width=6)
            d.line([(cx + 40, ground - 195 - dy), (cx + 260, ground - 140 - dy)], fill=CHARCOAL_SOFT, width=6)

    elif kind == "lamp":
        # oil lamp - the icon of the Golden Age of Islam
        d.ellipse([cx - 235, ground - 95, cx + 235, ground + 15], fill=ACCENT, outline=CHARCOAL, width=12)
        d.polygon([(cx + 195, ground - 70), (cx + 345, ground - 148), (cx + 205, ground + 12)], fill=ACCENT, outline=CHARCOAL)
        d.arc([cx - 140, ground - 275, cx + 140, ground - 85], start=202, end=338, fill=CHARCOAL, width=14)
        d.rectangle([cx - 95, ground + 8, cx + 95, ground + 52], fill=CHARCOAL)
        d.ellipse([cx - 45, ground + 40, cx + 45, ground + 66], fill=CHARCOAL)
        d.polygon([(cx + 330, ground - 160), (cx + 380, ground - 245), (cx + 385, ground - 140)], fill=ACCENT, outline=CHARCOAL)

    elif kind == "coin":
        d.ellipse([cx - 280, ground - 620, cx + 280, ground - 60], fill=ACCENT, outline=CHARCOAL, width=13)
        d.ellipse([cx - 200, ground - 540, cx + 200, ground - 140], outline=CHARCOAL, width=9)
        d.ellipse([cx - 60, ground - 420, cx + 60, ground - 300], fill=CHARCOAL)

    elif kind == "fall":
        d.line([(cx - 310, ground - 28), (cx + 55, ground - 28)], fill=CHARCOAL, width=13)
        d.ellipse([cx + 80, ground - 90, cx + 180, ground + 8], outline=CHARCOAL, width=11)
        d.line([(cx - 175, ground - 28), (cx - 258, ground - 148)], fill=CHARCOAL, width=10)
        d.line([(cx - 95, ground - 28), (cx - 132, ground - 158)], fill=CHARCOAL, width=10)
        d.line([(cx - 272, ground - 28), (cx - 345, ground + 145)], fill=CHARCOAL, width=10)
        d.line([(cx - 222, ground - 28), (cx - 228, ground + 152)], fill=CHARCOAL, width=10)

    elif kind == "crowd":
        for row, (n, y, s) in enumerate([(9, ground - 40, 0.42), (8, ground - 210, 0.55), (7, ground - 400, 0.7), (5, ground - 610, 0.9)]):
            offset = (row * 55) % (2000 // n)
            for i in range(n):
                x = int(110 + (W - 220) * (i + 0.5) / n + (offset - 60) * 0.3)
                hr = int(44 * s * 1.9)
                d.ellipse([x - hr, y - hr * 2, x + hr, y], outline=CHARCOAL, width=int(12 * s) + 2)
                d.arc([x - hr * 2, y, x + hr * 2, y + int(120 * s)], start=180, end=360, fill=CHARCOAL, width=int(12 * s) + 2)

    elif kind == "flag":
        d.line([(cx - 280, ground), (cx - 280, ground - 700)], fill=CHARCOAL, width=14)
        d.polygon([(cx - 280, ground - 700), (cx - 40, ground - 620), (cx - 180, ground - 460), (cx - 280, ground - 520)], fill=TEAL, outline=CHARCOAL)
        d.line([(cx - 160, ground), (cx + 260, ground)], fill=ACCENT, width=9)

    elif kind == "banner":
        d.rounded_rectangle([cx - 430, ground - 430, cx + 430, ground - 170], radius=60, outline=CHARCOAL, width=13, fill=ACCENT)
        d.polygon([(cx - 480, ground - 430), (cx - 430, ground - 430), (cx - 430, ground - 300)], fill=CHARCOAL_SOFT)
        d.polygon([(cx + 480, ground - 430), (cx + 430, ground - 430), (cx + 430, ground - 300)], fill=CHARCOAL_SOFT)

    else:  # fallback: hero standing with sun
        stick(d, cx, ground, 1.0, "standing")
        d.ellipse([cx + 180, 130, cx + 350, 300], outline=ACCENT, width=9)
    return img


def render_scene(kind, seed):
    img = parchment(seed=seed)
    img = doodle(img, kind)
    return frame_edge(img)
