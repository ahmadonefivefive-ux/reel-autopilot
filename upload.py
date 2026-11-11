"""
YouTube uploader.

Auth works in two ways, first match wins:
1. Environment secrets (recommended, used by GitHub Actions):
       YT_CLIENT_ID + YT_CLIENT_SECRET + YT_REFRESH_TOKEN
2. Local files made by:
       python upload.py
   then convert these two files to base64 and add them as GitHub secrets:
       token.pickle        -> YT_TOKEN_PICKLE_B64
       client_secret.json  -> YT_CLIENT_SECRET_B64
"""

import json
import os
import pickle
import sys
from datetime import datetime, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from topics_util import DuplicateChecker

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_FILE = "token.pickle"
CLIENT_SECRET_FILE = "client_secret.json"
HISTORY_FILE = "uploaded_history.json"


def get_authenticated_service():
    refresh_token = os.environ.get("YT_REFRESH_TOKEN", "").strip()
    client_id = os.environ.get("YT_CLIENT_ID", "").strip()
    client_secret = os.environ.get("YT_CLIENT_SECRET", "").strip()
    if refresh_token and client_id and client_secret:
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=SCOPES,
        )
        creds.refresh(Request())
        return build("youtube", "v3", credentials=creds)

    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if os.environ.get("CI"):
                sys.exit(
                    "YouTube login is invalid in GitHub Actions. "
                    "Run `python upload.py` on your computer, then update "
                    "the YT_TOKEN_PICKLE_B64 secret."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRET_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)

    return build("youtube", "v3", credentials=creds)


DRIVE_FOLDER_NAME = "Forgotten Empires"
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def build_drive_service():
    refresh_token = os.environ.get("DRIVE_REFRESH_TOKEN", "").strip()
    if not refresh_token:
        sys.exit(
            "DRIVE_REFRESH_TOKEN is not set. Add it in GitHub: "
            "Settings -> Secrets and variables -> Actions."
        )
    client_id = (os.environ.get("DRIVE_CLIENT_ID") or os.environ.get("YT_CLIENT_ID") or "").strip()
    client_secret = (os.environ.get("DRIVE_CLIENT_SECRET") or os.environ.get("YT_CLIENT_SECRET") or "").strip()
    if not client_id or not client_secret:
        sys.exit(
            "Drive client ID/secret missing. Set DRIVE_CLIENT_ID/DRIVE_CLIENT_SECRET, "
            "or reuse YT_CLIENT_ID/YT_CLIENT_SECRET (same Google project)."
        )
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=DRIVE_SCOPES,
    )
    creds.refresh(Request())
    return build("drive", "v3", credentials=creds)


def find_or_create_drive_folder(service):
    q = (
        "mimeType='application/vnd.google-apps.folder' and "
        "name='" + DRIVE_FOLDER_NAME + "' and trashed=false"
    )
    res = service.files().list(q=q, spaces="drive", fields="files(id)").execute()
    folders = res.get("files", [])
    if folders:
        return folders[0]["id"]
    folder = service.files().create(
        body={
            "name": DRIVE_FOLDER_NAME,
            "mimeType": "application/vnd.google-apps.folder",
        },
        fields="id",
    ).execute()
    print("  + Created Drive folder:", DRIVE_FOLDER_NAME)
    return folder["id"]


def drive_upload(service, folder_id, path, name, mime):
    media = MediaFileUpload(path, mimetype=mime, resumable=True)
    file = service.files().create(
        body={"name": name, "parents": [folder_id]},
        media_body=media,
        fields="id, webViewLink",
    ).execute()
    print("  + Drive upload:", name, "->", file.get("webViewLink", "ok"))
    return file["id"]


def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def already_uploaded(topic, title):
    history = load_history()

    topic_checker = DuplicateChecker(
        [h.get("topic", "") for h in history if h.get("topic")]
    )
    if topic and topic_checker.is_duplicate(topic):
        return True

    title_checker = DuplicateChecker(
        [h.get("title", "") for h in history if h.get("title")]
    )
    if title and title_checker.is_duplicate(title):
        return True

    return False


def mark_topic_used(topic):
    used = []
    if os.path.exists("used_topics.json"):
        try:
            with open("used_topics.json", "r", encoding="utf-8") as f:
                used = json.load(f)
        except Exception:
            used = []

    checker = DuplicateChecker(used)
    if not checker.is_duplicate(topic):
        used.append(topic)
        with open("used_topics.json", "w", encoding="utf-8") as f:
            json.dump(used, f, indent=2, ensure_ascii=False)


def clean_title(title):
    title = " ".join(str(title).split())
    for ch in "<>":
        title = title.replace(ch, "")
    return title[:100].strip()


def upload_video(youtube, video_path, thumbnail_path, title, description, tags):
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "27",  # Education
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(
        part="snippet,status", body=body, media_body=media
    )

    print("Uploading video...")
    response = request.execute()
    video_id = response["id"]
    print(f"Uploaded! https://youtube.com/shorts/{video_id}")

    try:
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(thumbnail_path),
        ).execute()
        print("Thumbnail set.")
    except Exception as e:
        print(f"  [!] Could not set thumbnail (video is still live): {e}")
        print("  [!] Verify your channel at youtube.com/verify.")

    return video_id


def main():
    youtube = get_authenticated_service()
    print("Login successful. token.pickle is ready.")

    if not os.path.exists("script.json"):
        print("No script.json yet. One-time login setup is complete.")
        return

    with open("script.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    if data.get("used_fallback"):
        sys.exit("Refusing to upload a fallback script that does not match the topic.")

    title = clean_title(data["title"])
    topic = data.get("source_topic", "")

    if already_uploaded(topic, title):
        print("This topic/title is already in uploaded_history.json. Skipping duplicate.")
        return

    description = data.get("description", "").strip()
    if "#Shorts" not in description:
        description = description.rstrip() + " #Shorts"

    tags = data.get("tags") or [
        "history", "historyfacts", "ancienthistory", "islamic history",
        "oneminutehistory", "shorts",
    ]

    # Every video passes through Google Drive first, then YouTube, and is
    # removed from Drive only after it is safely on YouTube.
    require_drive = os.environ.get("DRIVE_REQUIRED", "1") != "0"
    drive_ids = []
    try:
        drive_service = build_drive_service()
        drive_folder = find_or_create_drive_folder(drive_service)
        drive_ids.append(
            drive_upload(drive_service, drive_folder, "final_video.mp4",
                         title + ".mp4", "video/mp4")
        )
        if os.path.exists("thumbnail.jpg"):
            drive_ids.append(
                drive_upload(drive_service, drive_folder, "thumbnail.jpg",
                             title + ".jpg", "image/jpeg")
            )
    except Exception as e:
        if require_drive:
            sys.exit(
                f"Drive stash failed: {e}. Video was NOT uploaded to YouTube. "
                "Fix Drive token/scope, or set DRIVE_REQUIRED=0 to allow direct upload."
            )
        print(f"  [!] Drive stash failed, continuing anyway: {e}")

    video_id = upload_video(
        youtube,
        video_path="final_video.mp4",
        thumbnail_path="thumbnail.jpg",
        title=title,
        description=description,
        tags=tags,
    )

    history = load_history()
    history.append({
        "topic": topic,
        "title": title,
        "video_id": video_id,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    })
    save_history(history)

    if topic:
        mark_topic_used(topic)
        print(f"Marked topic as used: {topic}")


if __name__ == "__main__":
    main()
