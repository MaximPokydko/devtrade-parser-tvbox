"""Видео → текст: скачивание аудио (yt-dlp + ffmpeg) и транскрибация (Whisper).

Объединяет логику бывших youtube_transcribe.py / insta_transcribe.py:
источник определяется по домену ссылки, cookies берутся из файла (сервер/бот)
или из браузера (локальный CLI) согласно настройкам в config.
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
    """Ищет бинарь deno: DENO_PATH → PATH → стандартный ~/.deno/bin/deno."""
    if config.DENO_PATH and os.path.exists(config.DENO_PATH):
        return config.DENO_PATH
    found = shutil.which("deno")
    if found:
        return found
    default = os.path.expanduser("~/.deno/bin/deno")
    return default if os.path.exists(default) else None

# Whisper-модель тяжёлая — грузим один раз и переиспользуем (важно для воркера).
_model = None


def _get_model():
    global _model
    if _model is None:
        print(f"Загружаем модель Whisper ({config.WHISPER_MODEL})...")
        _model = whisper.load_model(config.WHISPER_MODEL)
    return _model


def detect_source(url: str) -> str:
    """Возвращает 'youtube' | 'instagram' | 'other' по домену ссылки."""
    host = (urlparse(url).hostname or "").lower()
    if "youtube" in host or "youtu.be" in host:
        return "youtube"
    if "instagram" in host:
        return "instagram"
    return "other"


def _js_runtimes() -> dict:
    """Список JS-движков для yt-dlp. deno предпочтительнее, node — запасной."""
    runtimes: dict = {}
    deno = _find_deno()
    if deno:
        runtimes["deno"] = {"path": deno}
    if shutil.which("node"):
        runtimes["node"] = {}
    return runtimes


def _ydl_opts(tmpdir: str) -> dict:
    opts = {
        "format": "bestaudio*",
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
        # YouTube требует JS-движок для решения «n challenge» (иначе доступны только
        # картинки-превью). deno — основной движок yt-dlp; node как запасной.
        # Плюс подтягиваем EJS-солвер.
        "js_runtimes": _js_runtimes(),
        "remote_components": ["ejs:github"],
        "extractor_args": {"youtube": {"player_client": ["web"]}},
    }
    # Cookies: файл предпочтительнее (работает на сервере без браузера), но только
    # если он реально существует — иначе откатываемся на cookies из браузера.
    if config.COOKIES_FILE and os.path.exists(config.COOKIES_FILE):
        opts["cookiefile"] = config.COOKIES_FILE
    elif config.COOKIES_FROM_BROWSER:
        opts["cookiesfrombrowser"] = (config.COOKIES_FROM_BROWSER,)
    return opts


@dataclass
class Transcript:
    text: str
    title: str
    source: str


def transcribe_url(url: str) -> Transcript:
    """Скачивает аудио по ссылке и возвращает транскрибацию.

    Бросает исключение при ошибке скачивания/доступа — вызывающий код решает,
    как её обработать (бот сохранит её в Job.error).
    """
    source = detect_source(url)

    with tempfile.TemporaryDirectory() as tmpdir:
        with yt_dlp.YoutubeDL(_ydl_opts(tmpdir)) as ydl:
            info = ydl.extract_info(url, download=True)

        audio_file = os.path.join(tmpdir, "audio.mp3")
        if not os.path.exists(audio_file):
            raise FileNotFoundError(f"Аудио не найдено после скачивания: {audio_file}")

        print("🎧 Транскрибируем аудио...")
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
    """Очищает строку для использования в имени файла."""
    safe = "".join(c for c in name if c.isalnum() or c in (" ", "_", "-")).strip()
    return safe[:120] if safe else "video"
