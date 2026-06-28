"""Telegram-бот (aiogram 3.x): приём ссылок и постановка задач в очередь.

Тяжёлую работу (скачивание + Whisper + LLM) бот не делает — он лишь кладёт Job
в очередь, а обработкой занимается отдельный воркер (worker.py).
"""

import re
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import BufferedInputFile, Message
from sqlalchemy import select

from . import config
from .db import Job, Script, User, init_models, SessionLocal

router = Router()

_URL_RE = re.compile(r"https?://\S+")
_SUPPORTED_HOSTS = ("youtube.", "youtu.be", "instagram.")


def find_supported_url(text: str) -> str | None:
    """Возвращает первую поддерживаемую ссылку из текста или None."""
    for match in _URL_RE.findall(text or ""):
        host = (urlparse(match).hostname or "").lower()
        if any(h in host for h in _SUPPORTED_HOSTS):
            return match
    return None


async def _ensure_user(session, message: Message) -> None:
    user = await session.get(User, message.from_user.id)
    if user is None:
        session.add(User(telegram_id=message.from_user.id, username=message.from_user.username))


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    async with SessionLocal() as session:
        await _ensure_user(session, message)
        await session.commit()
    await message.answer(
        "👋 Привет! Я devtrade_bot.\n\n"
        "Пришли мне ссылку на Instagram Reels или YouTube Shorts с торговой стратегией — "
        "я расшифрую видео, извлеку стратегию и пришлю готовый скрипт на PineScript.\n\n"
        "Команды:\n"
        "/my — мои скрипты\n"
        "/get <id> — прислать скрипт заново"
    )


@router.message(Command("my"))
async def cmd_my(message: Message) -> None:
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(Script)
                .where(Script.user_id == message.from_user.id)
                .order_by(Script.id.desc())
                .limit(20)
            )
        ).scalars().all()

    if not rows:
        await message.answer("У тебя пока нет сохранённых скриптов. Пришли ссылку, чтобы создать первый.")
        return

    lines = [f"#{s.id} — {s.strategy_json.get('type') or 'стратегия'} ({s.source_type})" for s in rows]
    await message.answer("📁 Твои скрипты:\n" + "\n".join(lines) + "\n\n/get <id> — прислать заново")


@router.message(Command("get"))
async def cmd_get(message: Message) -> None:
    parts = (message.text or "").split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Использование: /get <id>")
        return
    script_id = int(parts[1])

    async with SessionLocal() as session:
        script = await session.get(Script, script_id)

    if script is None or script.user_id != message.from_user.id:
        await message.answer("Скрипт не найден.")
        return

    await _send_script(message.bot, message.from_user.id, script)


@router.message(F.text)
async def on_link(message: Message) -> None:
    url = find_supported_url(message.text)
    if url is None:
        await message.answer("Пришли ссылку на Instagram Reels или YouTube Shorts/видео 🙂")
        return

    async with SessionLocal() as session:
        await _ensure_user(session, message)
        session.add(Job(user_id=message.from_user.id, url=url, status="pending"))
        await session.commit()

    await message.answer("⏳ Принято! Обрабатываю видео — это может занять пару минут.")


async def _send_script(bot: Bot, chat_id: int, script: Script) -> None:
    """Отправляет .pine файлом + краткое описание и замечания валидатора."""
    filename = f"strategy_{script.id}.pine"
    doc = BufferedInputFile(script.pine_code.encode("utf-8"), filename=filename)

    caption = f"📈 Стратегия #{script.id} — {script.strategy_json.get('type') or 'без типа'}"
    issues = script.validation_issues or []
    if issues:
        caption += "\n\n⚠️ Замечания валидатора:\n" + "\n".join(f"• {i}" for i in issues[:10])
    await bot.send_document(chat_id, doc, caption=caption[:1024])


async def main() -> None:
    await init_models()
    bot = Bot(token=config.require_token())
    dp = Dispatcher()
    dp.include_router(router)
    print("🤖 devtrade_bot запущен (polling)")
    await dp.start_polling(bot)
