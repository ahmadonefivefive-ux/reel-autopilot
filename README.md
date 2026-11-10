# ▶ Reel Autopilot

A **free** self-hosted version of a "mass reels" pipeline. It runs 24/7 on
**GitHub Actions + Google Drive** (both free) and does this every day:

1. Takes YouTube links from your queue (**paste as many as you want at once**)
2. Renders videos ahead of time: **small black border** around the video +
   **your channel name only** (no hook text on top)
3. **AI writes a fresh viral-style title + description + hashtags** for each
   video (Google Gemini, free tier) so reposts don't look copied —
   configurable style: viral / neutral / cinematic / off
4. Keeps finished videos ready in a **private Google Drive stash**
   (your free 15 GB, like a conveyor belt — each video is deleted from
   Drive right after it uploads, so the space keeps getting reused)
5. **Uploads 1–5 videos per day** to your YouTube channel automatically,
   each set to **go live at the best viewing hours** (default: noon, 4 PM
   and 8 PM New York time — US lunch, Europe evening, US prime time)
6. Checks **which uploaded videos are getting views** (stats refresh every 6 h)
7. Shows everything on a free dashboard (GitHub Pages)

Your PC and phone can be **off** — everything runs on GitHub's servers.

## What's inside

```
.github/workflows/prep.yml        every 6 h: queue -> render -> Drive stash
.github/workflows/daily.yml       every day: Drive stash -> YouTube (scheduled),
                                  then delete from Drive to free the space
.github/workflows/stats.yml       refreshes view counts every 6 hours
scripts/prep_batch.py             download -> border + channel name -> Drive
scripts/ai_writer.py              Gemini (free tier) viral title/description
scripts/run_batch.py              Drive stash -> scheduled YouTube upload
scripts/drive_stash.py            the Drive helpers (private folder, quota)
scripts/update_stats.py           fetch view counts of uploaded videos
scripts/auth.py                   one-time login to connect your YouTube+Drive
index.html                        the dashboard (GitHub Pages)
data/queue.txt                    your links, one per line
data/settings.json                channel name, videos per day, posting hours,
                                  stash target, Drive reserve...
data/uploaded.json                upload history (updated by the bot)
data/stash.json                   how many videos are ready + Drive free space
data/stats.json                   view counts (updated by the bot)
data/failed.json                  links that failed, with the reason
```

## Quick start

Follow **[SETUP.md](SETUP.md)** — it takes about 30 minutes the first time
(creating a Google Cloud API key + pushing this repo to GitHub). After that
it runs itself, forever, for free.

## Honest notes

- **YouTube API quota:** default is 10,000 units/day; one upload costs 1,600,
  so ~6 uploads/day max. That's why the daily limit is capped at 1–5.
- **yt-dlp on GitHub servers:** YouTube sometimes blocks datacenter IPs with
  "sign in to confirm you're not a bot". The Drive stash is the protection:
  publishing never depends on downloading — and a failed day just means the
  prep robot retries next run.
- **Drive storage:** the stash fills up to `stash_target` videos (default 25,
  max 500) and always keeps `drive_free_reserve_mb` free (default 2 GB) so
  your Drive is never 100% stuffed. Videos are deleted from Drive after they
  are safely on YouTube.
- **Can it run on my phone instead?** You don't need it to — GitHub's
  servers run everything, so your phone can be off. (Technically possible
  on Android with the Termux app, but fragile: battery, storage, disconnects.
  Not recommended.)
- **Rights:** you are responsible for the content you repost. Reposting videos
  you don't own can lead to copyright strikes — the same warning MassReels
  gives in its own terms.
- Keep the repo **public** — that's what makes Actions + Pages free.
