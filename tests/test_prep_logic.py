"""Tests for the prep/publish planning logic and Drive metadata."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import prep_batch
import drive_stash

ok = 0
fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  PASS {name}")
    else:
        fail += 1
        print(f"  FAIL {name} — {detail}")


# ---------------- plan(): which links to render this run

queue = ["a", "b", "c", "d", "e"]
failed = {"c"}

# stash empty, target 25 -> renders up to MAX_PER_RUN
big_queue = [f"link{i}" for i in range(20)] + ["c"]
needed, to_render = prep_batch.plan(big_queue, failed, 0, 25)
check("needed = target - stash", needed == 25, needed)
check("renders max_per_run links", len(to_render) == prep_batch.MAX_PER_RUN, len(to_render))
check("skips failed links", "c" not in to_render, to_render)
check("takes from the top, in order", to_render[0] == "link0", to_render)

# stash nearly full
needed, to_render = prep_batch.plan(queue, failed, 23, 25)
check("needed 2 when 23/25", needed == 2 and to_render == ["a", "b"], (needed, to_render))

# stash full -> nothing to do
needed, to_render = prep_batch.plan(queue, failed, 25, 25)
check("stash full -> no renders", needed == 0 and to_render == [], (needed, to_render))

# fewer links than target allows
needed, to_render = prep_batch.plan(["x"], set(), 0, 500)
check("only renders what exists", to_render == ["x"], to_render)

# all links failed 3 times -> nothing to render
needed, to_render = prep_batch.plan(queue, set(queue), 0, 25)
check("all failed -> none rendered", to_render == [], to_render)

# ---------------- has_space(): the Drive guard

check("unknown quota -> allowed", prep_batch.has_space(None, 2 * 1024**3) is True)
check("plenty free -> allowed",
      prep_batch.has_space(10 * 1024**3, 2 * 1024**3) is True)
check("below reserve -> blocked",
      prep_batch.has_space(1 * 1024**3, 2 * 1024**3) is False)
check("exactly at reserve -> blocked",
      prep_batch.has_space(2 * 1024**3, 2 * 1024**3) is False)

# ---------------- pick_oldest(): FIFO publishing

files = [
    {"id": "3", "createdTime": "2026-11-10T09:00:00Z", "name": "c.mp4"},
    {"id": "1", "createdTime": "2026-11-08T09:00:00Z", "name": "a.mp4"},
    {"id": "2", "createdTime": "2026-11-09T09:00:00Z", "name": "b.mp4"},
]
picked = drive_stash.pick_oldest(files, 2)
check("oldest first", [f["id"] for f in picked] == ["1", "2"], picked)
check("slices to count", len(drive_stash.pick_oldest(files, 5)) == 3)

# ---------------- parse_meta(): metadata survives on the Drive file

desc = drive_stash.make_meta("https://youtu.be/abc", "my funny reel #42",
                             "line one\nvia My Channel")
meta = drive_stash.parse_meta({"description": desc, "name": "x.mp4"})
check("meta round-trips", meta == {"source": "https://youtu.be/abc",
                                    "title": "my funny reel #42",
                                    "description": "line one\nvia My Channel"},
      meta)

# empty/corrupt metadata falls back to the file name
meta = drive_stash.parse_meta({"description": "", "name": "fallback.mp4"})
check("fallback to file name", meta["title"] == "fallback.mp4", meta)
meta = drive_stash.parse_meta({"description": "not json{{{"})
check("corrupt json survives", "title" in meta and "source" in meta, meta)

# long titles/sources are truncated safely
desc = drive_stash.make_meta("u" * 10000, "t" * 10000, "d" * 10000)
meta = drive_stash.parse_meta({"description": desc})
check("long values truncated", len(meta["source"]) <= 450 and
      len(meta["title"]) <= 450 and len(meta["description"]) <= 4900,
      (len(meta["source"]), len(meta["title"]), len(meta["description"])))

print(f"\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
