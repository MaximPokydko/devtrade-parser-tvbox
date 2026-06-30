"""Telegram bot settings (from environment / .env)."""

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ModuleNotFoundError:
    pass

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# In docker-compose DATABASE_URL is overridden to point at the db service.
# The default port 5433 matches what docker-compose exposes on the host.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://devtrade:devtrade@localhost:5433/devtrade",
)

WORKER_POLL_INTERVAL = float(os.getenv("WORKER_POLL_INTERVAL", "3"))


def require_token() -> str:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set — define it in .env")
    return TELEGRAM_BOT_TOKEN
