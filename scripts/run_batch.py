#!/usr/bin/env python3
"""
The daily publisher. Runs on GitHub Actions for free.

What it does, in order:
  1. Takes the 1-5 OLDEST rendered videos from the Google Drive stash
     (the stash was filled from your queue by scripts/prep_batch.py)
  2. Loads each video back from Drive
  3. Uploads it to your YouTube channel, set to go PUBLIC automatically
     at the posting times you configured (settings.post_times, in
     settings.timezone) so videos land at good viewing hours
  4. DELETES the video from Drive after YouTube has it — so your Drive
     storage is freed again (the video now lives on YouTube)
  5. Records it in data/uploaded.json for the dashboard

If a video fails, it stays in the stash and is retried the next day.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

# Windows consoles can choke on emoji in printed titles; keep logs safe.
try:
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
WORK = ROOT / ".batch"

CANVAS_W, CANVAS_H = 1080, 1920  # standard vertical (Shorts) canvas


# ---------------------------------------------------------------- helpers

def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def fill(template, **values):
    """Replace {title} / {channel_name} / {source_url} tokens in a template."""
    out = str(template or "")
    for key, val in values.items():
        out = out.replace("{" + key + "}", str(val or ""))
    return out


def find_font():
    for candidate in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # GitHub runners
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arialbd.ttf",   # local testing on Windows
        "C:/Windows/Fonts/seguisb.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",  # macOS
    ]:
        if Path(candidate).exists():
            return Path(candidate)
    return None


# ---------------------------------------------------------------- scheduling

def post_slots(count, settings, now=None):
    """Publish times for today's batch, in the user's priority order.

    settings["post_times"] is a list like ["12:00", "16:00", "20:00"] in
    settings["timezone"]. The 1st video of the day goes live at the 1st
    time, the 2nd at the 2nd, and so on — so put your best hour first.
    A time that already passed today moves to tomorrow automatically.

    Returns timezone-aware datetimes, or [] when no posting times are set
    (then videos are posted immediately when the batch runs).
    """
    times = [str(t).strip() for t in settings.get("post_times") or [] if str(t).strip()]
    if not times:
        return []

    tzname = str(settings.get("timezone") or "UTC").strip()
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(tzname)
    except Exception:
        print(f"  ! unknown timezone '{tzname}', using UTC")
        tz = timezone.utc

    now = now or datetime.now(timezone.utc)
    local_now = now.astimezone(tz)
    today = local_now.date()

    slots = []
    for i in range(count):
        hhmm = times[i % len(times)]
        try:
            h, m = (int(x) for x in hhmm.split(":"))
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValueError
        except ValueError:
            print(f"  ! bad posting time '{hhmm}' — posting immediately instead")
            return []
        slot = datetime(today.year, today.month, today.day, h, m, tzinfo=tz)
        if slot <= local_now:
            slot += timedelta(days=1)  # already passed today -> tomorrow
        slots.append(slot)
    return slots


# ---------------------------------------------------------------- download

# YouTube blocks anonymous downloads from datacenter IPs ("Sign in to
# confirm you're not a bot" — GitHub's runners live in a datacenter),
# and since 2026 it additionally demands a "PO token" (proof that a
# real player app is asking) before handing out video files — even for
# logged-in sessions. Two things get the robot through:
#
#   1. PO-token helper: a tiny server (bgutil-ytdlp-pot-provider) that
#      the prep workflow runs in Docker on port 4416; the matching pip
#      package in requirements.txt makes yt-dlp use it automatically.
#      Without it, every player client below fails with
#      "Requested format is not available".
#   2. YOUTUBE_COOKIES (optional secret): a cookies.txt exported from a
#      logged-in browser, attached to every attempt — a token alone
#      does not lift the IP-based login wall, so cookies are needed too.
#
# yt-dlp can impersonate different player apps, and each has a different
# chance of getting through, so we try them in order. 'mweb' is proven
# to still return downloadable formats for accounts on YouTube's
# "SABR" streaming experiment (which hides the normal formats from
# logged-in sessions), so it is our last resort.
PLAYER_CLIENT_CHAIN = [
    None,        # yt-dlp's own default clients first
    "tv",        # smart-TV player — often still allowed
    "ios",
    "android_vr",
    "android",
    "mweb",      # still returns formats even on SABR-forced accounts
]

# When the logged-in session is burned (every cookied client hits the
# bot wall), these clients are tried once more LOGGED OUT — anonymous
# requests with the PO-token helper's visitor data sometimes succeed
# from datacenter IPs where the flagged session could not.
ANON_FALLBACK_CLIENTS = ["tv", "mweb"]

# The phrase YouTube uses when its bot check blocks the request.
BOT_WALL_MARKER = "Sign in to confirm"


class BotWall(Exception):
    """Raised when YouTube's 'Sign in to confirm you're not a bot' wall
    blocked EVERY attempt — the IP/session is blocked, not the video.

    The prep robot stops the run early when this happens (hammering a
    blocked session only makes things worse) and the failure NEVER
    counts toward the permanent 3-strike skip.
    """


def cookie_file(workdir):
    """Write the optional YOUTUBE_COOKIES secret to a real file."""
    cookies = os.environ.get("YOUTUBE_COOKIES", "").strip()
    if not cookies:
        return None
    path = Path(workdir) / "cookies.txt"
    path.write_text(cookies, encoding="utf-8")
    return path


@lru_cache(maxsize=1)
def cookie_health_warning():
    """One-time sanity check of the YOUTUBE_COOKIES secret.

    The cookie contents are never logged — only whether the export
    looks complete. A real signed-in youtube.com export always carries
    the core auth cookies; a partial copy/paste (e.g. out of a chat)
    does not, and stale/partial cookies are the #1 cause of
    "Sign in to confirm you're not a bot" failures.
    """
    cookies = os.environ.get("YOUTUBE_COOKIES", "").strip()
    if not cookies:
        return ("the YOUTUBE_COOKIES secret is not set — YouTube's bot "
                "check usually blocks anonymous downloads from GitHub's "
                "servers")
    missing = [name for name in ("SID", "SAPISID", "__Secure-1PSID")
               if f"\t{name}\t" not in cookies]
    if missing:
        lines = sum(1 for l in cookies.splitlines()
                    if l.strip() and not l.strip().startswith("#"))
        return (f"the YOUTUBE_COOKIES secret looks partial/truncated "
                f"({lines} cookie lines, missing core auth cookie(s): "
                f"{', '.join(missing)}) — re-export the FULL file from "
                "youtube.com while signed in and update the secret")
    return None


POT_PING_URL = "http://127.0.0.1:4416/ping"


@lru_cache(maxsize=1)
def pot_provider_available():
    """Is the PO-token helper server up? (checked once per run).

    Purely informational — yt-dlp talks to the helper on its own; this
    just puts a clear line in the Actions log so a missing helper is
    easy to spot when someone pastes the log for debugging.
    """
    import urllib.request
    try:
        urllib.request.urlopen(POT_PING_URL, timeout=5)
        return True
    except Exception:
        return False


def download_opts(client, cookiefile, workdir):
    """yt-dlp options for one attempt at one link."""
    opts = {
        "format": "bv*[height<=1920]+ba/b[height<=1920]/b",
        "outtmpl": str(workdir / "src.%(ext)s"),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
        "fragment_retries": 3,
    }
    if client:
        opts["extractor_args"] = {"youtube": {"player_client": [client]}}
    if cookiefile:
        opts["cookiefile"] = str(cookiefile)
    return opts


def download(url, workdir):
    import yt_dlp

    if pot_provider_available():
        print("  PO-token helper: reachable")
    else:
        print("  note: PO-token helper not reachable — YouTube may refuse "
              "to hand out video formats without it (see the 'Start the "
              "YouTube PO-token helper' step in the prep workflow)",
              file=sys.stderr)

    warn = cookie_health_warning()
    if warn:
        print(f"  !! cookie check: {warn}", file=sys.stderr)

    cookiefile = cookie_file(workdir)

    def try_clients(clients, use_cookies):
        """One pass over player clients. Returns (result, last_err, walls)."""
        last_err, walls = None, 0
        for client in clients:
            label = (client or "default") + ("" if use_cookies else " + logged out")
            cf = cookiefile if use_cookies else None
            try:
                with yt_dlp.YoutubeDL(download_opts(client, cf, workdir)) as ydl:
                    info = ydl.extract_info(url, download=True)
                try:
                    filepath = Path(info["requested_downloads"][0]["filepath"])
                except Exception:
                    filepath = next(p for p in workdir.iterdir()
                                   if p.name.startswith("src."))
                if not filepath.exists():
                    raise RuntimeError(f"downloaded file not found: {filepath}")
                title = info.get("title") or "video"
                print(f"  downloaded: {title}")
                return (filepath, title), None, walls
            except Exception as e:
                last_err = e
                if BOT_WALL_MARKER in str(e):
                    walls += 1
                print(f"  download via '{label}' failed: {str(e)[:160]}",
                      file=sys.stderr)
        return None, last_err, walls

    result, last_err, walls = try_clients(PLAYER_CLIENT_CHAIN,
                                          cookiefile is not None)
    attempts, total_walls = len(PLAYER_CLIENT_CHAIN), walls

    # Stale cookies can be WORSE than no cookies: if every cookied
    # attempt hit the bot wall, the logged-in session is burned — so
    # retry LOGGED OUT. Anonymous requests + the PO-token helper's
    # visitor data sometimes get through from datacenter IPs where the
    # flagged session could not.
    if result is None and cookiefile is not None \
            and walls == len(PLAYER_CLIENT_CHAIN):
        print("  every cookied client hit the bot wall — retrying logged out",
              file=sys.stderr)
        result, anon_err, anon_walls = try_clients(ANON_FALLBACK_CLIENTS, False)
        attempts += len(ANON_FALLBACK_CLIENTS)
        total_walls += anon_walls
        if last_err is None or result is None:
            last_err = anon_err or last_err
        if result is not None:
            print("  ! note: this download worked WITHOUT cookies — the "
                  "YOUTUBE_COOKIES secret is stale. Re-export it when "
                  "convenient (see SETUP.md); the robot keeps working "
                  "meanwhile.", file=sys.stderr)
            return result

    if result is not None:
        return result

    if attempts >= 2 and total_walls == attempts:
        raise BotWall(
            "YouTube's bot wall ('Sign in to confirm you're not a bot') "
            "blocked EVERY attempt this run — the IP/session is blocked, "
            "not the video. Fix: export a FRESH cookies.txt with the "
            "incognito method (see 'Troubleshooting' in SETUP.md) and "
            f"update the YOUTUBE_COOKIES secret. Last error: {str(last_err)[:200]}"
        )
    raise RuntimeError(f"download failed (tried {attempts} "
                       f"player clients): {str(last_err)[:400]}")


# ---------------------------------------------------------------- process

def process(src, dst, settings, workdir):
    """Small black border around the video + channel name overlay.

    ffmpeg runs with workdir as its working directory and the filter only
    uses bare file names (chan.txt / chanfont.ttf). This avoids all quoting
    problems with spaces and drive letters in paths.
    """
    border = max(0, int(settings.get("border_px", 20)))
    inner_w = max(CANVAS_W - 2 * border, 16)
    inner_h = max(CANVAS_H - 2 * border, 16)

    chain = [
        # fit inside the inner area, keep aspect ratio
        f"scale=w={inner_w}:h={inner_h}:force_original_aspect_ratio=decrease",
        # pad to full 1080x1920 with BLACK all around -> the black wall
        f"pad={CANVAS_W}:{CANVAS_H}:(ow-iw)/2:(oh-ih)/2:color=black",
        "setsar=1",
    ]

    # channel name only (no hook text) as a clean text pill
    name = str(settings.get("channel_name", "")).strip()
    if name:
        font = find_font()
        if font:
            shutil.copy(font, Path(workdir) / "chanfont.ttf")
        (Path(workdir) / "chan.txt").write_text(name, encoding="utf-8")
        fontsize = int(settings.get("name_fontsize", 54))
        y_expr = "90" if settings.get("name_position", "top") == "top" else "h-th-90"
        draw = (
            "drawtext=textfile=chan.txt"
            + (":fontfile=chanfont.ttf" if font else "")
            + f":fontcolor=white:fontsize={fontsize}"
            + ":box=1:boxcolor=black@0.45:boxborderw=16"
            + f":x=(w-text_w)/2:y={y_expr}"
        )
        chain.append(draw)

    cmd = [
        os.environ.get("FFMPEG_BIN", "ffmpeg"), "-y", "-i", str(src),
        "-vf", ",".join(chain),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(dst),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(workdir))
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr[-400:]}")
    print(f"  processed: black border {border}px + channel name")
    return dst


# ---------------------------------------------------------------- upload

# Google does not allow YouTube and Drive permissions in the same consent,
# so we keep TWO refresh tokens (two quick sign-ins in scripts/auth.py):
TOKEN_ENV = {
    "youtube": "YT_REFRESH_TOKEN",
    "drive": "DRIVE_REFRESH_TOKEN",
}


def missing_secrets(kind="youtube"):
    """Which required environment secrets are missing for this service."""
    token_env = TOKEN_ENV.get(kind)
    if not token_env:
        raise ValueError(f"unknown credential kind: {kind!r}")
    names = ["YT_CLIENT_ID", "YT_CLIENT_SECRET", token_env]
    return [n for n in names if not os.environ.get(n)]


def make_credentials(kind="youtube"):
    """OAuth credentials for one service: 'youtube' or 'drive'."""
    missing = missing_secrets(kind)
    if missing:
        raise RuntimeError(
            f"missing secrets for {kind}: {', '.join(missing)}. "
            "Add them in GitHub -> Settings -> Secrets and variables -> Actions."
        )
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    creds = Credentials(
        token=None,
        refresh_token=os.environ[TOKEN_ENV[kind]],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
    )
    creds.refresh(Request())
    return creds


def upload_video(path, title, description, settings, publish_at=None):
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    yt = build("youtube", "v3", credentials=make_credentials(), cache_discovery=False)
    status = {
        "privacyStatus": settings.get("privacy", "public"),
        "selfDeclaredMadeForKids": False,
    }
    if publish_at is not None:
        # YouTube only accepts a publish time on a private video;
        # it flips to public automatically at exactly that moment.
        status["privacyStatus"] = "private"
        status["publishAt"] = publish_at.astimezone(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        print(f"  scheduled to go live at {publish_at.strftime('%Y-%m-%d %H:%M')} "
              f"({publish_at.tzinfo})")

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:4900],
            "categoryId": "22",
            "tags": [],
        },
        "status": status,
    }
    media = MediaFileUpload(str(path), chunksize=8 * 1024 * 1024,
                            resumable=True, mimetype="video/mp4")
    request = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  uploading... {int(status.progress() * 100)}%", flush=True)
    return response["id"]


# ---------------------------------------------------------------- main

def main():
    settings = load_json(DATA / "settings.json", {})
    per_day = max(1, min(5, int(settings.get("videos_per_day", 3))))  # 1..5 only

    import drive_stash
    drv = drive_stash.drive_service()
    folder_id = drive_stash.ensure_folder(drv)
    files = drive_stash.stash_files(drv, folder_id)

    if not files:
        drive_stash.write_summary(DATA, drv, folder_id)
        print("Stash is empty — nothing to publish today. The 'Prepare videos' "
              "workflow fills the stash from your queue; check the Actions tab.")
        return

    batch = drive_stash.pick_oldest(files, per_day)
    print(f"Publishing {len(batch)} of {len(files)} ready video(s) today.")

    slots = post_slots(len(batch), settings)
    if slots:
        pretty = ", ".join(s.strftime("%H:%M") for s in slots)
        print(f"Videos go live today at (local time {slots[0].tzinfo}): {pretty}")

    uploaded = load_json(DATA / "uploaded.json", [])
    WORK.mkdir(exist_ok=True)

    for idx, item in enumerate(batch):
        meta = drive_stash.parse_meta(item)
        print(f"\n=== {meta['source'] or item.get('name')}")
        tmp = Path(tempfile.mkdtemp(dir=WORK))
        try:
            local = tmp / "video.mp4"
            drive_stash.download_rendered(drv, item["id"], local)

            title = fill(settings.get("title_template", "{title}"),
                         title=meta["title"],
                         channel_name=settings.get("channel_name", ""),
                         source_url=meta["source"])
            # Prefer the AI-written description stored at render time;
            # fall back to the description template for old stash entries.
            if meta.get("description"):
                description = meta["description"]
            else:
                description = fill(settings.get("description_template", "{title}"),
                                   title=meta["title"],
                                   channel_name=settings.get("channel_name", ""),
                                   source_url=meta["source"])

            slot = slots[idx] if idx < len(slots) else None
            video_id = upload_video(local, title, description, settings,
                                    publish_at=slot)

            # The video is safely on YouTube now -> free the Drive space.
            drive_stash.delete_file(drv, item["id"])
            print("  deleted from Drive to save storage")

            entry = {
                "id": video_id,
                "title": title,
                "source": meta["source"],
                "uploaded_at": now_iso(),
            }
            if slot is not None:
                entry["publish_at"] = (f"{slot.strftime('%Y-%m-%d %H:%M')} "
                                      f"({slot.tzinfo})")
                entry["publish_utc"] = slot.astimezone(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ")
                print(f"  -> goes live {entry['publish_at']}: "
                      f"https://youtu.be/{video_id}")
            else:
                print(f"  -> LIVE: https://youtu.be/{video_id}")
            uploaded.append(entry)
            save_json(DATA / "uploaded.json", uploaded)
        except Exception as e:
            error = str(e)[:500]
            print(f"  !! FAILED (video stays in the stash for tomorrow): "
                  f"{error}", file=sys.stderr)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    summary = drive_stash.write_summary(DATA, drv, folder_id)
    print(f"\nDone. {len(uploaded)} video(s) uploaded in total. "
          f"{summary['count']} still ready in the Drive stash.")


if __name__ == "__main__":
    main()
