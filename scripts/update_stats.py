#!/usr/bin/env python3
"""
Fetches view counts for every uploaded video (runs every 6 hours on
GitHub Actions). Writes data/stats.json which the dashboard reads to
show which videos are getting views and which are not.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from run_batch import load_json, save_json, make_credentials, now_iso

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def chunks(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def main():
    uploaded = load_json(DATA / "uploaded.json", [])
    if not uploaded:
        print("Nothing uploaded yet.")
        return

    from googleapiclient.discovery import build
    yt = build("youtube", "v3", credentials=make_credentials(), cache_discovery=False)

    stats = load_json(DATA / "stats.json", {})
    ids = [u["id"] for u in uploaded if u.get("id")]

    for chunk in chunks(ids, 50):
        resp = yt.videos().list(part="statistics,snippet", id=",".join(chunk)).execute()
        for item in resp.get("items", []):
            s = item.get("statistics", {})
            thumb = (item.get("snippet", {}).get("thumbnails", {})
                     .get("medium", {}).get("url"))
            stats[item["id"]] = {
                "views": int(s.get("viewCount", 0)),
                "likes": int(s.get("likeCount", 0)),
                "comments": int(s.get("commentCount", 0)),
                "title": item.get("snippet", {}).get("title", ""),
                "thumb": thumb,
                "checked_at": now_iso(),
            }

    save_json(DATA / "stats.json", stats)
    total_views = sum(v.get("views", 0) for v in stats.values())
    print(f"Updated stats for {len(ids)} video(s). Total views: {total_views}.")


if __name__ == "__main__":
    main()
