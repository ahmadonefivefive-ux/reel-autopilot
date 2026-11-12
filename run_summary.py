"""
Prints a Markdown summary of the last run for the GitHub Actions job page.

Free alternative to a notification service: every run leaves a readable
report on the Actions tab, including the last uploaded episode.
"""

import json
import os


def load(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def main():
    history = load("uploaded_history.json", [])
    used = load("used_topics.json", [])
    gen = load("generated_topics.json", [])

    print("## Forgotten Empires - run report\n")
    print(f"- Episodes published: **{len(history)}**")
    print(f"- Topics left in curated pool: **{len(used)} used**")
    print(f"- Generated topic reserve: **{len(gen)}**")

    if history:
        last = history[-1]
        print("\n### Last upload")
        print(f"- Episode: **{last.get('episode', '?')}**")
        print(f"- Title: {last.get('title', '?')}")
        if last.get("video_id"):
            print(f"- Link: https://youtube.com/shorts/{last.get('video_id')}")
        print(f"- Time (UTC): {last.get('uploaded_at', '?')}")
    else:
        print("\n_No uploads recorded yet._")


if __name__ == "__main__":
    main()