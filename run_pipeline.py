"""
Main pipeline: Topic -> Script -> Voiceover -> Video -> Thumbnail -> Upload.

Run locally with:
    python run_pipeline.py

GitHub Actions runs this automatically (see .github/workflows/pipeline.yml).
"""

import os
import shutil
import subprocess
import sys
import time

STEPS = [
    ("Finding a fresh topic...", "topic_finder.py"),
    ("Writing the script...", "script_writer.py"),
    ("Generating the voiceover...", "voiceover.py"),
    ("Assembling the video...", "video_assembly.py"),
    ("Creating the thumbnail...", "thumbnail.py"),
    ("Uploading to YouTube...", "upload.py"),
]

# Files that are recreated on every run. Never delete state files such as
# used_topics.json, generated_topics.json, or uploaded_history.json.
ARTIFACTS = [
    "topics.json",
    "script.json",
    "voiceover.mp3",
    "voiceover_raw.mp3",
    "word_boundaries.json",
    "captions.ass",
    "final_video.mp4",
    "thumbnail.jpg",
    "thumb_bg.jpg",
    "stock_loop.mp4",
    "segments.txt",
]


def clean_artifacts():
    for name in ARTIFACTS:
        if os.path.exists(name):
            try:
                os.remove(name)
            except OSError:
                pass

    if os.path.isdir("clips"):
        shutil.rmtree("clips", ignore_errors=True)

    for name in os.listdir("."):
        if name.startswith("seg_") and name.endswith(".mp4"):
            try:
                os.remove(name)
            except OSError:
                pass


def main():
    clean_artifacts()

    started = time.time()
    for message, script in STEPS:
        print(f"\n{'=' * 60}\n{message}\n{'=' * 60}")
        step_started = time.time()
        result = subprocess.run([sys.executable, script])
        if result.returncode != 0:
            print(
                f"\n[STOPPED] {script} failed. "
                "Nothing was uploaded. Fix the error above and re-run."
            )
            sys.exit(1)
        print(f"  (finished in {time.time() - step_started:.1f}s)")

    print(f"\nAll done in {time.time() - started:.1f}s. Video is live.")


if __name__ == "__main__":
    main()
