"""
Voiceover generator.

Uses edge-tts first (free, good quality) and saves word-level timings so
captions can be synced to the voice. Falls back to gTTS if edge-tts fails.
"""

import asyncio
import json
import os
import subprocess
import sys

import config

OUTPUT_FILE = "voiceover.mp3"
BOUNDARIES_FILE = "word_boundaries.json"


def load_text():
    with open("script.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    for key in ("script", "text", "voiceover", "narration"):
        if data.get(key):
            return data[key]
    sys.exit(f"No script text found in script.json. Keys: {list(data.keys())}")


async def edge_voiceover(text):
    import edge_tts

    communicate = edge_tts.Communicate(
        text,
        config.EDGE_TTS_VOICE,
        rate=config.EDGE_TTS_RATE,
    )

    boundaries = []
    with open(OUTPUT_FILE, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                # edge-tts uses 100-nanosecond units
                boundaries.append({
                    "text": chunk["text"],
                    "start": chunk["offset"] / 10_000_000,
                    "duration": chunk["duration"] / 10_000_000,
                })

    if not boundaries:
        raise RuntimeError("edge-tts returned no word timings.")

    with open(BOUNDARIES_FILE, "w", encoding="utf-8") as f:
        json.dump(boundaries, f, indent=2, ensure_ascii=False)


def gtts_voiceover(text):
    from gtts import gTTS

    raw = "voiceover_raw.mp3"
    gTTS(text=text, lang="en", tld="com").save(raw)
    subprocess.run(
        ["ffmpeg", "-y", "-i", raw, "-filter:a", f"atempo={config.GTTS_SPEED}", OUTPUT_FILE],
        check=True,
    )
    # gTTS has no word timings, so captions fall back to estimated timing.
    if os.path.exists(BOUNDARIES_FILE):
        os.remove(BOUNDARIES_FILE)


def check_audio():
    if not os.path.exists(OUTPUT_FILE) or os.path.getsize(OUTPUT_FILE) < 1000:
        raise RuntimeError("Voiceover file is missing or empty.")


def main():
    text = load_text()

    if os.path.exists(BOUNDARIES_FILE):
        os.remove(BOUNDARIES_FILE)

    print("Generating voiceover...")
    try:
        asyncio.run(edge_voiceover(text))
        check_audio()
        print("  [+] Voiceover made with edge-tts.")
        return
    except Exception as e:
        print(f"  [!] edge-tts failed: {e}")
        print("  [i] Switching to gTTS...")

    try:
        gtts_voiceover(text)
        check_audio()
        print("  [+] Voiceover made with gTTS.")
    except Exception as e:
        sys.exit(f"Voiceover failed: {e}")


if __name__ == "__main__":
    main()
