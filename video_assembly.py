"""
Video assembly.

Improvements over the old version:
  - Uses several different Pexels clips instead of one clip looping.
  - Picks 1080x1920-ish files, never a huge 4K download.
  - Builds captions from edge-tts word timings, so they match the voice.
  - Burns in a clean, large caption style.
  - Optional royalty-free background music at music/background.mp3.
  - Forces YouTube-safe output: yuv420p, 30fps, faststart.

Output: final_video.mp4
"""

import json
import os
import random
import re
import subprocess
import sys

import requests

import config
from topics_util import STOPWORDS, normalize

CLIPS_DIR = "clips"
QUERY_STOPWORDS = STOPWORDS | {
    "generate", "generates", "produce", "produces", "create", "creates",
    "high", "low", "voltage", "explain", "explained", "happen", "happens",
    "turn", "turns", "make", "makes",
}


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


def search_query(topic):
    words = [
        w for w in normalize(topic).split()
        if w not in QUERY_STOPWORDS and len(w) > 2
    ]
    return " ".join(words[:4]) or topic


def pexels_search(query, per_page=20):
    headers = {"Authorization": config.PEXELS_API_KEY}
    params = {"query": query, "orientation": "portrait", "per_page": per_page}
    resp = requests.get(
        "https://api.pexels.com/videos/search",
        headers=headers,
        params=params,
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json().get("videos", [])


def commons_search(query, per_page=12):
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": query + " filetype:video",
        "gsrnamespace": "6",
        "gsrlimit": str(per_page),
        "prop": "imageinfo",
        "iiprop": "url|size|mime",
    }
    resp = requests.get(
        "https://commons.wikimedia.org/w/api.php",
        params=params,
        headers={"User-Agent": "ForgottenEmpiresBot/1.0 (GitHub Actions)"},
        timeout=30,
    )
    resp.raise_for_status()
    pages = (resp.json().get("query") or {}).get("pages") or {}
    out = []
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        url, mime, size = info.get("url"), info.get("mime", ""), int(info.get("size") or 0)
        if not url:
            continue
        if not (mime.startswith("video/") or mime == "application/ogg"):
            continue
        if size > 80_000_000:
            continue  # skip huge originals
        out.append({"link": url, "duration": 10})
    return out


def fetch_commons_clips(topic, count):
    os.makedirs(CLIPS_DIR, exist_ok=True)
    for query in (search_query(topic), "ancient history", "battle", "empire"):
        hits = commons_search(query)
        if not hits:
            continue
        random.shuffle(hits)
        clips = []
        for hit in hits:
            if len(clips) >= count:
                break
            path = os.path.join(CLIPS_DIR, f"clip_{len(clips)}.mp4")
            try:
                download(hit["link"], path)
                if os.path.getsize(path) < 10_000:
                    raise RuntimeError("downloaded file is too small")
                clips.append(path)
                print(f"  + {path} (commons)")
            except Exception as e:
                print(f"  [!] Skipped a Commons clip: {e}")
                if os.path.exists(path):
                    os.remove(path)
        if clips:
            return clips
    raise RuntimeError(
        "Wikimedia Commons gave no usable clips for this topic. "
        "Add a free PEXELS_API_KEY (pexels.com/api) for much better results."
    )


def pick_file(video):
    files = [f for f in video.get("video_files", []) if f.get("link")]
    usable = []
    for f in files:
        try:
            height = int(f.get("height") or 0)
        except Exception:
            height = 0
        if 720 <= height <= 1920:
            usable.append((abs(height - 1920), f))
    if not usable:
        for f in files:
            try:
                height = int(f.get("height") or 0)
            except Exception:
                height = 0
            usable.append((abs(height - 1920), f))
    if not usable:
        return None
    usable.sort(key=lambda item: item[0])
    return usable[0][1]


def download(url, path):
    with requests.get(url, stream=True, timeout=120) as resp:
        resp.raise_for_status()
        with open(path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 256):
                if chunk:
                    f.write(chunk)


def fetch_clips(topic, count):
    os.makedirs(CLIPS_DIR, exist_ok=True)
    query = search_query(topic)
    print(f"  Pexels query: {query}")

    videos = pexels_search(query)
    if not videos:
        print("  [!] No match - trying 'abstract background'.")
        videos = pexels_search("abstract background")
    if not videos:
        raise RuntimeError("Pexels returned no videos.")

    # Prefer clips that are long enough to be useful.
    longer = [v for v in videos if float(v.get("duration") or 0) >= 5]
    if longer:
        videos = longer

    random.shuffle(videos)
    clips = []

    for video in videos:
        if len(clips) >= count:
            break
        file_info = pick_file(video)
        if not file_info:
            continue
        path = os.path.join(CLIPS_DIR, f"clip_{len(clips)}.mp4")
        try:
            download(file_info["link"], path)
            if os.path.getsize(path) < 10_000:
                raise RuntimeError("downloaded file is too small")
            clips.append(path)
            print(f"  + {path} ({file_info.get('height')}p)")
        except Exception as e:
            print(f"  [!] Skipped a clip: {e}")
            if os.path.exists(path):
                os.remove(path)

    if not clips:
        raise RuntimeError("Could not download any usable clip from Pexels.")
    return clips


def normalize_clip(src, dst, seconds):
    run([
        "ffmpeg", "-y", "-i", src, "-t", f"{seconds:.2f}",
        "-vf",
        f"scale={config.VIDEO_WIDTH}:{config.VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={config.VIDEO_WIDTH}:{config.VIDEO_HEIGHT},"
        f"fps={config.FPS},setsar=1",
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-pix_fmt", "yuv420p", dst,
    ])


def build_stock(clips, total_duration):
    segment_seconds = total_duration / len(clips) + 0.6
    segments = []
    for i, clip in enumerate(clips):
        dst = f"seg_{i}.mp4"
        normalize_clip(clip, dst, segment_seconds)
        segments.append(dst)

    with open("segments.txt", "w", encoding="utf-8") as f:
        for segment in segments:
            f.write(f"file '{os.path.abspath(segment)}'\n")

    run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", "segments.txt",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-pix_fmt", "yuv420p", "-r", str(config.FPS),
        "stock_loop.mp4",
    ])
    return "stock_loop.mp4"


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
        groups = [
            " ".join(words[i:i + size])
            for i in range(0, len(words), size)
        ]
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


def assemble(stock_path, audio_path, captions_path, out_path="final_video.mp4"):
    duration = audio_duration(audio_path)
    music_path = os.path.join("music", "background.mp3")

    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", stock_path,
        "-i", audio_path,
    ]    video_style = (
        f"{config.GRADE_FILTER},"
        f"subtitles={captions_path},"
        f"drawtext=text='{config.WATERMARK}':fontfile={config.WATERMARK_FONT}"
        f":fontsize={config.WATERMARK_FONTSIZE}:fontcolor=white@0.85"
        f":borderw=2:bordercolor=black@0.55"
        f":x=(w-text_w)/2:y={config.WATERMARK_Y}"
    )

    if os.path.exists(music_path):
        print("  Adding background music.")
        cmd += ["-stream_loop", "-1", "-i", music_path]
        filter_complex = (
            f"[0:v]{video_style}[v];"
            f"[1:a]volume=1.0[a1];"
            f"[2:a]volume={config.MUSIC_VOLUME}[a2];"
            f"[a1][a2]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]"
        )
    else:
        filter_complex = (
            f"[0:v]{video_style}[v];"
            f"[1:a]anull[aout]"
        )
    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "[aout]",
        "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
        "-pix_fmt", "yuv420p", "-r", str(config.FPS),
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        "-shortest", out_path,
    ]
    run(cmd)
    return out_path


def main():
    with open("script.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    topic = data["source_topic"]
    script_text = data["script"]

    duration = audio_duration("voiceover.mp3")
    print(f"  Voiceover duration: {duration:.1f}s")

    if config.PEXELS_API_KEY:
        clips = fetch_clips(topic, config.CLIP_COUNT)
    else:
        print("  No PEXELS_API_KEY - falling back to Wikimedia Commons (public domain).")
        clips = fetch_commons_clips(topic, config.CLIP_COUNT)
    stock = build_stock(clips, duration)

    captions = build_captions(script_text, duration)
    assemble(stock, "voiceover.mp3", captions)

    print("Done! Saved to final_video.mp4")


if __name__ == "__main__":
    main()
