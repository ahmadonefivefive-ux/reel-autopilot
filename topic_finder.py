"""
Topic finder for the history Shorts channel (history stories).

Guarantees:
  - Never picks a topic that exactly or closely matches used_topics.json.
  - Records the chosen topic immediately, so a crash cannot cause a repeat.
  - Uses a large curated pool first, then Gemini (free tier), then a small
    offline generator. If every source is exhausted it STOPS instead of
    uploading a duplicate.

Output: topics.json
Updates: used_topics.json, generated_topics.json
"""

import json
import os
import random
import re
import sys
import time
from datetime import datetime, timezone

import requests

from topics_util import DuplicateChecker

GENERATED_TOPICS_FILE = "generated_topics.json"
USED_TOPICS_FILE = "used_topics.json"
TOPIC_POOL_FILE = "topic_pool.json"
HISTORY_FILE = "uploaded_history.json"

LOW_POOL_THRESHOLD = 12
GEMINI_BATCH_SIZE = 40
GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest"]

# Last-resort offline topics. These are only used if the curated pool,
# generated pool, and Gemini are all empty.
PEOPLE = [
    "Alexander the Great", "Salahuddin Ayubi", "Tariq ibn Ziyad",
    "Mehmed the Conqueror", "Suleiman the Magnificent", "Genghis Khan",
    "Julius Caesar", "Cleopatra", "Hannibal", "Ibn Sina", "Ibn Battuta",
    "Mansa Musa", "Fatima al-Fihri", "Harun al-Rashid", "Khalid ibn al-Walid",
    "Razia Sultana", "Spartacus", "Joan of Arc", "Timur", "Charlemagne",
]

STORIES = [
    "built the largest empire", "never lost a single battle",
    "changed the map of the world", "took an impossible city",
    "was betrayed at the worst moment", "made a decision that shocked history",
    "turned a defeat into a legend", "ruled longer than anyone expected",
    "was ahead of their time", "left a mystery historians still debate",
]

EMPIRES = [
    "the Roman Empire", "the Ottoman Empire", "the Mughal Empire",
    "the Abbasid Empire", "the Umayyad Empire", "the Mongol Empire",
    "the Persian Empire", "the Byzantine Empire", "the Egyptian Empire",
    "the Mali Empire", "Islamic Spain", "the Aztec Empire",
]


def load_list(path):
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [str(x).strip() for x in data if str(x).strip()]
        print(f"  [!] {path} is not a JSON list - ignoring it.")
    except Exception as e:
        print(f"  [!] Could not read {path}: {e}")
    return []


def save_list(path, items):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)


def load_history_topics():
    """Second safety net: if used_topics.json was lost, the upload history
    still tells us which topics have already been published."""
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [
                str(item.get("topic", "")).strip()
                for item in data
                if isinstance(item, dict) and item.get("topic")
            ]
    except Exception as e:
        print(f"  [!] Could not read {HISTORY_FILE}: {e}")
    return []


def record_used(topic):
    used = load_list(USED_TOPICS_FILE)
    checker = DuplicateChecker(used + load_history_topics())
    if checker.is_duplicate(topic):
        print(f"  [!] Refusing to record a duplicate: {topic}")
        return
    used.append(topic)
    save_list(USED_TOPICS_FILE, used)
    print(f"  [+] Recorded topic: {topic}")


def offline_topics():
    out = [f"How {person} {story}" for person in PEOPLE for story in random.sample(STORIES, 3)]
    out += [f"How {empire} rose and fell" for empire in EMPIRES]
    out += [f"Why {empire} mattered" for empire in EMPIRES]
    random.shuffle(out)
    return out


def generate_with_gemini(avoid):
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key or api_key.startswith("PASTE_"):
        print("  [!] GEMINI_API_KEY is missing - skipping Gemini.")
        return []

    prompt = (
        f"Generate {GEMINI_BATCH_SIZE} short, curiosity-driven world history "
        f"topics for 35-45 second YouTube Shorts aimed at a US general "
        f"audience. Style examples: 'How Salahuddin took back Jerusalem', "
        f"'Why Alexander the Great turned back from India', "
        f"'How Mehmed II took Constantinople at 21'. Cover ancient empires, "
        f"Alexander the Great and ancient Greece, Muslim leaders and the "
        f"Islamic golden age, the Ottoman and Mughal empires, Rome, Egypt, "
        f"China, the Mongols, famous battles, and historical mysteries. "
        f"Every topic must be clearly different from the others, "
        f"historically accurate, and safe for a general audience. "
        f"Do NOT repeat, reword, or closely resemble any of these "
        f"already-used topics: {avoid}. "
        f"Reply with ONLY a JSON array of {GEMINI_BATCH_SIZE} plain strings."
    )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}

    for model in GEMINI_MODELS:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent"
        )
        for attempt in range(3):
            try:
                resp = requests.post(url, json=body, headers=headers, timeout=45)
                if resp.status_code in (429, 500, 502, 503, 504):
                    wait = 5 * (2 ** attempt)
                    print(f"  [!] {model} returned {resp.status_code} - retrying in {wait}s")
                    time.sleep(wait)
                    continue
                if resp.status_code != 200:
                    print(f"  [!] {model} error {resp.status_code}: {resp.text[:200]}")
                    break

                text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
                topics = json.loads(text)
                if isinstance(topics, list):
                    cleaned = [str(t).strip() for t in topics if str(t).strip()]
                    if cleaned:
                        print(f"  [+] Gemini ({model}) returned {len(cleaned)} topics.")
                        return cleaned
                print(f"  [!] {model} returned unusable output.")
                break
            except Exception as e:
                print(f"  [!] {model} attempt {attempt + 1} failed: {e}")
                time.sleep(3)
        print(f"  [i] Moving on from {model}...")
    return []


def main():
    print("Finding a fresh history topic...\n")

    used = load_list(USED_TOPICS_FILE)
    generated = load_list(GENERATED_TOPICS_FILE)
    curated = load_list(TOPIC_POOL_FILE)
    history_topics = load_history_topics()

    checker = DuplicateChecker(used + history_topics)
    candidates = curated + generated
    available = [t for t in candidates if not checker.is_duplicate(t)]

    print(
        f"  Used: {len(used)} | History: {len(history_topics)} | "
        f"Curated: {len(curated)} | Generated: {len(generated)} | "
        f"Available: {len(available)}"
    )

    source = "curated pool"

    if len(available) < LOW_POOL_THRESHOLD:
        print("\n  [i] Pool is low - asking Gemini for fresh topics...\n")
        avoid = used[-200:] + history_topics[-100:] + generated[-100:]
        new_topics = generate_with_gemini(avoid)

        accepted = []
        batch_checker = DuplicateChecker(used + history_topics + candidates)
        for t in new_topics:
            if not batch_checker.is_duplicate(t):
                accepted.append(t)
                batch_checker.add(t)

        if accepted:
            save_list(GENERATED_TOPICS_FILE, generated + accepted)
            available.extend(accepted)
            source = "gemini"
            print(f"  [+] Saved {len(accepted)} new topics for future runs.\n")

    if not available:
        print("  [!] Gemini gave nothing - using offline generator.\n")
        available = [t for t in offline_topics() if not checker.is_duplicate(t)]
        source = "offline generator"

    if not available:
        print("  [X] Every source is exhausted. Stopping instead of repeating a topic.")
        sys.exit(1)

    # A different run number gives a different pick even if state was lost.
    seed = os.environ.get("GITHUB_RUN_NUMBER") or str(int(time.time()))
    chosen = random.Random(seed).choice(available)

    record_used(chosen)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "audience": "USA",
        "niche": "history_stories",
        "topics": [{"topic": chosen, "source": source, "upvotes": 0, "url": ""}],
    }
    with open("topics.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nDone! Chosen topic: {chosen}  (from {source})")


if __name__ == "__main__":
    main()
