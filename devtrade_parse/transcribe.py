"""Video -> text: download audio (yt-dlp + ffmpeg) and transcribe it (Whisper).

Source is detected from the link's domain; cookies come from a per-platform file
(server/bot) or from the browser (local CLI) per the settings in config.
"""

import os
import shutil
import tempfile
from dataclasses import dataclass
from urllib.parse import urlparse

import whisper
import yt_dlp

from . import config


def _find_deno() -> str | None:
    if config.DENO_PATH and os.path.exists(config.DENO_PATH):
        return config.DENO_PATH
    found = shutil.which("deno")
    if found:
        return found
    default = os.path.expanduser("~/.deno/bin/deno")
    return default if os.path.exists(default) else None


# Heavy model: load once and reuse (matters for the long-lived worker).
_model = None


def _get_model():
    global _model
    if _model is None:
        print(f"Loading Whisper model ({config.WHISPER_MODEL})...")
        _model = whisper.load_model(config.WHISPER_MODEL)
    return _model


def detect_source(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if "youtube" in host or "youtu.be" in host:
        return "youtube"
    if "instagram" in host:
        return "instagram"
    return "other"


def _js_runtimes() -> dict:
    runtimes: dict = {}
    deno = _find_deno()
    if deno:
        runtimes["deno"] = {"path": deno}
    if shutil.which("node"):
        runtimes["node"] = {}
    return runtimes


def _ydl_opts(tmpdir: str, source: str) -> dict:
    opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "noplaylist": True,
        "retries": 10,
        "fragment_retries": 10,
        "socket_timeout": 60,
        "outtmpl": f"{tmpdir}/audio.%(ext)s",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
        }],
        # YouTube needs a JS runtime for the "n challenge"; deno primary, node fallback.
        "js_runtimes": _js_runtimes(),
        "remote_components": ["ejs:github"],
        "extractor_args": {"youtube": {"player_client": ["web"]}},
    }
    cookie_file = config.cookies_file_for(source)
    if cookie_file and os.path.exists(cookie_file):
        # yt-dlp writes the cookie jar back to the file; the source is mounted
        # read-only and shared, so give it a writable copy in tmpdir.
        writable = os.path.join(tmpdir, "cookies.txt")
        shutil.copyfile(cookie_file, writable)
        opts["cookiefile"] = writable
    elif config.COOKIES_FROM_BROWSER:
        opts["cookiesfrombrowser"] = (config.COOKIES_FROM_BROWSER,)
    return opts


@dataclass
class Transcript:
    text: str
    title: str
    source: str


def transcribe_url(url: str) -> Transcript:
    """Download audio for a link and return its transcription.

    Raises on download/access errors; the caller decides how to handle them.
    """
    source = detect_source(url)

    with tempfile.TemporaryDirectory() as tmpdir:
        with yt_dlp.YoutubeDL(_ydl_opts(tmpdir, source)) as ydl:
            info = ydl.extract_info(url, download=True)

        audio_file = os.path.join(tmpdir, "audio.mp3")
        if not os.path.exists(audio_file):
            raise FileNotFoundError(f"Audio not found after download: {audio_file}")

        print("Transcribing audio...")
        result = _get_model().transcribe(audio_file)
        text = (result.get("text") or "").strip()

    title = (
        info.get("title")
        or info.get("description")
        or info.get("id")
        or "video"
    )
    return Transcript(text=text, title=title, source=source)


def safe_filename(name: str) -> str:
    safe = "".join(c for c in name if c.isalnum() or c in (" ", "_", "-")).strip()
    return safe[:120] if safe else "video"
