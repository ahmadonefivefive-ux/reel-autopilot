"""
Long-form thumbnail (1280x720).

Same brand as the Shorts thumbnail: parchment, charcoal ink, old gold.
Title on the left, one framed art stamp on the right so the long-form grid
row reads instantly as "the full story" version of the channel.

Output: longform_thumbnail.jpg
"""

import json
import os

from PIL import Image, ImageDraw

from stickman_art import render_scene

W, H = 1280, 720

CHARCOAL = (43, 33, 24)
CHARCOAL_SOFT = (66, 53, 40)
GOLD = (184, 134, 11)
TEAL = (43, 122, 127)
PARCH_TOP = (245, 230, 200)
PARCH_BOT = (226, 206, 162)

SCRIPT_FILE = "longform_script.json"
HISTORY_FILE = "longform_history.json"


def get_font(size, bold=True):
    candidates = [
        "C:/Windows/Fonts/impact.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    if not bold:
        candidates.insert(0, "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    from PIL import ImageFont
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def episode_number():
    if not os.path.exists(HISTORY_FILE):
        return 1
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        episodes = [d.get("episode") for d in data if isinstance(d.get("episode"), int)]
        return (max(episodes) if episodes else len(data)) + 1
    except Exception:
        return 1


def parchment():
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        color = tuple(
            int(PARCH_TOP[i] + (PARCH_BOT[i] - PARCH_TOP[i]) * t) for i in range(3)
        )
        draw.line([(0, y), (W, y)], fill=color)
    return img


def wrap(draw, text, font, max_width):
    words = text.upper().split()
    lines, current = [], ""
    for word in words:
        candidate = (current + " " + word).strip()
        if draw.textlength(candidate, font=font) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def shorten_for_thumb(title):
    """Thumbnails carry the hook, not the full title. Keep it punchy."""
    text = title.strip()
    if ":" in text:
        head = text.split(":")[0].strip()
        if len(head) >= 10:
            text = head
    if len(text) <= 62:
        return text
    cut = text[:62]
    if " " in cut:
        cut = cut[:cut.rfind(" ")]
    return cut.rstrip(" ,:;-")


def make_thumbnail(title, draw_kind="banner", out_path="longform_thumbnail.jpg"):
    img = parchment()
    d = ImageDraw.Draw(img)

    d.rectangle([18, 18, W - 18, H - 18], outline=CHARCOAL, width=8)
    d.rectangle([38, 38, W - 38, H - 38], outline=GOLD, width=3)

    kicker = get_font(28)
    d.text((70, 62), "FORGOTTEN  EMPIRES", font=kicker, fill=CHARCOAL_SOFT)
    ep_text = f"FULL  STORY  {episode_number():02d}"
    ep_w = d.textlength(ep_text, font=kicker)
    d.text((W - 70 - ep_w, 62), ep_text, font=kicker, fill=GOLD)

    # art stamp on the right, cropped to the drawn content
    art = render_scene(draw_kind, seed=97)
    art = art.crop((60, 372, 1020, 1332))
    stamp = 400
    art = art.resize((stamp, stamp), Image.LANCZOS)
    sx, sy = W - 70 - stamp, 120
    d.rectangle([sx - 7, sy - 7, sx + stamp + 7, sy + stamp + 7],
                fill=(196, 178, 142), outline=CHARCOAL, width=3)
    img.paste(art, (sx, sy))

    # title block on the left
    max_width = sx - 70 - 34
    title = shorten_for_thumb(title)
    size = 104
    while size > 44:
        font = get_font(size)
        lines = wrap(d, title, font, max_width)
        if len(lines) <= 4:
            break
        size -= 6
    font = get_font(size)
    lines = wrap(d, title, font, max_width)[:4]

    line_h = int(size * 1.1)
    block = line_h * len(lines)
    y = (H - block) // 2 - 24
    for line in lines:
        d.text((74, y + 4), line, font=font, fill=PARCH_BOT)
        d.text((70, y), line, font=font, fill=CHARCOAL)
        y += line_h

    d.rectangle([70, H - 104, 70 + 180, H - 94], fill=GOLD)
    tagline = get_font(26, bold=False)
    d.text((70, H - 78), "THE FULL STORY  \u00b7  NEW EPISODE EVERY SUNDAY",
           font=tagline, fill=TEAL)

    img.save(out_path, quality=94)
    return out_path


def main():
    with open(SCRIPT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    scenes = data.get("scenes") or []
    draw_kind = scenes[-1].get("draw", "banner") if scenes else "banner"
    print(f"Generating long-form thumbnail for: {data['title']}")
    make_thumbnail(data["title"], draw_kind)
    print("Saved to longform_thumbnail.jpg")


if __name__ == "__main__":
    main()