"""
Stickman scenes pipeline.

Reads script.json (with a "scenes" list), renders each scene with the PIL
library (stickman_art.py), animates each scene with a gentle zoom, chains
them with fade transitions, and muxes the edge-tts voiceover.

Output: final_video.mp4 (1080x1920, 30fps)
"""

import json
import os
import re
import subprocess
import sys

import config
from stickman_art import render_scene, W, H, PLATE, PLATE_EDGE

CAP_FONT = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/impact.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]
LABEL_FONT = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/impact.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]
SMALL_FONT = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def load_font(size, candidates):
    from PIL import ImageFont
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def run(cmd):
    print("  $", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True)


def audio_duration(path):
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        capture_output=True,
        text=True,
    )
    value = result.stdout.strip()
    if result.returncode != 0 or not value:
        raise RuntimeError(f"Could not read the duration of {path}.")
    return float(value)


def render_scenes(scenes):
    from PIL import ImageDraw
    paths = []
    last = len(scenes) - 1
    for i, scene in enumerate(scenes):
        img = render_scene(scene.get("draw", "banner"), seed=41 + i * 13)
        d = ImageDraw.Draw(img)

        # End card on the final scene only: one line, no clutter.
        if i == last:
            cta = load_font(40, LABEL_FONT)
            text = "SUBSCRIBE  \u2022  NEW EMPIRE DAILY"
            tw = d.textlength(text, font=cta)
            pad = 34
            x0 = (W - tw) / 2 - pad
            x1 = (W + tw) / 2 + pad
            d.rounded_rectangle([x0, 1150, x1, 1250], radius=50,
                                fill=PLATE, outline=PLATE_EDGE, width=5)
            d.text(((W - tw) / 2, 1172), text, font=cta, fill=(212, 175, 55))

        y0, plate_h = 1420, 150
        d.rounded_rectangle([80, y0, W - 80, y0 + plate_h], radius=44,
                            fill=PLATE, outline=PLATE_EDGE, width=6)
        label = str(scene.get("label", "HISTORY")).upper()[:26]
        size = 96
        font = load_font(size, LABEL_FONT)
        while font.size > 42 and d.textlength(label, font=font) > W - 260:
            font = load_font(font.size - 8, LABEL_FONT)
        tw = d.textlength(label, font=font)
        d.text(((W - tw) / 2, y0 + 26), label, font=font, fill=(255, 255, 255))
        small = load_font(28, SMALL_FONT)
        mark = "F O R G O T T E N   E M P I R E S"
        mw = d.textlength(mark, font=small)
        d.text(((W - mw) / 2, 1670), mark, font=small, fill=(122, 100, 76))
        path = f"scene_{i:02d}.png"
        img.save(path)
        paths.append(path)
        print(f"  + {path}  [{scene.get('draw')}] {label}")
    return paths


def load_boundaries():
    if not os.path.exists("word_boundaries.json"):
        return []
    try:
        with open("word_boundaries.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def ass_time(seconds):
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02}:{s:05.2f}"


def clamp_entry(start, end, duration):
    start = max(0.0, min(start, duration - 0.10))
    end = max(start + 0.10, min(end, duration - 0.05))
    return start, end


def build_captions(script_text, duration, out_path="captions.ass"):
    boundaries = load_boundaries()
    entries = []

    if boundaries:
        chunk = []
        for word in boundaries:
            chunk.append(word)
            text = " ".join(w["text"] for w in chunk)
            if len(chunk) >= 4 or re.search(r"[.!?,;:]$", text):
                start = chunk[0]["start"]
                end = chunk[-1]["start"] + chunk[-1]["duration"] + 0.10
                entries.append((*clamp_entry(start, end, duration), text))
                chunk = []
        if chunk:
            start = chunk[0]["start"]
            end = chunk[-1]["start"] + chunk[-1]["duration"] + 0.10
            entries.append(
                (*clamp_entry(start, end, duration), " ".join(w["text"] for w in chunk))
            )
    else:
        words = script_text.split()
        size = 4
        groups = [" ".join(words[i:i + size]) for i in range(0, len(words), size)]
        per = duration / max(len(groups), 1)
        entries = [
            (*clamp_entry(i * per, (i + 1) * per, duration), group)
            for i, group in enumerate(groups)
        ]

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {config.VIDEO_WIDTH}
PlayResY: {config.VIDEO_HEIGHT}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,{config.CAPTION_FONT_SIZE},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,0,2,70,70,{config.CAPTION_MARGIN_V},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(header)
        for start, end, text in entries:
            safe = (
                text.replace("\\", "")
                .replace("{", "")
                .replace("}", "")
                .replace("\n", " ")
                .strip()
            )
            if safe:
                f.write(
                    f"Dialogue: 0,{ass_time(start)},{ass_time(end)},"
                    f"Default,,0,0,0,,{safe}\n"
                )
    return out_path


def scene_spans(scenes, duration):
    """Allocate share of the voiceover to each scene, by word count."""
    words = [max(1, len(str(s.get("text", " ")).split())) for s in scenes]
    total = sum(words)
    spans, t = [], 0.0
    for w in words:
        d = duration * w / total
        spans.append((t, t + d))
        t += d
    return spans


def make_segment(image_path, dst, seconds, zoom_in):
    frames = max(1, int(round(seconds * config.FPS)))
    z_expr = "min(zoom+0.0016,1.22)" if zoom_in else "max(1.22-(on*0.0016),1.0)"
    vf = (
        f"scale={config.VIDEO_WIDTH}:{config.VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={config.VIDEO_WIDTH}:{config.VIDEO_HEIGHT},"
        f"zoompan=z='{z_expr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={config.VIDEO_WIDTH}x{config.VIDEO_HEIGHT}:fps={config.FPS},"
        f"fps={config.FPS},setsar=1"
    )
    run([
        "ffmpeg", "-y", "-loop", "1", "-i", image_path, "-t", f"{seconds:.2f}",
        "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-pix_fmt", "yuv420p", dst,
    ])
    return dst


def plain_segment(image_path, dst, seconds):
    run([
        "ffmpeg", "-y", "-loop", "1", "-i", image_path, "-t", f"{seconds:.2f}",
        "-vf",
        f"scale={config.VIDEO_WIDTH}:{config.VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={config.VIDEO_WIDTH}:{config.VIDEO_HEIGHT},"
        f"fps={config.FPS},setsar=1",
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-pix_fmt", "yuv420p", dst,
    ])
    return dst


def xfade_concat(segments, durations, out_path):
    n = len(segments)
    if n == 1:
        run(["ffmpeg", "-y", "-i", segments[0], "-c:v", "libx264",
             "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
             "-r", str(config.FPS), out_path])
        return out_path
    inputs = []
    for s in segments:
        inputs += ["-i", s]
    chain = []
    cumulative = 0.0
    prev = "[0:v]"
    for i in range(1, n):
        cumulative += durations[i - 1]
        offset = max(0.1, cumulative - 0.7 * i)
        out_label = "[vout]" if i == n - 1 else f"[v{i}]"
        chain.append(f"{prev}[{i}:v]xfade=transition=fade:duration=0.7:offset={offset:.2f}{out_label}")
        prev = out_label
    filter_complex = ";".join(chain)
    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-pix_fmt", "yuv420p", "-r", str(config.FPS),
        out_path,
    ]
    try:
        run(cmd)
        return out_path
    except subprocess.CalledProcessError:
        print("  [!] Fade transitions failed - using plain concat instead.")
        with open("segments.txt", "w", encoding="utf-8") as f:
            for seg in segments:
                f.write(f"file '{os.path.abspath(seg)}'\n")
        run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "segments.txt",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-r", str(config.FPS), out_path,
        ])
        return out_path


def assemble(stock_video, audio_path, captions_path, out_path="final_video.mp4"):
    duration = audio_duration(audio_path)
    music_path = os.path.join("music", "background.mp3")

    def build_cmd(video_filter):
        cmd = ["ffmpeg", "-y", "-i", stock_video, "-i", audio_path]
        if os.path.exists(music_path):
            print("  Adding background music.")
            cmd += ["-stream_loop", "-1", "-i", music_path]
            fc = (
                f"[0:v]{video_filter}[v];"
                f"[1:a]volume=1.0[a1];"
                f"[2:a]volume={config.MUSIC_VOLUME}[a2];"
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
            "-pix_fmt", "yuv420p", "-r", str(config.FPS),
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


def main():
    with open("script.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    topic = data["source_topic"]
    script_text = data["script"]
    scenes = data.get("scenes") or []

    duration = audio_duration("voiceover.mp3")
    print(f"  Voiceover duration: {duration:.1f}s | Scenes: {len(scenes)}")

    if not scenes:
        sys.exit("script.json has no scenes - regenerate the script with scene data.")

    spans = scene_spans(scenes, duration)

    print("  Rendering scenes...")
    images = render_scenes(scenes)
    durations = [max(2.2, end - start) for start, end in spans]

    segments = []
    for i, (img, d) in enumerate(zip(images, durations)):
        seg = f"seg_{i:02d}.mp4"
        try:
            make_segment(img, seg, d, zoom_in=(i % 2 == 0))
        except subprocess.CalledProcessError:
            print(f"  [!] Zoom-pan failed for scene {i} - using static frame.")
            plain_segment(img, seg, d)
        segments.append(seg)

    stock = "stock_scenes.mp4"
    xfade_concat(segments, durations, stock)

    captions = build_captions(script_text, duration)
    assemble(stock, "voiceover.mp3", captions)

    print("Done! Saved to final_video.mp4")


if __name__ == "__main__":
    main()
