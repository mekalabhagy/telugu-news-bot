"""Central settings. Values come from environment variables or a local .env file."""
import os
from pathlib import Path

ROOT = Path(__file__).parent


def _load_env_file():
    p = ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env_file()


def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


# ---- Channel branding -------------------------------------------------------
CHANNEL_NAME = env("CHANNEL_NAME", "తెలుగు తాజా వార్తలు")
CHANNEL_HANDLE = env("CHANNEL_HANDLE", "@your_handle")

# ---- Behaviour --------------------------------------------------------------
# review = cards wait in queue/pending until you run `python main.py approve`
# auto   = cards are published immediately (fully autonomous)
POST_MODE = env("POST_MODE", "review")
POSTS_PER_RUN = int(env("POSTS_PER_RUN", "2"))
MIN_SOURCES = int(env("MIN_SOURCES", "2"))          # outlets that must carry the story
SKIP_SENSITIVE = env("SKIP_SENSITIVE", "true").lower() == "true"
DEDUPE_HOURS = int(env("DEDUPE_HOURS", "72"))
MAX_STORY_AGE_HOURS = int(env("MAX_STORY_AGE_HOURS", "18"))

# ---- Claude API (Telugu writing + safety screening) --------------------------
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY")
CLAUDE_MODEL = env("CLAUDE_MODEL", "claude-sonnet-5-5")

# ---- Instagram Graph API ------------------------------------------------------
IG_USER_ID = env("IG_USER_ID")
IG_ACCESS_TOKEN = env("IG_ACCESS_TOKEN")
GRAPH_VERSION = env("GRAPH_VERSION", "v23.0")

# ---- Public image hosting (Instagram must fetch the image from a public URL) --
# Any S3-compatible bucket works (Cloudflare R2, AWS S3, Backblaze B2, ...)
S3_ENDPOINT = env("S3_ENDPOINT")          # e.g. https://<account>.r2.cloudflarestorage.com
S3_BUCKET = env("S3_BUCKET")
S3_ACCESS_KEY = env("S3_ACCESS_KEY")
S3_SECRET_KEY = env("S3_SECRET_KEY")
S3_PUBLIC_BASE_URL = env("S3_PUBLIC_BASE_URL")   # e.g. https://pub-xxxx.r2.dev

# ---- Paths --------------------------------------------------------------------
STATE_DIR = ROOT / "state"
QUEUE_PENDING = ROOT / "queue" / "pending"
QUEUE_PUBLISHED = ROOT / "queue" / "published"
OUT_DIR = ROOT / "out"
for _d in (STATE_DIR, QUEUE_PENDING, QUEUE_PUBLISHED, OUT_DIR):
    _d.mkdir(parents=True, exist_ok=True)
DB_PATH = STATE_DIR / "posted.db"
