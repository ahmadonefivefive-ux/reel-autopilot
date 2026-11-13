"""
Long-form script writer (6-10 minute episodes).

Picks the next topic from longform_topics.json (strict list order, never a
topic already used), asks Gemini for a chaptered documentary script, and
writes longform_script.json.

Same rules as the Shorts writer: real history only, no invented facts,
no generic fallback. If Gemini fails this stops instead of publishing junk.

Output: longform_script.json
"""

import json
import os
import sys
import time

import requests

import config
from topics_util import DuplicateChecker

SCRIPT_FILE = "longform_script.json"
POOL_FILE = "longform_topics.json"
USED_FILE = "longform_used.json"
HISTORY_FILE = "longform_history.json"

GEMINI_MODELS = ["gemini-3.6-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]

ALLOWED_DRAWS = [
    "horse", "horse_ride", "battle", "wall", "sail", "map", "crown",
    "pyramid", "palm", "arch", "book", "lamp", "coin", "fall",
    "crowd", "campaignmap", "flag", "banner",
]

PROMPT_TEMPLATE = """You are writing a long-form YouTube history documentary for the channel
"Forgotten Empires". Episode topic:

"{topic}"

TARGET: a 6-10 minute narration (about 950-1450 spoken words), chaptered.

Structure:
- 5 to 8 CHAPTERS. Each chapter is a real stage of the story (rise, turning
  point, crisis, consequence), in chronological order.
- 26 to 40 SCENES spread across those chapters. Each scene is one visual beat:
  25-45 spoken words. When all scene texts are read in order they must flow as
  one continuous, natural narration - no repetition, no headings read aloud.
- Scene 1 is the HOOK: a startling fact, a number, or a question. Never open
  with "Welcome", "In this video", "Today we will learn" or "Back in the day".
- The final scene gives the payoff and then loops back to the idea in the hook,
  without repeating the same words.

Historical rules:
- STRICT ACCURACY. Only well-documented events, names, dates and numbers.
  If historians disagree, say so in one short clause or leave it out.
- No invented quotes. If you quote someone, it must be a documented quote.
- No modern moralising, no glorifying violence, respectful of every figure.
- Include at least 3 concrete details per chapter: a date, a place, a price,
  a distance, a name, an object, a smell.

Style: cinematic documentary, short sentences, calm authority, spoken aloud.

For each scene choose "draw" from EXACTLY this list:
horse, horse_ride, battle, wall, sail, map, crown, pyramid, palm, arch,
book, lamp, coin, fall, crowd, campaignmap, flag, banner

Scene-picking guide:
- Large armies, sieges, battle lines -> "battle" or "wall".
- Early Islamic conquests / Rashidun and Umayyad campaigns -> "campaignmap".
- Routes, trade, geography, strategy -> "map".
- Defeat, death, collapse -> "fall".
- Learning, libraries, law, religion, administration -> "book" or "lamp".
- Trade, wealth, tribute -> "coin". Kingship, dynasty -> "crown".

Each scene needs:
- "chapter": the chapter number it belongs to (1-based).
- "label": 2-6 words in CAPS, a headline that carries the story with the sound
  OFF. e.g. "THE CITY THAT PAID", "40,000 MEN", "HE DIED AT 32".
- "text": the narration for this scene.

Each chapter needs:
- "title": 2-5 words, CAPS-friendly, e.g. "THE BOY KING".
- "summary": one short line (not read aloud) describing the chapter.

Also return:
- "title": under 90 characters, curiosity-driven, truthful. No clickbait lies.
- "description": ONE sentence hook, no hashtags (the uploader adds them).
- "tags": 8-12 short search terms.

Return ONLY this JSON, no other text:
{{
  "title": "...",
  "description": "...",
  "tags": ["...", "..."],
  "chapters": [
    {{"title": "...", "summary": "..."}}
  ],
  "scenes": [
    {{"chapter": 1, "draw": "battle", "label": "THE CITY THAT PAID", "text": "..."}}
  ]
}}
"""


def load_list(path):
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def history_topics():
    return [
        str(item.get("topic", "")).strip()
        for item in load_list(HISTORY_FILE)
        if isinstance(item, dict) and item.get("topic")
    ]


def choose_topic():
    pool = [str(t).strip() for t in load_list(POOL_FILE) if str(t).strip()]
    used = [str(t).strip() for t in load_list(USED_FILE) if str(t).strip()]
    checker = DuplicateChecker(used + history_topics())

    if not pool:
        sys.exit(f"{POOL_FILE} is empty - add long-form topics.")

    for topic in pool:
        if not checker.is_duplicate(topic):
            return topic

    sys.exit(
        "Every long-form topic in the pool is used. Add new topics to "
        f"{POOL_FILE} before the next run."
    )


def call_gemini(prompt):
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "maxOutputTokens": 16384,
            "temperature": 0.9,
        },
    }
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": config.GEMINI_API_KEY,
    }

    last_error = None
    for model in GEMINI_MODELS:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent"
        )
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=180)
            resp.raise_for_status()
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            last_error = e
            print(f"  [!] {model} failed: {e}")
            time.sleep(3)

    raise last_error


def parse_json(text):
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Gemini did not return a JSON object.")
    return json.loads(text[start:end + 1])


def validate(data):
    for key in ("title", "description"):
        if not data.get(key):
            raise ValueError(f"Gemini response is missing '{key}'.")

    title = " ".join(str(data["title"]).split()).replace("<", "").replace(">", "")
    data["title"] = title[:100].strip()

    chapters = data.get("chapters")
    if not isinstance(chapters, list) or not (4 <= len(chapters) <= 8):
        raise ValueError("Gemini must return 4-8 chapters.")

    clean_chapters = []
    for i, chapter in enumerate(chapters, 1):
        if not isinstance(chapter, dict):
            raise ValueError(f"Chapter {i} is not an object.")
        name = " ".join(str(chapter.get("title", "")).split()).upper()
        if not name:
            raise ValueError(f"Chapter {i} has no title.")
        clean_chapters.append({
            "title": name[:48],
            "summary": " ".join(str(chapter.get("summary", "")).split())[:200],
        })
    data["chapters"] = clean_chapters

    scenes = data.get("scenes")
    if not isinstance(scenes, list) or not (20 <= len(scenes) <= 48):
        raise ValueError("Gemini must return 20-48 scenes.")

    allowed = {d.lower() for d in ALLOWED_DRAWS}
    total_words = 0
    for i, scene in enumerate(scenes):
        draw = str(scene.get("draw", "")).strip().lower()
        if draw not in allowed:
            draw = "banner"
        scene["draw"] = draw

        label = " ".join(str(scene.get("label", "HISTORY")).split()).upper()
        scene["label"] = label[:40] or "HISTORY"

        text = " ".join(str(scene.get("text", "")).split())
        if not text:
            raise ValueError(f"Scene {i} has no text.")
        scene["text"] = text
        total_words += len(text.split())

        try:
            chapter = int(scene.get("chapter", 1))
        except (TypeError, ValueError):
            chapter = 1
        scene["chapter"] = min(max(1, chapter), len(clean_chapters))

    if total_words < config.LF_MIN_WORDS or total_words > config.LF_MAX_WORDS + 250:
        raise ValueError(
            f"Scene texts total {total_words} words - need "
            f"{config.LF_MIN_WORDS}-{config.LF_MAX_WORDS + 250}."
        )

    # Every chapter must own at least two scenes, otherwise the chapter list is
    # noise and YouTube will reject the timestamps.
    counts = {}
    for scene in scenes:
        counts[scene["chapter"]] = counts.get(scene["chapter"], 0) + 1
    for number in range(1, len(clean_chapters) + 1):
        if counts.get(number, 0) < 2:
            raise ValueError(f"Chapter {number} has fewer than 2 scenes.")

    data["scenes"] = scenes
    data["script"] = " ".join(scene["text"] for scene in scenes)
    data["word_count"] = total_words

    description = str(data["description"]).strip()
    data["description"] = description

    tags = data.get("tags") or []
    if not isinstance(tags, list):
        tags = []
    data["tags"] = [str(t).strip() for t in tags if str(t).strip()][:12]
    return data


def main():
    if not config.GEMINI_API_KEY or config.GEMINI_API_KEY.startswith("PASTE_"):
        sys.exit(
            "GEMINI_API_KEY is not set. Add it in GitHub: "
            "Settings -> Secrets and variables -> Actions."
        )

    topic = choose_topic()
    print(f"Writing long-form script for: {topic}")

    prompt = PROMPT_TEMPLATE.format(topic=topic)
    result = None
    last_error = None

    for attempt in range(3):
        try:
            raw = call_gemini(prompt)
            result = validate(parse_json(raw))
            break
        except Exception as e:
            last_error = e
            print(f"  [!] Attempt {attempt + 1} failed: {e}")
            if attempt < 2:
                time.sleep(5 * (attempt + 1))

    if result is None:
        sys.exit(
            f"Gemini failed 3 times ({last_error}). "
            "Refusing to publish a script that does not match the topic."
        )

    result["source_topic"] = topic
    result["used_fallback"] = False
    result["format"] = "longform"

    with open(SCRIPT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    words = result["word_count"]
    print("\nTitle:", result["title"])
    print(f"Chapters: {len(result['chapters'])} | Scenes: {len(result['scenes'])} | Words: {words}")
    print(f"Estimated runtime: {words / 150:.1f} min at 150 wpm")
    print(f"\nSaved to {SCRIPT_FILE}")


if __name__ == "__main__":
    main()