#!/usr/bin/env python3
"""
Google Drive stash — the buffer of ready-to-post videos.

Architecture:

    data/queue.txt ──(prep robot, every 6h)──▶ Google Drive "reel-autopilot"
    (your pasted links)   download + render        folder with finished MP4s
                                                        │
                                                        ▼
                                        (daily robot) YouTube, scheduled
                                        then DELETE the file from Drive
                                        to free the space again

The Drive token uses the "drive.file" scope: the bot can only see and
touch the files IT created in that one folder. Your personal Drive files,
photos and documents are invisible to it and can never be leaked.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

FOLDER_NAME = "reel-autopilot"


# ---------------------------------------------------------------- service

def drive_service():
    from googleapiclient.discovery import build
    from run_batch import make_credentials
    # kind='drive' -> uses the DRIVE_REFRESH_TOKEN secret
    return build("drive", "v3", credentials=make_credentials(kind="drive"),
                 cache_discovery=False)


def ensure_folder(drv):
    """Find (or create) the 'reel-autopilot' folder in My Drive."""
    query = (f"name='{FOLDER_NAME}' and "
             f"mimeType='application/vnd.google-apps.folder' and trashed=false")
    res = drv.files().list(q=query, spaces="drive",
                           fields="files(id,name)", pageSize=5).execute()
    for f in res.get("files", []):
        return f["id"]
    meta = {"name": FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder"}
    return drv.files().create(body=meta, fields="id").execute()["id"]


# ---------------------------------------------------------------- metadata

def make_meta(source, title, description):
    """Metadata stored on the Drive file itself (JSON in description)."""
    return json.dumps({
        "source": str(source)[:450],
        "title": str(title)[:450],
        "description": str(description or "")[:4900],
    }, ensure_ascii=False)


def parse_meta(file_item):
    try:
        meta = json.loads(file_item.get("description") or "{}")
    except Exception:
        meta = {}
    return {
        "source": meta.get("source", ""),
        "title": meta.get("title", file_item.get("name", "video")),
        "description": meta.get("description", ""),
    }


# ---------------------------------------------------------------- listing

def stash_files(drv, folder_id):
    """All rendered videos waiting in the stash."""
    query = f"'{folder_id}' in parents and trashed=false"
    res = drv.files().list(q=query, spaces="drive",
                           fields="files(id,name,size,createdTime,description)",
                           pageSize=1000).execute()
    return res.get("files", [])


def pick_oldest(files, count):
    """Take the OLDEST 'count' videos — first rendered, first posted."""
    ordered = sorted(files, key=lambda f: f.get("createdTime", ""))
    return ordered[:count]


# ---------------------------------------------------------------- transfer

def upload_rendered(drv, folder_id, path, source, title, description=""):
    """Put a rendered MP4 into the stash (private, only you can see it)."""
    from googleapiclient.http import MediaFileUpload

    meta = {
        "name": path.name,
        "parents": [folder_id],
        "description": make_meta(source, title, description),
    }
    media = MediaFileUpload(str(path), resumable=True,
                            mimetype="video/mp4", chunksize=8 * 1024 * 1024)
    request = drv.files().create(body=meta, media_body=media, fields="id")
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  saving to Drive... {int(status.progress() * 100)}%", flush=True)
    return response["id"]


def download_rendered(drv, file_id, dest_path):
    """Fetch a stashed video back from Drive to the runner."""
    from googleapiclient.http import MediaIoBaseDownload

    request = drv.files().get_media(fileId=file_id)
    with open(dest_path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                print(f"  loading from Drive... {int(status.progress() * 100)}%",
                      flush=True)
    return dest_path


def delete_file(drv, file_id):
    """Permanently delete a stashed video (frees Drive space immediately)."""
    drv.files().delete(fileId=file_id).execute()


# ---------------------------------------------------------------- quota

def free_bytes(drv):
    """How many bytes are still free in this Google account."""
    about = drv.about().get(fields="storageQuota").execute()
    quota = about.get("storageQuota", {})
    limit = int(quota.get("limit", 0))
    usage = int(quota.get("usage", 0))
    return (limit - usage) if limit else None  # None = unlimited/unreported


# ---------------------------------------------------------------- summary

def write_summary(data_dir, drv, folder_id):
    """Small data/stash.json for the dashboard (count + Drive free space)."""
    files = stash_files(drv, folder_id)
    free = free_bytes(drv)
    summary = {
        "count": len(files),
        "drive_free_mb": round(free / 1024 / 1024) if free is not None else None,
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    path = Path(data_dir) / "stash.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    return summary
