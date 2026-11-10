#!/usr/bin/env python3
"""
One-time setup: get your YouTube and Google Drive refresh tokens.

Run this ON YOUR OWN PC (not on GitHub):

    pip install google-auth-oauthlib
    python scripts/auth.py client_secret.json

(You get client_secret JSON from Google Cloud -> Credentials ->
OAuth client ID -> Desktop app -> Download JSON. See SETUP.md Part 2.)

Google does not allow YouTube and Drive permissions in the same consent
request, so the browser opens TWICE:
    1st sign-in: YouTube  (upload videos + read your stats)
    2nd sign-in: Google Drive (the private video-stash folder)

Both use the same client_secret file. At the end this script prints the
4 values to paste into GitHub secrets:
    YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN, DRIVE_REFRESH_TOKEN
"""

import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

# YouTube scopes (these two combine fine with each other)
YT_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

# Drive scope, requested separately. drive.file = can ONLY see files this
# app itself created in Drive — it can never read your personal files.
DRIVE_SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
]


def run_flow(secret_path, scopes, label):
    flow = InstalledAppFlow.from_client_secrets_file(secret_path, scopes)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    if not creds.refresh_token:
        print(f"  !! {label}: no refresh token returned. Re-run the script; "
              "if it keeps happening, remove the app at "
              "https://myaccount.google.com/permissions and try again.")
    print(f"  {label}: OK")
    return creds


def main():
    secret_path = sys.argv[1] if len(sys.argv) > 1 else "client_secret.json"
    if not Path(secret_path).exists():
        print(f"ERROR: file not found: {secret_path}")
        print("Pass the path to your client_secret JSON file, e.g.:")
        print("    python scripts/auth.py client_secret.json")
        sys.exit(1)

    print("A browser window will open. Sign in with the Google account")
    print("that owns your YouTube channel and click Allow.\n")

    print("[1/2] YouTube permission (upload + read stats)...")
    yt = run_flow(secret_path, YT_SCOPES, "YouTube")

    print("[2/2] Google Drive permission (video stash)...")
    dr = run_flow(secret_path, DRIVE_SCOPES, "Drive")

    print()
    print("=" * 60)
    print("Copy these 4 values into GitHub repo secrets (see SETUP.md):")
    print("=" * 60)
    print()
    print(f"YT_CLIENT_ID        = {yt.client_id}")
    print(f"YT_CLIENT_SECRET    = {yt.client_secret}")
    print(f"YT_REFRESH_TOKEN    = {yt.refresh_token}")
    print(f"DRIVE_REFRESH_TOKEN = {dr.refresh_token}")
    print()
    print("GitHub -> your repo -> Settings -> Secrets and variables ->")
    print("Actions -> New repository secret  (one for each value)")


if __name__ == "__main__":
    main()
