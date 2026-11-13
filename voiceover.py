"""
Voiceover generator.

Uses edge-tts first (free, good quality) and saves word-level timings so
captions can be synced to the voice. Falls back to gTTS if edge-tts fails.

Usage:
    python voiceover.py                       # Shorts defaults
    python voiceover.py <script.json> <out.mp3> <boundaries.json>
"""

import asyncio
import json
import os
import subprocess
import sys

import config

OUTPUT_FILE = "voiceover.mp3"
BOUNDARIES_FILE = "word_boundaries.json"


def load_text(path="script.json"):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for key in ("script", "text", "voiceover", "narration"):
        if data.get(key):
            return data[key]
    sys.exit(f"No script text found in {path}. Keys: {list(data.keys())}")


async def edge_voiceover(text, out_file=OUTPUT_FILE, boundaries_file=BOUNDARIES_FILE):
    import edge_tts

    # edge-tts >= 7.0 changed the default boundary type from WordBoundary to
    # SentenceBoundary, which silently dropped all word timings in earlier runs.
    # Request word-level boundaries explicitly; tolerate older versions.
    try:
        communicate = edge_tts.Communicate(
            text,
            config.EDGE_TTS_VOICE,
            rate=config.EDGE_TTS_RATE,
            boundary="WordBoundary",
        )
    except TypeError:
        communicate = edge_tts.Communicate(
            text,
            config.EDGE_TTS_VOICE,
            rate=config.EDGE_TTS_RATE,
        )

    boundaries = []
    with open(out_file, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                # edge-tts uses 100-nanosecond units
                boundaries.append({
                    "text": chunk["text"],
                    "start": chunk["offset"] / 10_000_000,
                    "duration": chunk["duration"] / 10_000_000,
                })

    if not boundaries:
        raise RuntimeError("edge-tts returned no word timings.")

    with open(boundaries_file, "w", encoding="utf-8") as f:
        json.dump(boundaries, f, indent=2, ensure_ascii=False)


def gtts_voiceover(text, out_file=OUTPUT_FILE, boundaries_file=BOUNDARIES_FILE):
    from gtts import gTTS

    raw = "voiceover_raw.mp3"
    gTTS(text=text, lang="en", tld="com").save(raw)
    subprocess.run(
        ["ffmpeg", "-y", "-i", raw, "-filter:a", f"atempo={config.GTTS_SPEED}", out_file],
        check=True,
    )
    # gTTS has no word timings, so captions fall back to estimated timing.
    if os.path.exists(boundaries_file):
        os.remove(boundaries_file)


def check_audio(out_file=OUTPUT_FILE):
    if not os.path.exists(out_file) or os.path.getsize(out_file) < 1000:
        raise RuntimeError("Voiceover file is missing or empty.")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    script_path = argv[0] if len(argv) > 0 else "script.json"
    out_file = argv[1] if len(argv) > 1 else OUTPUT_FILE
    boundaries_file = argv[2] if len(argv) > 2 else BOUNDARIES_FILE

    text = load_text(script_path)

    if os.path.exists(boundaries_file):
        os.remove(boundaries_file)

    print("Generating voiceover...")
    # Retry edge-tts a few times; the service occasionally drops boundaries.
    for attempt in range(3):
        try:
            asyncio.run(edge_voiceover(text, out_file, boundaries_file))
            check_audio(out_file)
            if os.path.exists(boundaries_file):
                print("  [+] Voiceover made with edge-tts.")
                return
            raise RuntimeError("edge-tts returned no word timings.")
        except Exception as e:
            print(f"  [!] edge-tts attempt {attempt + 1} failed: {e}")
            if attempt < 2:
                import time
                time.sleep(3 * (attempt + 1))

    print("  [i] Switching to gTTS...")
    try:
        gtts_voiceover(text, out_file, boundaries_file)
        check_audio(out_file)
        print("  [+] Voiceover made with gTTS.")
    except Exception as e:
        sys.exit(f"Voiceover failed: {e}")


if __name__ == "__main__":
    main()