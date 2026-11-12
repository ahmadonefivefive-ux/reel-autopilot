"""
Thumbnail generator.

Brand-locked to the video art: same parchment, charcoal ink and old-gold
accent as every scene, so the channel grid looks like one product.
1280x720 is the size YouTube expects for custom thumbnails.

Output: thumbnail.jpg
"""

import json
import os

from PIL import Image, ImageDraw

W, H = 1280, 720

CHARCOAL = (43, 33, 24)
CHARCOAL_SOFT = (66, 53, 40)
GOLD = (184, 134, 11)
PARCH_TOP = (245, 230, 200)
PARCH_BOT = (226, 206, 162)
PLATE = (28, 21, 15)

HISTORY_FILE = "uploaded_history.json"


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


def wrap_title(title, max_chars):
    words = title.upper().split()
    lines, current = [], ""
    for word in words:
        candidate = (current + " " + word).strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:3]


def make_thumbnail(title, out_path="thumbnail.jpg"):
    img = parchment()
    draw = ImageDraw.Draw(img)

    # double frame: charcoal outer, gold inner
    draw.rectangle([18, 18, W - 18, H - 18], outline=CHARCOAL, width=8)
    draw.rectangle([38, 38, W - 38, H - 38], outline=GOLD, width=3)

    # top-left kicker
    kicker = get_font(30)
    draw.text((70, 62), "FORGOTTEN  EMPIRES", font=kicker, fill=CHARCOAL_SOFT)
    ep = episode_number()
    ep_text = f"EPISODE  {ep:02d}"
    ep_w = draw.textlength(ep_text, font=kicker)
    draw.text((W - 70 - ep_w, 62), ep_text, font=kicker, fill=GOLD)

    # title block, vertically centred, shrunk until it fits the frame
    lines = wrap_title(title, 20)
    size = 132
    while size > 56:
        font = get_font(size)
        if max(draw.textlength(line, font=font) for line in lines) <= W - 180:
            break
        size -= 6
    font = get_font(size)

    heights = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        heights.append(bbox[3] - bbox[1])
    total = sum(heights) + int(size * 0.18) * (len(lines) - 1)
    y = (H - total) // 2 - 10

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = max(70, (W - text_w) // 2)
        # hard ink shadow, then the ink itself
        draw.text((x + 5, y + 5), line, font=font, fill=PARCH_BOT)
        draw.text((x, y), line, font=font, fill=CHARCOAL)
        y += (bbox[3] - bbox[1]) + int(size * 0.18)

    # gold rule under the title
    draw.rectangle([70, H - 132, 70 + 190, H - 122], fill=GOLD)
    tagline = get_font(28, bold=False)
    draw.text((70, H - 104), "ONE FORGOTTEN EMPIRE, EVERY DAY", font=tagline, fill=CHARCOAL_SOFT)

    img.save(out_path, quality=95)
    return out_path


def main():
    with open("script.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    title = data["title"]
    print(f"Generating thumbnail for: {title}")
    make_thumbnail(title)
    print("Saved to thumbnail.jpg")


if __name__ == "__main__":
    main()