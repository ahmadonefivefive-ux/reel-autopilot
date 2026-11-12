# Forgotten Empires — history Shorts pipeline

*The channel is **Forgotten Empires**. The GitHub repo keeps its old name
**reel-autopilot** — the code inside is this pipeline.*

One history Short every day at 12:00 PM US Eastern, made and uploaded
automatically. Everything here runs on free tiers: Gemini free tier, edge-tts
voice, PIL-drawn stickman art, ffmpeg, GitHub Actions.

**Cost: $0.** No card, no bank account, nothing to pay.

## What each run does

1. `topic_finder.py` — picks the next topic in strict list order, never repeating.
2. `script_writer.py` — Gemini writes a 90-115 word, 5-7 scene script with a
   hook, real dates, and one documented "bravery line". Refuses to fall back to
   a generic script.
3. `voiceover.py` — edge-tts (`en-US-ChristopherNeural`) with word-level timings.
4. `stickman.py` — draws every scene with PIL, animates a slow zoom, fades the
   scenes together, burns synced captions, normalises loudness to -14 LUFS.
5. `thumbnail.py` — brand-locked parchment thumbnail with the episode number.
6. `upload.py` — Drive relay (stash → YouTube → delete), upload, thumbnail,
   description template, history ledger.
7. `run_summary.py` — writes a readable report to the Actions run page.

## Art

Every frame is drawn in code (`stickman_art.py`) — no stock footage, no
licensing, one consistent look:

| Scene | Use |
|---|---|
| `troops` | large armies as two blocks of dots, not stickman crowds |
| `campaignmap` | Arabia campaign map: green heartland, mosque, dashed route, battle banners |
| `battle`, `wall` | sieges and field battles |
| `horse`, `horse_ride`, `crown`, `flag`, `banner` | characters and courts |
| `map`, `sail`, `palm`, `arch`, `pyramid`, `book`, `lamp`, `coin`, `fall`, `crowd` | the rest |

Each scene carries a title plate, the channel footer, and the last scene carries
a subscribe end card.

## The no-repeat ledger

`used_topics.json` is written **only after a successful upload**, and checked
before every pick, along with `uploaded_history.json`. Matching uses word stems
and word pairs, so "Saladin" and "Salahuddin" count as the same topic. If every
source is exhausted, the bot stops instead of repeating.

## Secrets (repo → Settings → Secrets and variables → Actions)

- `GEMINI_API_KEY`
- `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`
- `DRIVE_REFRESH_TOKEN` (same Google project; scope `drive.file`)

No base64 secrets are needed. Optional: set `DRIVE_REQUIRED=0` to allow a
direct upload if Drive ever fails.

## YouTube rules for AI-made videos (honest defaults)

- Disclose synthetic voice when YouTube asks ("altered content: yes").
- Every script is written for its own topic — not mass-produced spam.
- Monetization needs 1,000 subscribers + 4,000 watch hours (or 10M Shorts
  views). Daily uploads make that a months-long climb, not a shortcut.

## Local run

```bash
pip install -r requirements.txt
python run_pipeline.py
```

Needs `ffmpeg` and `ffprobe` on PATH. The finished `final_video.mp4` stays in
the folder if you run it locally.