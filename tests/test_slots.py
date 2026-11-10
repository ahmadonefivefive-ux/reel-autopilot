"""Tests for the posting-time scheduling in run_batch.post_slots()."""
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_batch

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


settings = {
    "timezone": "America/New_York",
    "post_times": ["12:00", "16:00", "20:00", "18:00", "22:00"],
}

# --- Case 1: batch runs 05:00 UTC (= midnight New York) -> all slots today
now = datetime(2026, 11, 10, 5, 0, tzinfo=timezone.utc)
slots = run_batch.post_slots(3, settings, now=now)
check("3 slots returned", len(slots) == 3, f"got {len(slots)}")
# Nov 10 2026: US is on EST (UTC-5). 12:00 ET = 17:00 UTC same day.
check("slot1 = 12:00 ET same day",
      slots[0].astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ") == "2026-11-10T17:00Z",
      slots[0].astimezone(timezone.utc).isoformat())
check("slot2 = 16:00 ET same day",
      slots[1].astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ") == "2026-11-10T21:00Z",
      slots[1].astimezone(timezone.utc).isoformat())
check("slot3 = 20:00 ET -> next day 01:00Z",
      slots[2].astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ") == "2026-11-11T01:00Z",
      slots[2].astimezone(timezone.utc).isoformat())

# --- Case 2: run happens at 22:00 UTC (17:00 ET): 12:00 and 16:00 ET passed
now = datetime(2026, 11, 10, 22, 0, tzinfo=timezone.utc)
slots = run_batch.post_slots(3, settings, now=now)
check("past noon rolls to tomorrow",
      slots[0].astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ") == "2026-11-11T17:00Z",
      slots[0].astimezone(timezone.utc).isoformat())
check("past 16:00 rolls to tomorrow",
      slots[1].astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ") == "2026-11-11T21:00Z",
      slots[1].astimezone(timezone.utc).isoformat())
check("20:00 ET still today (= 11th 01:00Z, after now)",
      slots[2].astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ") == "2026-11-11T01:00Z",
      slots[2].astimezone(timezone.utc).isoformat())

# --- Case 3: DST handling — July (EDT, UTC-4): 12:00 ET = 16:00 UTC
now = datetime(2026, 7, 10, 5, 0, tzinfo=timezone.utc)
slots = run_batch.post_slots(1, settings, now=now)
check("summer 12:00 ET = 16:00Z (DST handled)",
      slots[0].astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ") == "2026-07-10T16:00Z",
      slots[0].astimezone(timezone.utc).isoformat())

# --- Case 4: no post_times -> empty (post immediately)
check("no post_times -> []", run_batch.post_slots(3, {"post_times": []}) == [])

# --- Case 5: more videos than times cycles the list
now = datetime(2026, 11, 10, 5, 0, tzinfo=timezone.utc)
small = {"timezone": "America/New_York", "post_times": ["12:00", "20:00"]}
slots = run_batch.post_slots(3, small, now=now)
check("cycles times when short", len(slots) == 3, str(len(slots)))

# --- Case 6: unknown timezone falls back to UTC without crashing
bad = {"timezone": "Not/AZone", "post_times": ["12:00"]}
slots = run_batch.post_slots(1, bad, now=datetime(2026, 11, 10, 5, 0, tzinfo=timezone.utc))
check("bad tz -> UTC noon = 12:00Z",
      slots[0].astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ") == "2026-11-10T12:00Z",
      slots[0].astimezone(timezone.utc).isoformat())

# --- Case 7: publishAt format is valid RFC3339 UTC
s = slots[0].astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
check("RFC3339 format", s == "2026-11-10T12:00:00Z", s)

# --- Case 8: bad time value -> [] (posts immediately instead)
bad2 = {"timezone": "UTC", "post_times": ["25:99"]}
check("invalid time value -> []", run_batch.post_slots(1, bad2) == [])

print(f"\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
