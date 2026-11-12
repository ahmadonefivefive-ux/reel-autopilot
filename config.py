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

# Channel style — applied to EVERY video so the channel feels identical each time.
GRADE_FILTER = "eq=saturation=0.88:gamma=1.03:contrast=0.98,vignette=angle=PI/4.5"
WATERMARK = "FORGOTTEN EMPIRES"
WATERMARK_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
WATERMARK_FONTSIZE = 36
WATERMARK_Y = 64
