"""Фоновый воркер: разбирает очередь Job и прогоняет пайплайн devtrade_parse.

Запускается отдельным процессом (`python -m devtrade_bot.worker`), держит модель
Whisper в памяти и обрабатывает задачи последовательно (concurrency = 1, т.к. один
Whisper на CPU). Результат пишет в БД и отправляет пользователю готовый .pine.
"""

import asyncio

from aiogram import Bot
from sqlalchemy import select

from devtrade_parse import process_url

from . import config
from .bot import _send_script
from .db import Job, Script, SessionLocal, init_models


async def _claim_job(session) -> Job | None:
    """Берёт одну pending-задачу и помечает её processing.

    На коробке работает один воркер, а SQLite сериализует записи, поэтому
    блокировка строк (FOR UPDATE SKIP LOCKED, доступная только в Postgres) не нужна.
    """
    job = (
        await session.execute(
            select(Job)
            .where(Job.status == "pending")
            .order_by(Job.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if job is not None:
        job.status = "processing"
        await session.commit()
    return job


async def _process_job(bot: Bot, job_id: int) -> None:
    async with SessionLocal() as session:
        job = await session.get(Job, job_id)
        url, user_id = job.url, job.user_id

    try:
        # process_url блокирующий (whisper) — уводим в поток, чтобы не вешать event loop.
        result = await asyncio.to_thread(process_url, url)
    except Exception as exc:  # noqa: BLE001 — любая ошибка пайплайна не должна ронять воркер
        async with SessionLocal() as session:
            job = await session.get(Job, job_id)
            job.status = "error"
            job.error = str(exc)[:2000]
            await session.commit()
        await bot.send_message(user_id, f"⛔ Не получилось обработать видео:\n{exc}")
        return

    if not result.is_strategy:
        async with SessionLocal() as session:
            job = await session.get(Job, job_id)
            job.status = "done"
            await session.commit()
        await bot.send_message(user_id, "🤷 В этом видео не нашлось торговой стратегии.")
        return

    issues = [i.message for i in result.validation.issues] if result.validation else []
    async with SessionLocal() as session:
        script = Script(
            user_id=user_id,
            source_url=url,
            source_type=result.source,
            strategy_json=result.strategy,
            pine_code=result.pine,
            validation_issues=issues or None,
        )
        session.add(script)
        await session.flush()
        script_id = script.id

        job = await session.get(Job, job_id)
        job.status = "done"
        job.script_id = script_id
        await session.commit()

        script = await session.get(Script, script_id)
        await _send_script(bot, user_id, script)


async def main() -> None:
    await init_models()
    bot = Bot(token=config.require_token())
    print("⚙️  devtrade_bot worker запущен")
    try:
        while True:
            async with SessionLocal() as session:
                job = await _claim_job(session)
                job_id = job.id if job else None
            if job_id is None:
                await asyncio.sleep(config.WORKER_POLL_INTERVAL)
                continue
            await _process_job(bot, job_id)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
