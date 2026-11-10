"""Tests for the AI writer: happy path (mocked API), and every fallback."""
import io
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ai_writer

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


SETTINGS = {"channel_name": "My Channel", "ai_style": "viral"}

# the fake key for all mocked-API tests (checked in the header test)
import os
os.environ["GEMINI_API_KEY"] = "test-key-123"


class FakeResponse(io.BytesIO):
    """Minimal context-manager response for urlopen mocks."""
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


def mock_api(answer, calls):
    """Patch urlopen to return a Gemini-shaped JSON answer."""

    def fake_urlopen(req, timeout=None):
        calls.append(req)
        payload = {
            "candidates": [{"content": {"parts": [{"text": answer}]}}
                           ]
        }
        return FakeResponse(json.dumps(payload).encode("utf-8"))

    urllib.request.urlopen = fake_urlopen


def restore_urlopen():
    urllib.request.urlopen = real_urlopen


real_urlopen = urllib.request.urlopen

try:
    # ---- happy path: AI returns good JSON
    calls = []
    mock_api(json.dumps({
        "title": "wait for the ending nobody expected 😳",
        "description": "he really did that\n\nvia My Channel\nsource: https://youtu.be/abc\n#shorts #wow",
    }), calls)
    meta = ai_writer.write_meta("Original Video Title", "https://youtu.be/abc", SETTINGS)
    check("AI title used", meta["title"].startswith("wait for the ending"), meta["title"])
    check("AI description used", "via My Channel" in meta["description"], meta["description"])
    check("API was called with the key header",
          calls and calls[0].headers.get("X-goog-api-key") == "test-key-123",
          calls[0].headers if calls else "no call")
    body = json.loads(calls[0].data.decode("utf-8"))
    check("prompt includes original title",
          "Original Video Title" in body["contents"][0]["parts"][0]["text"])
    check("prompt includes channel name",
          "My Channel" in body["contents"][0]["parts"][0]["text"])
    check("JSON mode requested",
          body["generationConfig"]["response_mime_type"] == "application/json")

    # ---- style is injected into the prompt
    calls.clear()
    ai_writer.write_meta("t", "u", {"channel_name": "C", "ai_style": "cinematic"})
    prompt2 = json.loads(calls[0].data.decode("utf-8"))["contents"][0]["parts"][0]["text"]
    check("cinematic style in prompt", "cinematic" in prompt2.lower(), prompt2[:100])

    # ---- unknown style falls back to viral wording, not a crash
    calls.clear()
    ai_writer.write_meta("t", "u", {"channel_name": "C", "ai_style": "weird-style"})
    prompt3 = json.loads(calls[0].data.decode("utf-8"))["contents"][0]["parts"][0]["text"]
    check("unknown style -> viral prompt", "viral" in prompt3.lower(), prompt3[:100])

    # ---- API returns broken JSON -> falls back to template
    mock_api("this is not json at all {{{", [])
    meta = ai_writer.write_meta("Original Title", "u", SETTINGS)
    check("broken AI JSON -> fallback title", meta["title"] == "Original Title", meta["title"])
    check("fallback description has channel",
          "via My Channel" in meta["description"], meta["description"])

    # ---- API raises (network error) -> falls back, no crash
    def boom(req, timeout=None):
        raise OSError("network down")
    urllib.request.urlopen = boom
    meta = ai_writer.write_meta("Original Title", "u", SETTINGS)
    check("API down -> fallback title", meta["title"] == "Original Title", meta["title"])

    # ---- style "off" -> plain template, no API call
    calls2 = []
    mock_api("{}", calls2)
    meta = ai_writer.write_meta("Original Title", "u",
                                {"channel_name": "C", "ai_style": "off"})
    check("style off -> fallback", meta["title"] == "Original Title", meta["title"])
    check("style off -> no API call", len(calls2) == 0, len(calls2))

finally:
    restore_urlopen()

# ---- no key in environment -> fallback without calling the API
import os
os.environ.pop("GEMINI_API_KEY", None)
calls3 = []
mock_api("{}", calls3)
try:
    meta = ai_writer.write_meta("Original Title", "u", SETTINGS)
    check("missing key -> fallback", meta["title"] == "Original Title", meta["title"])
    check("missing key -> no API call", len(calls3) == 0, len(calls3))
finally:
    restore_urlopen()

# ---- long values are clamped to YouTube limits
os.environ["GEMINI_API_KEY"] = "k"
try:
    mock_api(json.dumps({"title": "x" * 500, "description": "y" * 9000}), [])
    meta = ai_writer.write_meta("t" * 500, "u", SETTINGS)
    check("title clamped to 100", len(meta["title"]) <= 100, len(meta["title"]))
    check("description clamped to 4900", len(meta["description"]) <= 4900,
          len(meta["description"]))
finally:
    restore_urlopen()
    os.environ.pop("GEMINI_API_KEY", None)

# ---- metadata round-trip through the Drive file description
import drive_stash
desc = drive_stash.make_meta("https://youtu.be/abc",
                             "wait for the ending 😳",
                             "desc line\nvia My Channel")
meta = drive_stash.parse_meta({"description": desc, "name": "x.mp4"})
check("meta round-trips with description",
      meta == {"source": "https://youtu.be/abc",
               "title": "wait for the ending 😳",
               "description": "desc line\nvia My Channel"}, meta)
meta = drive_stash.parse_meta({"description": "", "name": "old.mp4"})
check("old stash entries get empty description",
      meta["description"] == "" and meta["title"] == "old.mp4", meta)

print(f"\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
