"""
Thumbnail generator.

Uses the first frame of the finished video as a blurred background, then
draws a short, bold title on top. 1280x720 is the size YouTube expects for
custom thumbnails.

Output: thumbnail.jpg
"""

import json
import os
import subprocess

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1280, 720


def get_font(size):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def background():
    if os.path.exists("final_video.mp4"):
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", "final_video.mp4", "-frames:v", "1", "thumb_bg.jpg"],
                check=True,
                capture_output=True,
            )
            img = Image.open("thumb_bg.jpg").convert("RGB").resize((W, H))
            img = img.filter(ImageFilter.GaussianBlur(12))
            dark = Image.new("RGB", (W, H), (0, 0, 0))
            return Image.blend(img, dark, 0.55)
        except Exception as e:
            print(f"  [!] Could not use video frame for background: {e}")

    img = Image.new("RGB", (W, H), (10, 10, 18))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        shade = int(18 + 45 * (y / H))
        draw.line([(0, y), (W, y)], fill=(shade, shade // 3, 120))
    return img


def wrap_title(title, max_chars=18):
    words = title.upper().split()
    lines = []
    current = ""
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
    return lines[:4]


def make_thumbnail(title, out_path="thumbnail.jpg"):
    img = background()
    draw = ImageDraw.Draw(img)

    lines = wrap_title(title)
    font_size = 110 if len(lines) <= 2 else 86
    font = get_font(font_size)
    line_height = int(font_size * 1.15)
    total_height = line_height * len(lines)
    y = max(60, (H - total_height) // 2)

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = (W - text_w) // 2

        for dx in range(-4, 5):
            for dy in range(-4, 5):
                if dx or dy:
                    draw.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill=(255, 255, 255))
        y += line_height

    draw.rectangle([0, H - 16, W, H], fill=(37, 99, 235))
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
