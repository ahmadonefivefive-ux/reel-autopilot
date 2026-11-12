"""
Script writer for the history Shorts channel.

Reads topics.json, asks Gemini for a 35-45 second history story script, and
writes script.json.

IMPORTANT: If Gemini fails, this exits with an error instead of uploading
one of a handful of generic fallback scripts. That old behaviour was a major
cause of "why does it keep making the same video?".
"""

import json
import re
import sys
import time

import requests

import config

GEMINI_MODELS = ["gemini-3.6-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]

ALLOWED_DRAWS = [
    "horse", "horse_ride", "battle", "wall", "sail", "map", "crown",
    "pyramid", "palm", "arch", "book", "lamp", "coin", "fall",
    "crowd", "campaignmap", "flag", "banner",
]

PROMPT_TEMPLATE = """You are a top YouTube Shorts history storyteller. Write a script for this topic:

"{topic}"

Rules:
- TOTAL 90-115 spoken words, told as 5 to 7 SCENES. Each scene is one beat of the story.
- First scene is the HOOK: a surprising fact, a number, or a direct question.
  Never start with "Hey guys", "In this video", "Back in the day", or "Today we will learn".
- Tell the story with 2-3 concrete facts. Use at least one date or number.
- Include ONE "bravery line": a specific, human, non-textbook detail that most
  people have never heard - a smell, a price, a betrayal, a mistake, a small
  object. It must be real and documented. This is the line viewers repeat.
- STRICT ACCURACY: only real, well-documented history. No invented events,
  numbers, or quotes. If a detail is debated by historians, say so briefly
  or leave it out.
- End with a clear payoff: the surprising outcome or the reason it mattered.
- Make the last sentence loop back to the first line's idea, so a replay feels
  seamless instead of sudden. Do not repeat the exact words.
- Cinematic documentary tone. Short sentences. Respectful of all figures.
- Title: maximum 60 characters, curiosity-driven, and truthful.
- Description: ONE sentence only. No hashtags (the uploader adds them).
- tags: 5-8 short search terms.

for each scene choose "draw" from EXACTLY this list:
horse, horse_ride, battle, wall, sail, map, crown, pyramid, palm, arch,
book, lamp, coin, fall, crowd, campaignmap, flag, banner

Scene-picking guide:
- For a LARGE ARMY, a siege or a battle line, use "battle" or "wall".
- For stories about the early Islamic conquests or the Rashidun caliphs,
  use "campaignmap" (a stylized map of Arabia with the Muslim heartland,
  mosque and conquest cities).
- For tricks and geography use "map".
- For defeat or death use "fall".

Each scene also needs:
- "label": 1-4 words in CAPS for a title plate shown on the scene. It must
  carry the story with the sound OFF, like a headline: "HE WAS 12",
  "20,000 VS 47,000", "THE CITY FELL", "ONE MAN SAID NO". Never a vague
  place name on its own.
- "text": the voiceover words for this scene. Concatenating all scene texts
  must read as one natural script.

Return ONLY this JSON, with no other text:
{{
  "title": "...",
  "description": "...",
  "tags": ["...", "..."],
  "scenes": [
    {{"draw": "horse", "label": "GAUGAMELA 331 BC", "text": "..."}},
    {{"draw": "map", "label": "THE ROUTE EAST", "text": "..."}}
  ]
}}
"""


def load_next_topic():
    with open("topics.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    if not data.get("topics"):
        raise ValueError("No topics found. Run topic_finder.py first.")
    return data["topics"][0]


def call_gemini(prompt):
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
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
            resp = requests.post(url, json=body, headers=headers, timeout=90)
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

    title = " ".join(str(data["title"]).split())
    for ch in "<>":
        title = title.replace(ch, "")
    data["title"] = title[:100].strip()

    scenes = data.get("scenes")
    if not isinstance(scenes, list) or len(scenes) < 4 or len(scenes) > 8:
        raise ValueError("Gemini must return 4-8 scenes, each with draw/label/text.")

    allowed = {d.lower() for d in ALLOWED_DRAWS}
    total_words = 0
    for i, scene in enumerate(scenes):
        draw = str(scene.get("draw", "")).strip().lower()
        if draw not in allowed:
            draw = "banner"
        scene["draw"] = draw

        label = " ".join(str(scene.get("label", "HISTORY")).split()).upper()
        scene["label"] = label[:28] or "HISTORY"

        text = " ".join(str(scene.get("text", "")).split())
        if not text:
            raise ValueError(f"Scene {i} has no text.")
        scene["text"] = text
        total_words += len(text.split())

    if total_words < 60 or total_words > 160:
        raise ValueError(f"Scene texts total {total_words} words - need 60-160.")

    data["scenes"] = scenes
    data["script"] = " ".join(scene["text"] for scene in scenes)

    description = str(data["description"]).strip()
    if "#Shorts" not in description and "#shorts" not in description.lower():
        description = description.rstrip() + " #Shorts"
    data["description"] = description

    tags = data.get("tags") or []
    if not isinstance(tags, list):
        tags = []
    data["tags"] = [str(t).strip() for t in tags if str(t).strip()][:10]
    return data


def main():
    if not config.GEMINI_API_KEY or config.GEMINI_API_KEY.startswith("PASTE_"):
        sys.exit(
            "GEMINI_API_KEY is not set. Add it in GitHub: "
            "Settings -> Secrets and variables -> Actions."
        )

    topic = load_next_topic()
    print(f"Writing script for: {topic['topic']}")

    prompt = PROMPT_TEMPLATE.format(topic=topic["topic"])
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
            "Refusing to upload a generic fallback video that does not match the topic."
        )

    result["source_topic"] = topic["topic"]
    result["source_url"] = topic.get("url", "")
    result["used_fallback"] = False

    with open("script.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print("\nTitle:", result["title"])
    print("\nScript:\n", result["script"])
    print("\nSaved to script.json")


if __name__ == "__main__":
    main()
