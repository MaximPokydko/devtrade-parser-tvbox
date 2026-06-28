"""Настройки Telegram-бота (читаются из окружения / .env)."""

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ModuleNotFoundError:
    pass

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Пример: postgresql+asyncpg://user:pass@localhost:5432/devtrade
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://devtrade:devtrade@localhost:5432/devtrade",
)

# Период опроса очереди задач воркером, сек.
WORKER_POLL_INTERVAL = float(os.getenv("WORKER_POLL_INTERVAL", "3"))


def require_token() -> str:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не задан — укажите его в .env")
    return TELEGRAM_BOT_TOKEN
