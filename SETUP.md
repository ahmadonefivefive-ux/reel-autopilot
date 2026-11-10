# Setup guide (do this once, ~30 minutes)

After this, the bot uploads for you every day, free, from GitHub's servers.
You never need to keep your PC on.

You need: a GitHub account, a Google account that owns your YouTube channel,
and Python installed on this PC (you already have it).

---

## Part 1 — Put this folder on GitHub

1. Go to [github.com](https://github.com) and sign in (create a free account if needed).
2. Click **+** (top right) → **New repository**.
3. Name: `reel-autopilot` · Visibility: **Public** (public = free Actions + free Pages) → **Create repository**.
4. Get these files onto GitHub. Two options:

   **Option A — GitHub Desktop (easiest, no commands):**
   - Install [GitHub Desktop](https://desktop.github.com) and sign in.
   - In the app: **File → Add local repository…** → choose the `reel-autopilot`
     folder → it says "this is not a repository" → click **create a repository**
     with the same name → then click **Publish repository** (keep it **public**).

   **Option B — command line (if you install [git](https://git-scm.com)):**
   ```
   cd "C:\Users\HC\Documents\Default Project\reel-autopilot"
   git init
   git add .
   git commit -m "first"
   git branch -M main
   git remote add origin https://github.com/YOUR-NAME/reel-autopilot.git
   git push -u origin main
   ```

---

## Part 2 — Let the bot use your YouTube channel + Google Drive

The bot needs permission to upload videos to your channel and to keep the
rendered videos in your Google Drive until they are posted. This is the only
manual step, done **once**.

> Tip for maximum privacy: you can use a **separate Google account** just for
> the bot (create a fresh one, create a YouTube channel on it). Then your
> main Google account is never touched at all. Your choice — your existing
> channel works too.

1. Go to [console.cloud.google.com](https://console.cloud.google.com).
2. Top bar → project picker → **New project** → name it `reel-autopilot` → Create.
3. Menu ☰ → **APIs & Services → Library** → search **YouTube Data API v3** → **Enable**.
4. Menu ☰ → **APIs & Services → OAuth consent screen**:
   - User type: **External** → Create
   - App name: `reel-autopilot` · user support email: your email
   - Add yourself (your YouTube account's email) as a **test user** (step "Audience"/"Test users")
   - At the top, **Publish app** → confirm. (This stops the login token from
     expiring every 7 days. If you skip it, you must redo Part 3 weekly.)
5. **APIs & Services → Credentials** → **+ Create credentials → OAuth client ID**:
   - Application type: **Desktop app** → Create
   - Click **Download JSON** → you get a file like
     `client_secret_1234-abcd.apps.googleusercontent.com.json`
6. On your PC, in this folder:
   ```
   pip install google-auth-oauthlib
   python scripts/auth.py client_secret_XXXX.json
   ```
   (use your real downloaded file name)
   A browser opens → sign in with the Google account of your **YouTube channel**
   → if you see "Google hasn't verified this app", click **Advanced → Go to reel-autopilot (unsafe)** → **Allow**.
   The screen will mention **YouTube AND Google Drive** permissions — that is
   the stash where finished videos wait before posting (see below).
7. The script prints 3 values. Put them in GitHub as **secrets**:
   GitHub → your repo → **Settings → Secrets and variables → Actions →
   New repository secret** (do it 3 times):
   - Name `YT_CLIENT_ID` → value from the printout
   - Name `YT_CLIENT_SECRET` → value
   - Name `YT_REFRESH_TOKEN` → value
8. **AI title writing (free, optional but recommended):** Gemini writes a
   fresh viral-style title + description + hashtags for every video, so
   your reposts don't look copied (YouTube suppresses reused content).
   - Go to [aistudio.google.com](https://aistudio.google.com) → sign in
     with the **same Google account**
   - Click **Get API key** → **Create API key** → copy it
   - GitHub → repo → **Settings → Secrets and variables → Actions →
     New repository secret** → Name `GEMINI_API_KEY` → paste the key
   - That's it. The free tier is enough for hundreds of videos per day.
     Without this key the bot still works — it just keeps the original
     video title (see dashboard → Settings → "Title & description
     writing" to pick the style or turn it off).

---

## Part 3 — Turn the robots on

There are three workflows, all free:

1. GitHub → your repo → **Actions** tab → click **I understand my workflows, go ahead and enable them**.
2. Click **Prepare videos (fill Drive stash)** → **Run workflow** → **Run workflow**.
   This is your first manual test: it renders your queued links and fills
   the Drive stash. Watch the run to see it work.
3. Click **Daily publish (stash to YouTube)** → **Run workflow** — this posts
   from the stash (or tells you the stash is empty, which is fine before
   step 2 finishes).
4. Turn on your dashboard (GitHub Pages):
   Repo → **Settings → Pages** → Source: **Deploy from a branch** →
   Branch: **main** / folder: **/ (root)** → **Save**.
   After a few minutes your dashboard is live at:
   `https://YOUR-NAME.github.io/reel-autopilot/`

---

## Part 4 — Daily use

- **Add links:** open your dashboard and paste links (see "Connect GitHub"
  button to enable in-page pasting — 2 minute setup, instructions inside),
  **or** repo → `data/queue.txt` → pencil ✏️ → paste one link per line →
  **Commit changes**.
- **How many per day:** dashboard → Settings → "Videos per day" (1–5),
  or edit `data/settings.json` → `"videos_per_day": 3`.
- **How many to keep ready in Drive:** dashboard → Settings → "Ready videos
  to keep in Drive" (default 25). The prep robot keeps filling toward this
  number every 6 hours until your queue runs out.
- **Channel name on video & border size:** same place in the dashboard.
- **See what's getting views:** the dashboard updates every 6 hours
  (🔥 = getting views, 💤 = no views).

The bot takes links **from the top of the queue**, renders them, and removes
them from the queue — so the queue is always "next up first". Finished videos
wait in the Drive stash and post oldest-first.

### When videos go live (timing for views)

Videos do **not** go public the moment the bot runs. Each one is uploaded
privately and **flips to public automatically** at the posting times you set
(dashboard → Settings → "Viewer timezone" + "Posting times", or in
`data/settings.json`):

```json
"timezone": "America/New_York",
"post_times": ["12:00", "16:00", "20:00", "18:00", "22:00"]
```

- The **1st video of the day** goes live at the **1st time** in the list,
  the 2nd at the 2nd, and so on — so put your best hour first.
- The defaults target the biggest English-speaking audience (the US, plus
  Europe evening and India night overlap):
  - **12:00** New York = US lunch + Europe evening + India late evening
  - **16:00** New York = US afternoon + UK evening
  - **20:00** New York = US prime evening
- Change the timezone to wherever YOUR viewers are, e.g. `Africa/Cairo`,
  `Europe/London`, `Asia/Karachi`, `America/Los_Angeles` (full list:
  [IANA time zones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)).
- A time that already passed today moves to tomorrow automatically.
- Leave "Posting times" **empty** to publish immediately at the run time.

> Tip: for Shorts, consistency matters more than a magic hour. Same hours
> every day trains the audience and the algorithm.

### Is my Google account safe?

Yes, and here is exactly why:

- You create the key **inside your own Google account** (Part 2). Your
  password is never typed into this project, GitHub, or anywhere else.
- The 3 values go into **GitHub Secrets** — an encrypted vault separate
  from your files. They are hidden from logs and other people, even in a
  public repo.
- The YouTube key only allows **two things**: upload videos to your channel
  and read your video statistics. It cannot read your email, files,
  passwords, or delete anything.
- The Drive key uses Google's **`drive.file` scope**: the bot can only see
  files **it created itself** (the one `reel-autopilot` folder). It cannot
  see, read, or delete any of your personal Drive files, photos, or
  documents — impossible, not just policy.
- Revoke it anytime: Google Cloud → APIs & Services → Credentials →
  delete the OAuth client. The bot loses access instantly.

One honest caveat: the repo is public, so anyone can see your
`data/queue.txt`, `data/settings.json` and upload list (your *links and
titles*, never your key). Your Drive videos are **not** public — Drive
files are private to your account unless you share them. If the queue
visibility bothers you, say so — a private repo still works within
GitHub's free Actions minutes, but the dashboard (GitHub Pages) then needs
a paid plan, so you'd manage links by editing files on github.com instead.

### How the Google Drive stash works (the conveyor belt)

- Every 6 hours, the **prep robot** renders videos from your queue
  (download → black border + channel name → finished MP4) and saves them
  to a private folder **`reel-autopilot`** in *My Drive* on the account you
  connected.
- It keeps going until the stash holds `stash_target` ready videos
  (default 25, change it in the dashboard up to 500) **or** Drive is nearly
  full — it always keeps `drive_free_reserve_mb` (default 2000 MB) free, so
  your Drive never gets 100% stuffed and your Gmail keeps working.
- Every day, the **publisher** takes the oldest 1–5 videos from the stash,
  uploads them to YouTube (set to go live at your chosen hours), and
  **deletes each one from Drive right after** — YouTube has it now, so the
  Drive space is freed and reused. Like a conveyor belt.
- So Drive space is never permanently used: it's rented per video.
  A 15 GB free Drive ≈ hundreds of rendered Shorts at a time.
- Nothing on your PC or phone: rendering happens on GitHub's servers.

### Do I need to keep my phone or PC on?

**No.** All robots run on GitHub's servers, free, 24/7. Your devices can be
off. (Technically you *could* run the scripts on an Android phone with the
Termux app — but it's fragile: battery limits, storage, WiFi drops. The
GitHub way is strictly better, and it's what this project is built for.)

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Download fails: "Sign in to confirm you're not a bot" | YouTube blocked GitHub's servers temporarily. The prep robot retries automatically every 6 h — a link needs to fail 3 times before it's skipped forever. Publishing still happens from the Drive stash. You can also trigger "Prepare videos" manually from the Actions tab. |
| Video keeps the original title (no AI) | The `GEMINI_API_KEY` secret is missing or invalid — see Part 2 step 8. The style may also be set to "Off" in dashboard → Settings. |
| `429` / rate limit in the prep log | Gemini's free tier was briefly exhausted — extremely unlikely at 12 videos/run. It automatically falls back to the plain template and retries next run. |
| Video stays private / "scheduled" | It goes public by itself at its posting time — check the dashboard card or `data/uploaded.json` for the exact time. If it never flipped, YouTube rejected the schedule: re-run the publish workflow (⚡ Run now). |
| "Stash is empty" in the daily run | The prep robot hasn't rendered anything yet (queue empty, or downloads blocked). Run "Prepare videos" manually from the Actions tab and watch its log. |
| `insufficientPermissions` / 403 on upload | You signed in during Part 2 with the wrong Google account. Redo Part 2 steps 6–7 with the account that owns the channel. |
| Refresh token stopped working | If you kept the consent screen in "Testing" mode, tokens expire after 7 days — publish the app (Part 2 step 4) and redo steps 6–7. |
| quotaExceeded | YouTube allows ~6 uploads/day on the free quota. Keep videos_per_day at 1–5. |
| Dashboard says "stats coming" | The stats workflow runs every 6 h — or run it manually: Actions → Update view stats → Run workflow. |
| Text on videos looks odd with emoji | The overlay font supports normal letters/numbers only — keep the channel name plain. |

---

## Rights & responsibility

Only repost videos you have the rights to. Reuploading other people's
videos can get your channel copyright strikes, and YouTube's reused-content
policy can terminate channels that repost without meaningful change.
The channel name + border makes the video yours visually, but the
responsibility is yours.
