"""Настройки Telegram-бота (читаются из окружения / .env)."""

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ModuleNotFoundError:
    pass

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Вариант tvbox: SQLite-файл (без сервера БД). Пример Postgres:
#   postgresql+asyncpg://user:pass@localhost:5432/devtrade
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///devtrade.db")

# Период опроса очереди задач воркером, сек.
WORKER_POLL_INTERVAL = float(os.getenv("WORKER_POLL_INTERVAL", "3"))

# Таймаут HTTP-сессии к Telegram, сек. На медленных каналах (tvbox) дефолта мало.
BOT_REQUEST_TIMEOUT = float(os.getenv("BOT_REQUEST_TIMEOUT", "120"))


def require_token() -> str:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не задан — укажите его в .env")
    return TELEGRAM_BOT_TOKEN
