"""devtrade_bot — Telegram-бот поверх пайплайна devtrade_parse.

bot.py    — приём ссылок от пользователя, постановка задач в очередь (Job).
worker.py — фоновый процесс: гоняет пайплайн, пишет результат в БД, шлёт ответ.
db.py     — модели User / Script / Job (PostgreSQL, SQLAlchemy async).
"""
