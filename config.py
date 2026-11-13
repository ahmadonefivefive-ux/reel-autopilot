import os

# Set these as GitHub repository secrets (Settings -> Secrets and variables -> Actions).
# Do NOT paste your real keys into this file.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "").strip()

NICHE = "history_stories"
AUDIENCE = "USA"
UPLOADS_PER_RUN = 1

# Voice
EDGE_TTS_VOICE = "en-US-ChristopherNeural"
EDGE_TTS_RATE = "+2%"
GTTS_SPEED = 1.1

# Video
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
FPS = 30

# Captions
CAPTION_FONT_SIZE = 72
CAPTION_MARGIN_V = 220

# Music (optional). Put a royalty-free track at music/background.mp3.
MUSIC_VOLUME = 0.08

# How many different Pexels clips to use per video.
CLIP_COUNT = 4

# Channel identity. Used in titles, descriptions, thumbnails and end cards.
CHANNEL_NAME = "FORGOTTEN EMPIRES"
CHANNEL_HANDLE = "@ForgottenEmpires"
CHANNEL_CTA = (
    "One forgotten empire every day at 12 PM ET. "
    "Subscribe so the next one finds you."
)

# Hashtags appended to every description (YouTube shows the first 3 above the title).
CHANNEL_HASHTAGS = "#history #historyshorts #ancienthistory #islamichistory #worldhistory"

# ---------------------------------------------------------------- long form
# Weekly 6-10 minute "full story" episodes. Same art, same voice, same brand.
LF_VIDEO_WIDTH = 1920
LF_VIDEO_HEIGHT = 1080
LF_FPS = 30
LF_CAPTION_FONT_SIZE = 50
LF_CAPTION_MARGIN_V = 148
LF_WORDS_PER_LINE = 4
LF_MUSIC_VOLUME = 0.05
LF_MIN_WORDS = 900
LF_MAX_WORDS = 1500
LF_EPISODE_LABEL = "FULL STORY"
LF_CTA = (
    "The full story every Sunday at 10 AM ET. "
    "Subscribe so the next one finds you."
)
LF_HASHTAGS = "#history #documentary #ancienthistory #islamichistory #worldhistory"

# Channel style — applied to EVERY video so the channel feels identical each time.
GRADE_FILTER = "eq=saturation=0.88:gamma=1.03:contrast=0.98,vignette=angle=PI/4.5"
WATERMARK = "FORGOTTEN EMPIRES"
WATERMARK_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
WATERMARK_FONTSIZE = 36
WATERMARK_Y = 64
