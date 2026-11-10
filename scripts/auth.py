#!/usr/bin/env python3
"""
One-time setup: get your YouTube refresh token.

Run this ON YOUR OWN PC (not on GitHub):

    pip install google-auth-oauthlib
    python scripts/auth.py path/to/client_secret_XXXX.json

(You get client_secret_XXXX.json from Google Cloud -> Credentials ->
OAuth client ID -> Desktop app -> Download JSON. See SETUP.md step 5.)

A browser window opens, you sign in with the Google account that owns
your YouTube channel, and then this script prints the 3 values you
need to paste into GitHub secrets:
    YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
"""

import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    # drive.file = can ONLY see files this app itself created in Drive.
    # It cannot read, see or delete any of your personal Drive files.
    "https://www.googleapis.com/auth/drive.file",
]


def main():
    secret_path = sys.argv[1] if len(sys.argv) > 1 else "client_secret.json"
    if not Path(secret_path).exists():
        print(f"ERROR: file not found: {secret_path}")
        print("Pass the path to your client_secret JSON file, e.g.:")
        print("    python scripts/auth.py client_secret_1234-abcd.apps.googleusercontent.com.json")
        sys.exit(1)

    flow = InstalledAppFlow.from_client_secrets_file(secret_path, SCOPES)
    print("A browser window will open. Sign in with the Google account")
    print("that owns your YouTube channel and click Allow.\n")
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")

    print()
    print("=" * 60)
    print("Copy these 3 values into GitHub repo secrets (see SETUP.md):")
    print("=" * 60)
    print()
    print(f"YT_CLIENT_ID      = {creds.client_id}")
    print(f"YT_CLIENT_SECRET  = {creds.client_secret}")
    print(f"YT_REFRESH_TOKEN = {creds.refresh_token}")
    print()
    print("GitHub -> your repo -> Settings -> Secrets and variables ->")
    print("Actions -> New repository secret  (create one for each value)")


if __name__ == "__main__":
    main()
