#!/usr/bin/env python3
"""
The prep robot. Runs on GitHub Actions every 6 hours, for free.

Its job: keep the Google Drive stash FULL of ready-to-post videos.

  1. Reads links from data/queue.txt (your pasted links, top of the list
     first; links that already failed 3 downloads are skipped)
  2. Renders videos ahead of time: download -> small black border +
     channel name -> finished MP4
  3. Saves each finished MP4 into the Google Drive stash (private)
  4. Removes the used links from the queue

It keeps going until EITHER:
  - the stash reaches settings.stash_target ready videos (default 25), or
  - Google Drive is almost full (settings.drive_free_reserve_mb is kept
    free, so your Drive is never 100% stuffed and Gmail keeps working), or
  - the queue runs out of links, or
  - it has rendered MAX_PER_RUN videos this run (it just continues on the
    next run, every 6 hours)

The daily publisher (scripts/run_batch.py) then posts from the stash and
deletes each video from Drive after it is on YouTube — so the space is
used, freed, and used again, like a conveyor belt.
"""

import shutil
import sys
import tempfile
from pathlib import Path

import ai_writer
import drive_stash
from run_batch import (DATA, WORK, download, load_json, now_iso, process,
                       save_json)

MAX_PER_RUN = 12  # renders per run; more continue on the next run


# ---------------------------------------------------------------- planning

# Errors that mean "YouTube is blocking the robot in general" (stale
# cookies, datacenter IP, streaming experiments) or "the runner is
# missing something" — NOT that the link is bad. These never count
# toward the permanent 3-strike skip, so a bad day can't silently kill
# the whole queue.
GLOBAL_BLOCK_MARKERS = (
    "Sign in to confirm",
    "Requested format is not available",
    "The page needs to be reloaded",
    "Some formats may be missing",
    "ffmpeg is not installed",   # runner tooling, not the video's fault
    "HTTP Error 429",            # rate limited — retry later
    "timed out",                 # network hiccup
)


def permanent_skips(failed):
    """URLs that failed 3+ times for reasons about the video itself
    (deleted, private, region-blocked...). Global YouTube blocking
    (GLOBAL_BLOCK_MARKERS) never counts toward the skip."""
    counts = {}
    for f in failed:
        if not f.get("url"):
            continue
        err = str(f.get("error", ""))
        if any(m in err for m in GLOBAL_BLOCK_MARKERS):
            continue
        counts[f["url"]] = counts.get(f["url"], 0) + 1
    return {url for url, n in counts.items() if n >= 3}


def plan(queue_lines, failed_urls, stash_count, target, max_per_run=MAX_PER_RUN):
    """Which links should be rendered this run?

    Returns (needed_to_reach_target, links_to_render_now).
    """
    links = [l for l in queue_lines if l not in failed_urls]
    needed = max(0, target - stash_count)
    to_render = links[:min(needed, max_per_run)]
    return needed, to_render


def has_space(free_bytes, reserve_bytes):
    """True when it is safe to add another video to Drive."""
    if free_bytes is None:  # quota unknown/unlimited -> don't block
        return True
    return free_bytes > reserve_bytes


# ---------------------------------------------------------------- main

def main():
    settings = load_json(DATA / "settings.json", {})
    target = max(1, min(500, int(settings.get("stash_target", 25))))
    reserve_bytes = max(200, int(settings.get("drive_free_reserve_mb", 2000))) \
        * 1024 * 1024

    queue_path = DATA / "queue.txt"
    lines = [l.strip() for l in queue_path.read_text(encoding="utf-8").splitlines()
             if l.strip() and not l.strip().startswith("#")]
    failed = load_json(DATA / "failed.json", [])

    # A link that already failed 3 times for its OWN reasons is skipped
    # forever (probably deleted/private). Bot-wall and other global
    # YouTube failures never count (see permanent_skips).
    failed_urls = permanent_skips(failed)

    drv = drive_stash.drive_service()
    folder_id = drive_stash.ensure_folder(drv)
    files = drive_stash.stash_files(drv, folder_id)

    needed, to_render = plan(lines, failed_urls, len(files), target)
    print(f"Stash: {len(files)} ready, target {target} "
          f"({needed} more needed). Queue: {len(lines)} link(s).")

    if needed <= 0:
        drive_stash.write_summary(DATA, drv, folder_id)
        print("Stash is already full — nothing to do today. "
              "The publisher will eat from it every day.")
        return

    if not to_render:
        if failed_urls and set(lines) <= failed_urls:
            print("All queued links already failed 3 downloads — they are "
                  "skipped forever. Paste fresh links to keep the stash full.")
        else:
            print("Queue is empty — paste more links to keep the stash full.")
        drive_stash.write_summary(DATA, drv, folder_id)
        return

    free = drive_stash.free_bytes(drv)
    if not has_space(free, reserve_bytes):
        drive_stash.write_summary(DATA, drv, folder_id)
        mb = round(free / 1024 / 1024) if free is not None else "?"
        print(f"Drive is nearly full ({mb} MB free, reserve "
              f"{reserve_bytes // 1024 // 1024} MB) — not adding more. "
              f"Videos are freed from Drive every day after they upload.")
        return

    print(f"Rendering up to {len(to_render)} video(s) this run "
          f"(border + channel name), saving to Drive.")

    WORK.mkdir(exist_ok=True)  # scratch space for downloads/renders
    done = []
    for url in to_render:
        print(f"\n=== {url}")
        tmp = Path(tempfile.mkdtemp(dir=WORK))
        try:
            free = drive_stash.free_bytes(drv)
            if not has_space(free, reserve_bytes):
                print("  Drive reached the reserve — stopping here.",
                      file=sys.stderr)
                break

            src, orig_title = download(url, tmp)
            out = tmp / "out.mp4"
            process(src, out, settings, tmp)

            # Fresh viral-style title + description (Gemini free tier),
            # stored with the video in the Drive stash.
            meta = ai_writer.write_meta(orig_title, url, settings)
            drive_stash.upload_rendered(drv, folder_id, out, url,
                                        meta["title"], meta["description"])
            done.append(url)
            print("  ready in the Drive stash")
        except Exception as e:
            error = str(e)[:500]
            print(f"  !! FAILED: {error}", file=sys.stderr)
            failed.append({"url": url, "error": error, "at": now_iso()})
            save_json(DATA / "failed.json", failed)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    if done:
        remaining = [l for l in lines if l not in done]
        queue_path.write_text(
            ("\n".join(remaining) + "\n") if remaining else
            "# Queue is empty. Paste YouTube links here, one per line.\n",
            encoding="utf-8",
        )

    summary = drive_stash.write_summary(DATA, drv, folder_id)
    print(f"\nDone. Added {len(done)} video(s) to the stash "
          f"(now {summary['count']} ready, "
          f"{summary.get('drive_free_mb')} MB free on Drive). "
          f"{len(to_render) - len(done)} failed this run.")


if __name__ == "__main__":
    main()
