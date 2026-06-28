# devtrade_parse + devtrade_bot

**Превращает видео про трейдинг (YouTube / Instagram Reels) в торговые идеи и код на PineScript.**

Проект состоит из двух частей:

- **`devtrade_parse`** — Python-пакет-пайплайн: транскрибация видео (локально, Whisper) →
  извлечение стратегии в JSON-DSL (OpenAI) → генерация PineScript (OpenAI) → валидация кода.
- **`devtrade_bot`** — Telegram-бот (aiogram 3.x): пользователь присылает ссылку на Reels/Shorts,
  бот прогоняет её через `devtrade_parse` и возвращает готовый `.pine`, сохраняя пользователя
  и скрипт в PostgreSQL.

---

## Содержание

- [Как это работает](#как-это-работает)
- [Структура проекта](#структура-проекта)
- [Пакет devtrade_parse](#пакет-devtrade_parse)
- [Валидатор PineScript](#валидатор-pinescript)
- [Telegram-бот devtrade_bot](#telegram-бот-devtrade_bot)
- [Установка](#установка)
- [Настройка ключей и cookies](#настройка-ключей-и-cookies)
- [Запуск](#запуск)
- [Известные ограничения](#известные-ограничения)

---

## Как это работает

```
ссылка на видео (Reels / Shorts / YouTube)
        ↓  transcribe.py   (yt-dlp + ffmpeg + Whisper)
текст
        ↓  extract.py      (OpenAI: текст → стратегия в JSON-DSL)
DSL стратегии
        ↓  generate.py     (OpenAI: стратегия → PineScript)
сырой PineScript
        ↓  validate.py     (статические проверки + авто-починка)
готовый .pine
```

Оркестрирует всё `devtrade_parse.process_url(url)`. В боте этот вызов выполняет фоновый
воркер, а результат пишется в БД и отправляется пользователю файлом.

---

## Структура проекта

```
📦 devtradebot/
│
├── 📂 devtrade_parse/        # пакет-пайплайн
│   ├── config.py            # настройки (.env): ключи, модель Whisper, cookies
│   ├── transcribe.py        # видео → текст (yt-dlp + Whisper), автодетект источника
│   ├── extract.py           # текст → DSL-JSON (OpenAI)
│   ├── generate.py          # DSL → PineScript (OpenAI)
│   ├── validate.py          # статическая валидация + авто-починка PineScript
│   ├── pipeline.py          # process_url() — полный прогон одной ссылки
│   └── cli.py               # батч-режим через папки texts/ → ideas/ → pines/
│
├── 📂 devtrade_bot/          # Telegram-бот
│   ├── config.py            # токен, DATABASE_URL
│   ├── db.py                # модели User / Script / Job (SQLAlchemy async)
│   ├── bot.py               # хендлеры /start, ссылка, /my, /get
│   └── worker.py            # фоновый воркер: очередь Job → пайплайн → БД → ответ
│
├── 📂 texts/ ideas/ pines/   # артефакты CLI-режима (примеры в репозитории)
├── 📄 links.txt / insta_links.txt   # входные ссылки для CLI
├── 📄 requirements.txt
├── 📄 .env.example
└── 🐳 docker-compose.yml     # локальный PostgreSQL
```

---

## Пакет devtrade_parse

Публичный API (импортируется лениво):

```python
from devtrade_parse import process_url, transcribe_url, extract_strategy, generate_pine, validate_pine

result = process_url("https://www.instagram.com/reel/....")
print(result.is_strategy, result.pine)
print(result.validation.format_issues())
```

CLI (обмен через папки, как в исходной версии):

```bash
python -m devtrade_parse transcribe   # links.txt / insta_links.txt → texts/
python -m devtrade_parse extract      # texts/*.txt → ideas/*.json
python -m devtrade_parse generate     # ideas/*.json → pines/*.pine (с валидацией)
python -m devtrade_parse all          # extract + generate (по умолчанию)
python -m devtrade_parse url <ссылка> # полный пайплайн для одной ссылки в stdout
```

Модель OpenAI — `gpt-4.1-mini`, `temperature=0` (настраивается через `.env`).

---

## Валидатор PineScript

`validate.py` ловит типовые проблемы LLM-генерации **эвристиками/regex** (офлайн-компилятора
Pine не существует). Часть проблем чинится автоматически, остальное возвращается списком замечаний.

**Авто-починка:**
- удаление markdown-обёрток ` ```pinescript … ``` ` и пояснительного текста до `//@version`;
- добавление `//@version=5`, если директива отсутствует;
- перевод устаревших v4-функций в namespace-форму v5: `study()`→`indicator()`,
  `sma()`→`ta.sma()`, `abs()`→`math.abs()`, `security()`→`request.security()` и т.д.

**Предупреждения (без авто-починки):**
- несбалансированные скобки `()` / `[]`;
- нет/более одной декларации `strategy()`/`indicator()`;
- у `strategy()` нет вызовов `strategy.entry/exit/close`;
- смешаны табы и пробелы в отступах;
- код пустой или длиннее лимита.

Результат (`ValidationResult`) содержит исправленный код и список `ValidationIssue`
(severity `fixed` / `warning` / `error`). Замечания прикладываются к ответу бота.

---

## Telegram-бот devtrade_bot

Два процесса, общая БД PostgreSQL:

- **bot** (`python -m devtrade_bot`) — принимает ссылки, кладёт задачу `Job(pending)` в очередь,
  отвечает мгновенно. Команды: `/start`, `/my`, `/get <id>`.
- **worker** (`python -m devtrade_bot.worker`) — держит модель Whisper в памяти, последовательно
  забирает задачи, прогоняет `process_url`, сохраняет `Script` и шлёт пользователю `.pine`.

Таблицы: `users`, `scripts`, `jobs` (создаются автоматически при старте).

---

## Установка

Требуется: **Python 3.10+**, **ffmpeg**, **PyTorch** (для Whisper), **PostgreSQL** (для бота).

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu   # CPU-сборка
pip install -r requirements.txt
```

PostgreSQL для бота проще всего поднять через Docker:

```bash
docker compose up -d db
```

> 💡 Есть GPU + CUDA — выберите подходящую сборку PyTorch на https://pytorch.org.

---

## Настройка ключей и cookies

Скопируйте `.env.example` → `.env` и заполните:

- `OPENAI_API_KEY` — ключ OpenAI (https://platform.openai.com/api-keys);
- `TELEGRAM_BOT_TOKEN` — токен от @BotFather;
- `DATABASE_URL` — строка подключения к PostgreSQL;
- `COOKIES_FILE` — путь к cookies в формате Netscape (нужны для скачивания закрытых видео;
  на сервере браузера нет, поэтому используется файл, а не `COOKIES_FROM_BROWSER`).

> 🔒 `.env` и `cookies.txt` в `.gitignore` — никогда не коммить их.

---

## Запуск

**Пайплайн (CLI):** заполните `links.txt` / `insta_links.txt` и запустите шаги (см. выше).

**Бот:** в двух терминалах с активным venv и заполненным `.env`:

```bash
python -m devtrade_bot          # сам бот
python -m devtrade_bot.worker   # фоновый воркер
```

Пришлите боту ссылку на Reels/Shorts — через пару минут он вернёт `.pine` файлом.
`/my` покажет ваши скрипты, `/get <id>` — пришлёт скрипт заново.

---

## Известные ограничения

- **Валидность PineScript не гарантирована.** Валидатор ловит типовые ошибки, но финальную
  проверку и доводку делайте в редакторе TradingView.
- **Качество стратегии зависит от транскрибации.** Whisper (`small`) может искажать термины.
- **Cookies на сервере.** Instagram/YouTube часто требуют авторизацию; подготовьте `COOKIES_FILE`.
- **Скорость.** Локальный Whisper на CPU обрабатывает ролик дольше реального времени — для MVP
  ок (один воркер, очередь), позже можно вынести на GPU или внешний API транскрибации.
```
