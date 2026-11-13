"""
Long-form uploader (weekly full-story episode).

Flow (same rule as the Shorts): video goes to Google Drive first, then to
YouTube, and is deleted from Drive only after YouTube confirms the upload.

Reads:  longform_script.json, longform_video.mp4, longform_thumbnail.jpg,
        longform_chapters.json
Writes: longform_history.json, longform_used.json
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

from googleapiclient.http import MediaFileUpload

import config
import upload as shorts  # reuse auth + Drive helpers, no duplicated secrets

SCRIPT_FILE = "longform_script.json"
VIDEO_FILE = "longform_video.mp4"
THUMB_FILE = "longform_thumbnail.jpg"
CHAPTERS_FILE = "longform_chapters.json"
HISTORY_FILE = "longform_history.json"
USED_FILE = "longform_used.json"

DRIVE_FOLDER = "Forgotten Empires - Full Stories"


def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def next_episode(history):
    eps = [h.get("episode") for h in history if isinstance(h.get("episode"), int)]
    return (max(eps) if eps else len(history)) + 1


def video_duration(path):
    import subprocess

    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True,
    )
    try:
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def timestamp(seconds):
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def usable_chapters(chapters, duration):
    """YouTube needs 3+ chapters, each 10s or longer."""
    if not isinstance(chapters, list) or len(chapters) < 3:
        return []
    prepared = []
    for i, chapter in enumerate(chapters):
        start = int(chapter.get("start", 0))
        end = int(chapters[i + 1].get("start", duration)) if i + 1 < len(chapters) else int(duration)
        if end - start >= 10:
            prepared.append({"title": str(chapter.get("title", "PART")).strip(), "start": start})
    return prepared if len(prepared) >= 3 else []


def build_description(body, episode, chapters):
    parts = []
    if body:
        parts.append(body.strip())

    if chapters:
        lines = ["CHAPTERS"]
        for chapter in chapters:
            lines.append(f"{timestamp(chapter['start'])} {chapter['title']}")
        parts.append("\n".join(lines))

    parts.append(f"Full Story {episode:02d} \u00b7 {config.CHANNEL_NAME.title()}")
    parts.append(config.LF_CTA)
    parts.append(config.LF_HASHTAGS)
    return "\n\n".join(parts)


def publish(youtube, title, description, tags):
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "27",
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    last_error = None
    for attempt in range(3):
        try:
            media = MediaFileUpload(VIDEO_FILE, chunksize=-1, resumable=True)
            request = youtube.videos().insert(
                part="snippet,status", body=body, media_body=media
            )
            return request.execute()["id"]
        except Exception as e:
            last_error = e
            print(f"  [!] Upload attempt {attempt + 1} failed: {e}")
            if attempt < 2:
                time.sleep(30 * (attempt + 1))
    raise RuntimeError(f"Upload failed 3 times: {last_error}")


def set_thumbnail(youtube, video_id):
    try:
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(THUMB_FILE),
        ).execute()
        print("  Thumbnail set.")
    except Exception as e:
        print(f"  [!] Could not set thumbnail (video is still live): {e}")


def main():
    data = load_json(SCRIPT_FILE, None)
    if not data:
        sys.exit(f"{SCRIPT_FILE} is missing - nothing to upload.")
    if data.get("used_fallback"):
        sys.exit("Refusing to upload a fallback script that does not match the topic.")

    history = load_json(HISTORY_FILE, [])
    if not isinstance(history, list):
        history = []
    used = load_json(USED_FILE, [])
    if not isinstance(used, list):
        used = []

    topic = data.get("source_topic", "")
    title = shorts.clean_title(data["title"])
    episode = next_episode(history)
    duration = video_duration(VIDEO_FILE)
    chapters = usable_chapters(load_json(CHAPTERS_FILE, []), duration)
    description = build_description(data.get("description", ""), episode, chapters)

    tags = data.get("tags") or [
        "history", "documentary", "ancient history", "world history",
        "islamic history", "full story",
    ]

    print(f"Episode: Full Story {episode:02d}")
    print(f"Title: {title}")
    print(f"Runtime: {duration / 60:.1f} min | Chapters: {len(chapters)}")
    print(f"Drive relay: {DRIVE_FOLDER}")

    youtube = shorts.get_authenticated_service()
    print("YouTube login OK.")

    shorts.DRIVE_FOLDER_NAME = DRIVE_FOLDER
    drive_service = shorts.build_drive_service()
    folder_id = shorts.find_or_create_drive_folder(drive_service)

    drive_ids = [
        shorts.drive_upload(drive_service, folder_id, VIDEO_FILE,
                            title + ".mp4", "video/mp4"),
    ]
    if os.path.exists(THUMB_FILE):
        drive_ids.append(
            shorts.drive_upload(drive_service, folder_id, THUMB_FILE,
                                title + ".jpg", "image/jpeg")
        )

    video_id = publish(youtube, title, description, tags)
    print(f"Uploaded: https://youtube.com/watch?v={video_id}")

    set_thumbnail(youtube, video_id)

    # Only clean Drive after YouTube has the video.
    for file_id in drive_ids:
        try:
            drive_service.files().delete(fileId=file_id).execute()
            print(f"  - Removed Drive copy {file_id}")
        except Exception as e:
            print(f"  [!] Could not remove Drive copy {file_id}: {e}")

    history.append({
        "topic": topic,
        "title": title,
        "video_id": video_id,
        "episode": episode,
        "duration_seconds": round(duration, 1),
        "chapters": len(chapters),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    })
    save_json(HISTORY_FILE, history)

    if topic and topic not in used:
        used.append(topic)
        save_json(USED_FILE, used)
        print(f"Marked long-form topic as used: {topic}")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(
                f"## Full Story {episode:02d} published\n\n"
                f"- **{title}**\n"
                f"- Runtime: {duration / 60:.1f} min, {len(chapters)} chapters\n"
                f"- https://youtube.com/watch?v={video_id}\n"
            )


if __name__ == "__main__":
    main()