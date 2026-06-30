"""devtrade_parse settings (from environment / .env)."""

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ModuleNotFoundError:
    pass

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")

# Per-platform cookie files (Netscape format), refreshed on the host and mounted
# read-only into the worker (no browser/keyring inside the container).
YOUTUBE_COOKIES_FILE = os.getenv("YOUTUBE_COOKIES_FILE", "cookies/youtube.txt")
INSTAGRAM_COOKIES_FILE = os.getenv("INSTAGRAM_COOKIES_FILE", "cookies/instagram.txt")

# Local-CLI fallback: browser name for yt-dlp cookiesfrombrowser. Not used in Docker.
COOKIES_FROM_BROWSER = os.getenv("COOKIES_FROM_BROWSER")

# deno path for yt-dlp (YouTube n-challenge); falls back to PATH / ~/.deno/bin/deno.
DENO_PATH = os.getenv("DENO_PATH")

# Max generated PineScript length (lines), passed to the prompt and the validator.
PINE_MAX_LINES = int(os.getenv("PINE_MAX_LINES", "120"))


def cookies_file_for(source: str) -> str | None:
    """Cookie file path for a source ('youtube' / 'instagram'), or None."""
    return {
        "youtube": YOUTUBE_COOKIES_FILE,
        "instagram": INSTAGRAM_COOKIES_FILE,
    }.get(source)
