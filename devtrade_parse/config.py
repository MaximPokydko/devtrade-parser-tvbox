"""Настройки модуля devtrade_parse (читаются из окружения / .env)."""

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ModuleNotFoundError:
    # python-dotenv опционален: переменные можно задать и через окружение.
    pass

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

# Whisper (локальная транскрибация)
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")

# yt-dlp cookies.
#   COOKIES_FILE      — путь к cookies в формате Netscape (для сервера/бота, где нет браузера).
#   COOKIES_FROM_BROWSER — имя браузера для cookiesfrombrowser (для локального CLI), напр. "firefox".
COOKIES_FILE = os.getenv("COOKIES_FILE")
COOKIES_FROM_BROWSER = os.getenv("COOKIES_FROM_BROWSER")

# Путь к JS-движку deno (нужен yt-dlp для решения YouTube «n challenge»).
# Если не задан — ищем в PATH и в стандартном ~/.deno/bin/deno.
DENO_PATH = os.getenv("DENO_PATH")

# Лимит длины генерируемого PineScript (строк) — передаётся в промпт и в валидатор.
PINE_MAX_LINES = int(os.getenv("PINE_MAX_LINES", "120"))
