"""
Long-form pipeline: topic -> chaptered script -> voiceover -> video ->
thumbnail -> upload.

Runs once a week (see .github/workflows/longform.yml).
Run locally with:
    python run_longform.py
"""

import glob
import os
import subprocess
import sys
import time

STEPS = [
    ("Writing the long-form script...", ["longform_script.py"]),
    ("Generating the voiceover...",
     ["voiceover.py", "longform_script.json", "longform_voiceover.mp3",
      "longform_boundaries.json"]),
    ("Rendering the full episode...", ["longform_video.py"]),
    ("Creating the thumbnail...", ["longform_thumbnail.py"]),
    ("Uploading the full story...", ["longform_upload.py"]),
]

# Rebuilt on every run. State files (longform_used.json, longform_history.json)
# are never touched here.
ARTIFACTS = [
    "longform_script.json",
    "longform_voiceover.mp3",
    "longform_boundaries.json",
    "longform_captions.ass",
    "longform_video.mp4",
    "longform_thumbnail.jpg",
    "lf_body.mp4",
    "lf_segments.txt",
]

ARTIFACT_GLOBS = ("lf_scene_*.png", "lf_seg_*.mp4")


def clean_artifacts():
    for name in ARTIFACTS:
        if os.path.exists(name):
            try:
                os.remove(name)
            except OSError:
                pass
    for pattern in ARTIFACT_GLOBS:
        for name in glob.glob(pattern):
            try:
                os.remove(name)
            except OSError:
                pass


def main():
    clean_artifacts()

    started = time.time()
    for message, args in STEPS:
        print(f"\n{'=' * 60}\n{message}\n{'=' * 60}")
        step_started = time.time()
        result = subprocess.run([sys.executable] + args)
        if result.returncode != 0:
            print(
                f"\n[STOPPED] {args[0]} failed. "
                "Nothing was uploaded. Fix the error above and re-run."
            )
            sys.exit(1)
        print(f"  (finished in {time.time() - step_started:.1f}s)")

    print(f"\nFull story live in {time.time() - started:.1f}s.")


if __name__ == "__main__":
    main()