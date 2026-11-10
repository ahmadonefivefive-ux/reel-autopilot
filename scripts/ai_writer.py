#!/usr/bin/env python3
"""
AI title & description writer (Google Gemini, free tier).

Why: YouTube compares your upload against other videos. If your title is
identical to the original, it can be treated as "reused content" and get
fewer views. So every video gets a freshly written, viral-style title,
description and hashtags — like MassReels does, but free.

- Uses the GEMINI_API_KEY GitHub secret (free key from Google AI Studio,
  see SETUP.md Part 2).
- The AI is called ONCE per video, during rendering (prep_batch), and the
  result is stored with the video in the Drive stash. Publishing never
  depends on the AI working at that moment.
- If the key is missing, the style is "off", or the API fails, it falls
  back to the plain template (original title + channel name) — the
  pipeline never breaks.

No extra pip installs: it uses Python's built-in urllib.
"""

import json
import os
import sys
import urllib.request

# Windows consoles can choke on emoji in printed titles; keep logs safe.
try:
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except Exception:
    pass

API_URL = ("https://generativelanguage.googleapis.com/v1beta/models/"
           "{model}:generateContent")

# Google periodically renames/retires exact model names, which makes old
# hardcoded names 404 ("AI writer failed (HTTP Error 404)"). The
# '-latest' aliases are officially maintained to always point at a
# current free-tier model, so we try those first, then a chain of
# versioned names as fallback. GEMINI_MODEL env overrides the chain.
MODEL_CHAIN = [
    "gemini-flash-latest",     # official alias, always current
    "gemini-flash-lite-latest", # lighter alias, also always current
    "gemini-2.5-flash",
    "gemini-2.0-flash",
]
DEFAULT_MODEL = MODEL_CHAIN[0]

STYLES = {
    "viral": (
        "Write like a viral Shorts editor: punchy, curiosity-driven, "
        "makes people NEED to watch. Never spoil the payoff."
    ),
    "neutral": (
        "Write a simple, factual, clean description of what happens. "
        "No clickbait, no exaggeration."
    ),
    "cinematic": (
        "Write like a dramatic movie-recap narrator: cinematic, "
        "story-driven tone."
    ),
}

PROMPT = """You write YouTube Shorts titles and descriptions for a channel called "{channel}".

The channel reposts short videos. You are given the ORIGINAL video's title.
Write a NEW, fresh title and description for the repost so it does NOT look
copied. Style: {style}

Rules for the title:
- 6-10 words, under 70 characters
- casual lowercase style is ok, no clickbait lies
- do NOT include the channel name
- do NOT mention that it is a repost
- 0-2 fitting emoji max

Rules for the description:
- 1-2 short lines about the video
- then a line: "via {channel}"
- then a line: "source: {source}"
- then 3-5 relevant hashtags on the last line (mix #shorts with topic tags)

Original title: "{title}"

Answer ONLY with JSON exactly like:
{{"title": "...", "description": "..."}}"""


def write_meta(orig_title, source, settings):
    """Return {"title": ..., "description": ...} for one video.

    Tries Gemini with the chosen style; falls back to the plain template
    if the key is missing, the style is off, or anything fails.
    """
    style = str(settings.get("ai_style") or "viral").strip().lower()
    channel = str(settings.get("channel_name") or "this channel")

    if style == "off":
        return fallback_meta(orig_title, source, settings)

    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("  (no GEMINI_API_KEY secret — using plain template; "
              "see SETUP.md Part 2 step 8 to enable AI writing)")
        return fallback_meta(orig_title, source, settings)

    if style not in STYLES:
        style = "viral"

    prompt = PROMPT.format(
        channel=channel,
        style=STYLES[style],
        title=str(orig_title or "video")[:300],
        source=str(source or "")[:200],
    )

    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 1.0,
            "response_mime_type": "application/json",
        },
    }).encode("utf-8")

    models = [m for m in [os.environ.get("GEMINI_MODEL", "").strip()]
              if m] or MODEL_CHAIN

    last_err = None
    for model in models:
        req = urllib.request.Request(
            API_URL.format(model=model),
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": key,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(text)
            title = str(parsed.get("title") or "").strip()
            description = str(parsed.get("description") or "").strip()
            if not (title and description):
                raise ValueError("empty AI answer")
            print(f"  AI wrote: {title}")
            return {"title": title[:100], "description": description[:4900]}
        except Exception as e:
            last_err = e
            # 404 = this model name doesn't exist for this key; try the
            # next one. Other errors (bad key, quota) won't improve with
            # a different model, so stop early.
            if "404" not in str(e):
                break
    print(f"  ! AI writer failed ({str(last_err)[:150]}) — using plain template")
    return fallback_meta(orig_title, source, settings)


def fallback_meta(orig_title, source, settings):
    """Plain template — always works, no AI."""
    title = str(orig_title or "video")
    desc = (f"{title}\n\nvia {settings.get('channel_name', '')}\n"
            f"source: {source}")
    return {"title": title[:100], "description": desc[:4900]}
