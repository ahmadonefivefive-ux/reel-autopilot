"""
Long-form video assembly (1920x1080, 6-10 minutes).

Same art engine and brand as the Shorts, laid out as a wide documentary page:
parchment canvas, framed art panel on the left, chapter tag and headline on
the right, karaoke captions along the bottom.

Reads:  longform_script.json, longform_voiceover.mp3, longform_boundaries.json
Writes: longform_video.mp4, longform_chapters.json, longform_captions.ass
"""

import json
import os
import random
import re
import subprocess
import sys

from PIL import Image, ImageDraw

import config
from stickman import (
    LABEL_FONT,
    SMALL_FONT,
    ass_time,
    clamp_entry,
    clean_caption_text,
    karaoke_line,
    load_font,
)
from stickman_art import render_scene

W = config.LF_VIDEO_WIDTH
H = config.LF_VIDEO_HEIGHT
FPS = config.LF_FPS

SCRIPT_FILE = "longform_script.json"
AUDIO_FILE = "longform_voiceover.mp3"
BOUNDARIES_FILE = "longform_boundaries.json"
CAPTIONS_FILE = "longform_captions.ass"
CHAPTERS_FILE = "longform_chapters.json"
OUTPUT_FILE = "longform_video.mp4"

CHARCOAL = (43, 33, 24)
CHARCOAL_SOFT = (66, 53, 40)
GOLD = (184, 134, 11)
TEAL = (43, 122, 127)
PARCH_TOP = (245, 230, 200)
PARCH_BOT = (226, 206, 162)
PLATE = (28, 21, 15)

MIN_SCENE_SECONDS = 4.0
FADE = 0.5

_BASE = None


def run(cmd):
    print("  $", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True)


def audio_duration(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True,
    )
    value = result.stdout.strip()
    if result.returncode != 0 or not value:
        raise RuntimeError(f"Could not read the duration of {path}.")
    return float(value)


# ------------------------------------------------------------------ artwork
def wide_parchment():
    """One wide parchment sheet, built once and reused for every plate."""
    global _BASE
    if _BASE is not None:
        return _BASE.copy()

    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        color = tuple(
            int(PARCH_TOP[i] + (PARCH_BOT[i] - PARCH_TOP[i]) * t) for i in range(3)
        )
        d.line([(0, y), (W, y)], fill=color)

    rng = random.Random(11)
    px = img.load()
    for _ in range(9000):
        x, y = rng.randrange(W), rng.randrange(H)
        v = rng.randrange(-14, 15)
        r, g, b = px[x, y]
        px[x, y] = (
            max(0, min(255, r + v)),
            max(0, min(255, g + v)),
            max(0, min(255, b + v)),
        )

    # soft dark edges, same idea as the Shorts vignette
    vig = Image.new("L", (W, H), 0)
    vd = ImageDraw.Draw(vig)
    for i, alpha in enumerate([46, 34, 24, 16, 9]):
        pad = int(i * 14)
        vd.rectangle([0, 0, W, pad], fill=alpha)
        vd.rectangle([0, H - pad, W, H], fill=alpha)
        vd.rectangle([0, 0, pad, H], fill=alpha)
        vd.rectangle([W - pad, 0, W, H], fill=alpha)
    img = Image.composite(Image.new("RGB", (W, H), (20, 14, 9)), img, vig)

    _BASE = img
    return img.copy()


def wrap_text(draw, text, font, max_width):
    words = text.split()
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


def fit_headline(draw, text, max_width, max_lines=3):
    for size in range(116, 54, -6):
        font = load_font(size, LABEL_FONT)
        lines = wrap_text(draw, text, font, max_width)
        if len(lines) <= max_lines:
            return font, lines
    font = load_font(54, LABEL_FONT)
    return font, wrap_text(draw, text, font, max_width)[:max_lines]


def build_plate(scene, chapter, index, total, is_last):
    img = wide_parchment()
    d = ImageDraw.Draw(img)

    # double frame, identical to the Shorts brand
    d.rectangle([22, 22, W - 22, H - 22], outline=CHARCOAL, width=9)
    d.rectangle([42, 42, W - 42, H - 42], outline=GOLD, width=3)

    # art panel: crop the empty top/bottom of the portrait scene, then scale
    panel_h = 930
    art = render_scene(scene.get("draw", "banner"), seed=41 + index * 13)
    art = art.crop((52, 320, 1028, 1480))
    panel_w = int(panel_h * art.width / art.height)
    art = art.resize((panel_w, panel_h), Image.LANCZOS)
    ax, ay = 96, 75
    d.rectangle([ax - 9, ay - 9, ax + panel_w + 9, ay + panel_h + 9], fill=(196, 178, 142))
    d.rectangle([ax - 9, ay - 9, ax + panel_w + 9, ay + panel_h + 9], outline=CHARCOAL, width=4)
    img.paste(art, (ax, ay))

    # gold divider between the art and the words
    divider_x = ax + panel_w + 62
    d.rectangle([divider_x, 170, divider_x + 3, 910], fill=GOLD)

    col_x = divider_x + 42
    col_w = 1830 - col_x

    chapter_title = (chapter or {}).get("title", "")
    chapter_summary = (chapter or {}).get("summary", "")
    kicker_font = load_font(31, SMALL_FONT)
    if is_last:
        kicker = "THANKS  FOR  WATCHING"
    elif chapter_title:
        kicker = f"CHAPTER {scene.get('chapter', 1)}  \u00b7  {chapter_title}"
    else:
        kicker = "FORGOTTEN  EMPIRES"
    d.text((col_x, 205), kicker[:64], font=kicker_font, fill=CHARCOAL_SOFT)

    if is_last:
        big = load_font(104, LABEL_FONT)
        d.text((col_x + 3, 336), "SUBSCRIBE", font=big, fill=PARCH_BOT)
        d.text((col_x, 333), "SUBSCRIBE", font=big, fill=GOLD)
        sub = load_font(38, LABEL_FONT)
        d.text((col_x, 470), "THE FULL STORY EVERY SUNDAY", font=sub, fill=CHARCOAL)
        small = load_font(28, SMALL_FONT)
        d.text((col_x, 528), "NEW EPISODE EVERY WEEK  \u00b7  6-10 MINUTES", font=small, fill=TEAL)
    else:
        label = str(scene.get("label", "HISTORY")).upper()
        font, lines = fit_headline(d, label, col_w)
        line_h = int(font.size * 1.12)
        summary_font = load_font(30, SMALL_FONT)
        summary_lines = (
            wrap_text(d, chapter_summary, summary_font, col_w)[:2] if chapter_summary else []
        )
        headline_block = line_h * len(lines)
        summary_block = (26 + 24 + 44 * len(summary_lines)) if summary_lines else 0
        y = 320 + max(0, (560 - headline_block - summary_block) // 2)
        for line in lines:
            d.text((col_x + 4, y + 4), line, font=font, fill=PARCH_BOT)
            d.text((col_x, y), line, font=font, fill=CHARCOAL)
            y += line_h

        if summary_lines:
            sy = y + 26
            d.rectangle([col_x, sy, col_x + 120, sy + 4], fill=GOLD)
            sy += 24
            for line in summary_lines:
                d.text((col_x, sy), line, font=summary_font, fill=CHARCOAL_SOFT)
                sy += 44

    # footer: progress + brand mark
    small = load_font(26, SMALL_FONT)
    progress = f"SCENE {index + 1:02d} / {total:02d}"
    pw = d.textlength(progress, font=small)
    d.text((1830 - pw, 962), progress, font=small, fill=GOLD)
    mark = "F O R G O T T E N   E M P I R E S"
    mw = d.textlength(mark, font=small)
    d.text((1830 - mw, 1002), mark, font=small, fill=(122, 100, 76))

    return img


def render_plates(scenes, chapters, out_prefix="lf_scene"):
    paths = []
    last = len(scenes) - 1
    for i, scene in enumerate(scenes):
        number = int(scene.get("chapter", 1))
        chapter = chapters[number - 1] if 0 <= number - 1 < len(chapters) else {}
        img = build_plate(scene, chapter, i, len(scenes), is_last=(i == last))
        path = f"{out_prefix}_{i:02d}.png"
        img.save(path)
        paths.append(path)
        print(f"  + {path}  [{scene.get('draw')}] ch{number} {scene.get('label')}")
    return paths


# ----------------------------------------------------------------- captions
def build_captions(script_text, duration, out_path=CAPTIONS_FILE):
    boundaries = load_boundaries_file()
    entries = []

    if boundaries:
        chunk = []
        for word in boundaries:
            chunk.append(word)
            text = " ".join(w["text"] for w in chunk)
            if len(chunk) >= config.LF_WORDS_PER_LINE or re.search(r"[.!?,;:]$", text):
                start = chunk[0]["start"]
                end = chunk[-1]["start"] + chunk[-1]["duration"] + 0.10
                entries.append((*clamp_entry(start, end, duration), karaoke_line(chunk)))
                chunk = []
        if chunk:
            start = chunk[0]["start"]
            end = chunk[-1]["start"] + chunk[-1]["duration"] + 0.10
            entries.append((*clamp_entry(start, end, duration), karaoke_line(chunk)))
    else:
        words = script_text.split()
        size = config.LF_WORDS_PER_LINE
        groups = [" ".join(words[i:i + size]) for i in range(0, len(words), size)]
        per = duration / max(len(groups), 1)
        entries = [
            (*clamp_entry(i * per, (i + 1) * per, duration), group)
            for i, group in enumerate(groups)
        ]

    for i in range(len(entries) - 1):
        start, end, text = entries[i]
        next_start = entries[i + 1][0]
        entries[i] = (start, min(end, max(start + 0.10, next_start - 0.02)), text)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,{config.LF_CAPTION_FONT_SIZE},&H000B86B8,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,1,2,120,120,{config.LF_CAPTION_MARGIN_V},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(header)
        for start, end, text in entries:
            safe = str(text).replace("\n", " ").strip()
            if safe:
                f.write(
                    f"Dialogue: 0,{ass_time(start)},{ass_time(end)},"
                    f"Default,,0,0,0,,{safe}\n"
                )
    return out_path


def load_boundaries_file():
    if not os.path.exists(BOUNDARIES_FILE):
        return []
    try:
        with open(BOUNDARIES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


# ---------------------------------------------------------------- animation
def scene_spans(scenes, duration):
    words = [max(1, len(str(s.get("text", " ")).split())) for s in scenes]
    total = sum(words)
    spans, t = [], 0.0
    for w in words:
        d = duration * w / total
        spans.append((t, t + d))
        t += d
    return spans


def make_segment(image_path, dst, seconds, zoom_in):
    frames = max(1, int(round(seconds * config.LF_FPS)))
    z_expr = "min(zoom+0.00018,1.05)" if zoom_in else "max(1.05-(on*0.00018),1.0)"
    fade_start = max(0.0, seconds - FADE)
    vf = (
        f"zoompan=z='{z_expr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={frames}:s={W}x{H}:fps={config.LF_FPS},"
        f"fps={config.LF_FPS},setsar=1,"
        f"fade=t=in:st=0:d={FADE},fade=t=out:st={fade_start:.2f}:d={FADE},"
        f"format=yuv420p"
    )
    run([
        "ffmpeg", "-y", "-loop", "1", "-i", image_path, "-t", f"{seconds:.2f}",
        "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-pix_fmt", "yuv420p", dst,
    ])
    return dst


def plain_segment(image_path, dst, seconds):
    fade_start = max(0.0, seconds - FADE)
    run([
        "ffmpeg", "-y", "-loop", "1", "-i", image_path, "-t", f"{seconds:.2f}",
        "-vf",
        f"scale={W}:{H},fps={config.LF_FPS},setsar=1,"
        f"fade=t=in:st=0:d={FADE},fade=t=out:st={fade_start:.2f}:d={FADE},"
        f"format=yuv420p",
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-pix_fmt", "yuv420p", dst,
    ])
    return dst


def concat_segments(segments, out_path="lf_body.mp4"):
    list_path = "lf_segments.txt"
    with open(list_path, "w", encoding="utf-8") as f:
        for seg in segments:
            f.write(f"file '{os.path.abspath(seg)}'\n")
    try:
        run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path,
            "-c", "copy", out_path,
        ])
        return out_path
    except subprocess.CalledProcessError:
        print("  [!] Stream-copy concat failed - re-encoding instead.")
        run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-r", str(config.LF_FPS), out_path,
        ])
        return out_path


def assemble(body_video, audio_path, captions_path, out_path=OUTPUT_FILE):
    duration = audio_duration(audio_path)
    music_path = os.path.join("music", "background.mp3")

    def build_cmd(video_filter):
        cmd = ["ffmpeg", "-y", "-i", body_video, "-i", audio_path]
        if os.path.exists(music_path):
            print("  Adding background music.")
            cmd += ["-stream_loop", "-1", "-i", music_path]
            fc = (
                f"[0:v]{video_filter}[v];"
                f"[1:a]volume=1.0[a1];"
                f"[2:a]volume={config.LF_MUSIC_VOLUME}[a2];"
                f"[a1][a2]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
                f"loudnorm=I=-14:TP=-1.5:LRA=11[aout]"
            )
        else:
            fc = (
                f"[0:v]{video_filter}[v];"
                f"[1:a]loudnorm=I=-14:TP=-1.5:LRA=11[aout]"
            )
        cmd += [
            "-filter_complex", fc,
            "-map", "[v]", "-map", "[aout]",
            "-t", f"{duration:.3f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
            "-pix_fmt", "yuv420p", "-r", str(config.LF_FPS),
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            "-shortest", out_path,
        ]
        return cmd

    try:
        run(build_cmd(f"subtitles={captions_path}"))
    except subprocess.CalledProcessError:
        print("  [!] Caption burn failed - assembling without captions this time.")
        run(build_cmd("null"))
    return out_path


# ----------------------------------------------------------------- chapters
def build_chapters(scenes, spans, chapters):
    starts = {}
    for i, scene in enumerate(scenes):
        number = int(scene.get("chapter", 1))
        if number not in starts:
            starts[number] = spans[i][0]

    ordered = sorted(starts.items())
    out = []
    for number, start in ordered:
        title = chapters[number - 1]["title"] if number - 1 < len(chapters) else f"PART {number}"
        out.append({"title": title, "start": int(start)})
    if out:
        out[0]["start"] = 0

    with open(CHAPTERS_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    return out


def main():
    with open(SCRIPT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    scenes = data.get("scenes") or []
    if not scenes:
        sys.exit(f"{SCRIPT_FILE} has no scenes - regenerate the script first.")

    if not os.path.exists(AUDIO_FILE):
        sys.exit(f"{AUDIO_FILE} is missing - run the voiceover step first.")

    duration = audio_duration(AUDIO_FILE)
    print(f"  Runtime: {duration / 60:.1f} min | Scenes: {len(scenes)}")

    spans = scene_spans(scenes, duration)
    durations = [max(MIN_SCENE_SECONDS, end - start) for start, end in spans]

    print("  Rendering plates...")
    images = render_plates(scenes, data.get("chapters") or [])

    print("  Animating scenes...")
    segments = []
    for i, (img, d) in enumerate(zip(images, durations)):
        seg = f"lf_seg_{i:02d}.mp4"
        try:
            make_segment(img, seg, d, zoom_in=(i % 2 == 0))
        except subprocess.CalledProcessError:
            print(f"  [!] Zoom-pan failed for scene {i} - using a static frame.")
            plain_segment(img, seg, d)
        segments.append(seg)

    body = concat_segments(segments)

    captions = build_captions(data["script"], duration)
    chapters = build_chapters(scenes, spans, data.get("chapters") or [])
    assemble(body, AUDIO_FILE, captions)

    print(f"  Chapters: {len(chapters)}")
    for chapter in chapters:
        m, s = divmod(chapter["start"], 60)
        print(f"    {m:02d}:{s:02d}  {chapter['title']}")
    print(f"Done! Saved to {OUTPUT_FILE} ({duration / 60:.1f} min)")


if __name__ == "__main__":
    main()