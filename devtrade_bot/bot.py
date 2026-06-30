"""Telegram bot (aiogram 3.x): accepts links and enqueues jobs.

Heavy work (download + Whisper + LLM) runs in the separate worker (worker.py);
the bot only inserts a Job and replies immediately.
"""

import re
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, Message
from sqlalchemy import select

from . import config
from .db import Job, Script, User, init_models, SessionLocal

router = Router()

_URL_RE = re.compile(r"https?://\S+")
_SUPPORTED_HOSTS = ("youtube.", "youtu.be", "instagram.")


class RenameStates(StatesGroup):
    waiting_for_name = State()


def find_supported_url(text: str) -> str | None:
    """Return the first supported link in the text, or None."""
    for match in _URL_RE.findall(text or ""):
        host = (urlparse(match).hostname or "").lower()
        if any(h in host for h in _SUPPORTED_HOSTS):
            return match
    return None


async def _ensure_user(session, message: Message) -> None:
    user = await session.get(User, message.from_user.id)
    if user is None:
        session.add(User(telegram_id=message.from_user.id, username=message.from_user.username))


def _script_title(script: Script) -> str:
    return script.name or script.strategy_json.get("type") or "стратегия"


async def _send_script(bot: Bot, chat_id: int, script: Script) -> None:
    """Send a script as a .pine document with a caption and validator notes."""
    filename = f"strategy_{script.id}.pine"
    doc = BufferedInputFile(script.pine_code.encode("utf-8"), filename=filename)

    caption = f"📈 #{script.id} — {_script_title(script)}"
    issues = script.validation_issues or []
    if issues:
        caption += "\n\n⚠️ Замечания валидатора:\n" + "\n".join(f"• {i}" for i in issues[:10])
    await bot.send_document(chat_id, doc, caption=caption[:1024])


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
        "/my — прислать все мои скрипты\n"
        "/get <id> — прислать скрипт заново\n"
        "/rename <id> — переименовать скрипт"
    )


@router.message(Command("my"))
async def cmd_my(message: Message) -> None:
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(Script)
                .where(Script.user_id == message.from_user.id)
                .order_by(Script.id.desc())
            )
        ).scalars().all()

    if not rows:
        await message.answer("У тебя пока нет сохранённых скриптов. Пришли ссылку, чтобы создать первый.")
        return

    for script in rows:
        await _send_script(message.bot, message.from_user.id, script)


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


@router.message(Command("rename"))
async def cmd_rename(message: Message, state: FSMContext) -> None:
    parts = (message.text or "").split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Использование: /rename <id>")
        return
    script_id = int(parts[1])

    async with SessionLocal() as session:
        script = await session.get(Script, script_id)
    if script is None or script.user_id != message.from_user.id:
        await message.answer("Скрипт не найден.")
        return

    await state.update_data(script_id=script_id)
    await state.set_state(RenameStates.waiting_for_name)
    await message.answer(f"Пришли новое имя для скрипта #{script_id} (или /cancel).")


@router.message(Command("cancel"), StateFilter(RenameStates.waiting_for_name))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменено.")


@router.message(StateFilter(RenameStates.waiting_for_name), F.text)
async def rename_apply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()
    script_id = data["script_id"]
    new_name = (message.text or "").strip()[:255]
    if not new_name:
        await message.answer("Пустое имя — отменил.")
        return

    async with SessionLocal() as session:
        script = await session.get(Script, script_id)
        if script is None or script.user_id != message.from_user.id:
            await message.answer("Скрипт не найден.")
            return
        script.name = new_name
        await session.commit()
    await message.answer(f"Готово: скрипт #{script_id} теперь «{new_name}».")


@router.message(StateFilter(None), F.text)
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


async def main() -> None:
    await init_models()
    bot = Bot(token=config.require_token())
    dp = Dispatcher()
    dp.include_router(router)
    print("devtrade_bot started (polling)")
    await dp.start_polling(bot)
