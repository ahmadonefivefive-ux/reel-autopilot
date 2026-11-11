# Forgotten Empires — history Shorts bot

*The channel is called **Forgotten Empires**. The GitHub repo keeps its old
name **reel-autopilot** — the code inside it is fully replaced by this
pipeline. The YouTube channel itself is renamed from the old reposter channel
(old repost videos: delete or set private first).*

A free pipeline that makes **one history Short every day** and uploads it to
YouTube automatically. It is the science-shorts-bot you already know, rebuilt
for history: Alexander the Great, Muslim leaders, empires, battles, and
historical mysteries.

**Cost: $0.** Gemini free tier + Pexels free clips + edge-tts voice + GitHub
Actions. No card, no bank account, nothing to pay.

## What is different from the science bot

| Thing | Science bot | This bot |
|---|---|---|
| Topics | 120 science questions | 120+ history stories (Alexander, Salahuddin, Tariq ibn Ziyad, Mehmed II, Mansa Musa, Rome, Egypt, Mongols, Mughals, Ottomans...) |
| Script style | friendly teacher | cinematic storyteller, must use a real date or number, **no invented facts** |
| Voice | Jenny (female) | Guy (male documentary voice) |
| Upload rate | 4 per day | **1 per day** (noon US Eastern) |
| Tags | science | history, ancient history, Islamic history |
| Ledger | used science topics | starts EMPTY — it records every finished history video, so **no video is ever made twice** |

## The no-repeat ledger (your rule)

Every finished video's topic is written into `used_topics.json` before the
video is even made. Before picking a new topic, the bot checks:

1. `used_topics.json` (topics already made)
2. `uploaded_history.json` (topics actually on YouTube — second safety net)
3. Word stems and word pairs, so "Saladin" and "Salahuddin" count as the same.

If every topic source is exhausted, the bot **stops instead of repeating**.

## Setup (same flow as before — 15 minutes)

0. In **YouTube Studio**, rename the channel to **Forgotten Empires**
   (Customisation → Basic info → Name). Before that, **delete or set private
   all old reposted videos** — YouTube counts them as reused content and it
   can demonetize or strike the whole channel.
1. Your GitHub repo is **reel-autopilot** (keep the name, as you decided).
   Open it in the browser → **Add file → Upload files** → drag and drop
   EVERYTHING in this folder (except `client_secret*.json` and
   `token.pickle` — never upload those). Replace the old reposter code with
   this history pipeline.
2. Repo Settings → Actions → General → **Read and write permissions** → Save.
3. Repo Settings → Secrets → Actions — the same four secrets as before:
   - `GEMINI_API_KEY` (same key you already have)
   - `PEXELS_API_KEY` (same key you already have)
   - `YT_CLIENT_SECRET_B64` (base64 of your client_secret.json — in
     `..\reel-autopilot\client_secret.json`)
   - `YT_TOKEN_PICKLE_B64` — the token stays valid after the channel rename
     (channel ID doesn't change), so you can reuse the existing one IF it was
     created for this same Google account/channel.
4. Actions tab → **History Shorts Auto Pipeline** → Run workflow (first test).

To create the base64 strings on Windows (PowerShell), one at a time:

```powershell
# paste result into YT_TOKEN_PICKLE_B64
[Convert]::ToBase64String([IO.File]::ReadAllBytes("token.pickle")) | Set-Clipboard
# paste result into YT_CLIENT_SECRET_B64
[Convert]::ToBase64String([IO.File]::ReadAllBytes("client_secret.json")) | Set-Clipboard
```

Your `client_secret.json` for this is in `..\reel-autopilot\client_secret.json`.
The token is created by running `python upload.py` once in this folder on your
laptop (it opens a browser and you log into the Google account that owns the
new history channel).

## YouTube rules for AI-made videos (important, honest)

- Tick **"Altered content: yes"** when YouTube asks if content is synthetic —
  the voice is AI. This is YouTube's own disclosure question; being honest
  keeps the channel safe.
- This bot writes a **real script about a real topic** every time — it is not
  mass-produced spam. That is what YouTube's 2025 "inauthentic content" rule
  targets, and this pipeline is built to stay on the right side of it.
- Monetization needs 1,000 subscribers + 4,000 watch hours (or 10M Shorts
  views). Realistic with daily uploads: months, not days.

## Still to build (next session)

- **10-minute long videos** every 3 days (this bot makes ≤60s Shorts; long
  videos need a different assembly step — planned, not built yet)
- **Stickman animation style** — the current look is cinematic stock footage
  + captions + voiceover. A code-drawn stickman style is possible later with
  free tools (this is the upgrade you asked for)
- **Urdu version** of the channel — your native-language edge (same pipeline,
  Urdu voice `ur-PK-AsadNeural`, Urdu scripts)

## Where videos live

On GitHub Actions the video uploads straight to YouTube — nothing touches
your laptop or Drive, and nothing fills your Drive storage. If you ever run it
locally (`python run_pipeline.py`), the finished `final_video.mp4` stays in
this folder for you to upload or copy to your Google Drive yourself.
