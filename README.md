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
- [Быстрый старт (Docker)](#быстрый-старт-docker)
- [Настройка ключей и cookies](#настройка-ключей-и-cookies)
- [Cookies (YouTube и Instagram)](#cookies-youtube-и-instagram)
- [Локальная разработка (без Docker)](#локальная-разработка-без-docker)
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
│   ├── bot.py               # хендлеры /start, ссылка, /my, /get, /rename
│   └── worker.py            # фоновый воркер: очередь Job → пайплайн → БД → ответ
│
├── 📂 scripts/               # хост-утилиты (refresh_cookies.py — обновление куки)
├── 📂 cookies/               # youtube.txt / instagram.txt (в .gitignore, маунт в воркер)
├── 📂 texts/ ideas/ pines/   # артефакты CLI-режима (генерируются локально, в .gitignore)
├── 📄 youtube_links.txt / insta_links.txt   # входные ссылки для CLI
├── 📄 requirements.txt
├── 🐳 Dockerfile             # образ бота/воркера (ffmpeg + deno + torch CPU)
└── 🐳 docker-compose.yml     # db (PostgreSQL) + bot + worker
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
python -m devtrade_parse transcribe   # youtube_links.txt / insta_links.txt → texts/
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
  отвечает мгновенно. Команды: `/start`, `/my` (прислать все скрипты файлами),
  `/get <id>`, `/rename <id>` (интерактивно переименовать скрипт).
- **worker** (`python -m devtrade_bot.worker`) — держит модель Whisper в памяти, последовательно
  забирает задачи, прогоняет `process_url`, сохраняет `Script` и шлёт пользователю `.pine`.

Таблицы: `users`, `scripts`, `jobs` (создаются автоматически при старте).

---

## Быстрый старт (Docker)

Docker — основной способ запуска. Нужны только **Docker** и **Docker Compose** —
Python, ffmpeg, deno и torch (CPU-сборка) ставятся внутри образа.

```bash
# 1. создайте .env в корне (см. «Настройка ключей и cookies»)
# 2. заполните cookies/ (см. «Cookies») — для YouTube/Instagram нужна авторизация
docker compose up -d --build    # поднимет db + bot + worker
docker compose logs -f          # логи
docker compose down             # остановить
```

Что поднимается:

| Сервис   | Назначение                                                  |
|----------|-------------------------------------------------------------|
| `db`     | PostgreSQL 16, наружу на `localhost:5433`                    |
| `bot`    | принимает ссылки в Telegram, кладёт задачи в очередь         |
| `worker` | разбирает очередь, гоняет пайплайн `process_url` (по умолчанию 1 реплика) |

> `DATABASE_URL` внутри compose автоматически указывает на Postgres `db:5432` —
> значение из `.env` при этом не трогается. Таблицы создаются при старте сами.
> Первая сборка долгая: тянется torch (CPU) и deno.

### Масштаб воркеров

По умолчанию **1 воркер** (`deploy.replicas: 1`). Очередь `Job` спроектирована под
конкурентных воркеров (`SELECT … FOR UPDATE SKIP LOCKED`), так что поднять число
безопасно — меняй `deploy.replicas` в `docker-compose.yml` или на лету:

```bash
docker compose up -d --scale worker=2
```

> ⚠️ Транскрибация — локальный Whisper на **CPU**, и **каждый** воркер держит свою копию
> модели (~2 ГБ RAM). На машине с 15 ГБ RAM три воркера уходили в своп и тормозили сильнее,
> чем один. Поднимать `replicas` есть смысл только при заметно большем RAM/числе ядер либо
> когда транскрибация уедет на GPU/внешний API. Иначе 1 — оптимум.

Пришлите боту ссылку на Reels/Shorts — через пару минут он вернёт `.pine` файлом.
`/my` пришлёт все ваши скрипты файлами (каждый с подписью), `/get <id>` — один скрипт,
`/rename <id>` — переименовать (бот переспросит новое имя).

---

## Настройка ключей и cookies

Создайте `.env` в корне проекта и заполните:

- `OPENAI_API_KEY` — ключ OpenAI (https://platform.openai.com/api-keys);
- `TELEGRAM_BOT_TOKEN` — токен от @BotFather;
- `DATABASE_URL` — нужен только для локального запуска без Docker; в compose он
  переопределяется автоматически.

Cookies настраиваются не здесь, а файлами в `cookies/` — см. раздел ниже.

> 🔒 `.env` и `cookies/` в `.gitignore` — никогда не коммить их.

---

## Cookies (YouTube и Instagram)

YouTube («Sign in to confirm you're not a bot») и Instagram («empty media response»)
почти ничего не отдают **без залогиненной сессии**. Поэтому нужны cookies авторизованных
аккаунтов, разнесённые по платформам:

```
cookies/youtube.txt     # куки youtube.com (нужны LOGIN_INFO, __Secure-3PSID, SID…)
cookies/instagram.txt   # куки instagram.com (нужны sessionid, ds_user_id, csrftoken)
```

Каталог `cookies/` монтируется в воркер read-only. Каждый новый запрос перечитывает файл,
поэтому **после обновления на хосте свежие куки подхватываются без перезапуска**.

### Автообновление из браузера (на хосте)

> ⚠️ Внутри Docker-контейнера достать куки из Chrome нельзя — там нет ни браузера, ни
> keyring ОС, которым Chrome их шифрует. Обновление делается **на хосте** скриптом
> [`scripts/refresh_cookies.py`](scripts/refresh_cookies.py) (использует `browser_cookie3`),
> а контейнер только читает готовые файлы.

#### 1. Venv под скрипт (один раз)

`refresh_cookies.py` использует `browser_cookie3` и запускается **на хосте** обычным
Python (не из Docker). Заводим под него отдельный venv, чтобы не трогать системный Python:

```bash
python3 -m venv ~/.venvs/devtrade-cookies
~/.venvs/devtrade-cookies/bin/pip install -U pip browser_cookie3
```

> Если `python3 -m venv` ругнётся на `ensurepip` — поставь `sudo apt install python3-venv`.

#### 2. Запуск вручную

Залогинься в Chrome на youtube.com и instagram.com, затем из корня проекта:

```bash
~/.venvs/devtrade-cookies/bin/python scripts/refresh_cookies.py --force   # принудительно
~/.venvs/devtrade-cookies/bin/python scripts/refresh_cookies.py           # только устаревшие
~/.venvs/devtrade-cookies/bin/python scripts/refresh_cookies.py --browser firefox
```

Если логин-куки не найдены (разлогинен / нет доступа к keyring), скрипт **не трогает**
рабочий файл и предупреждает — затереть хорошие куки пустыми нельзя.

#### 3. Автообновление каждые 10 минут (systemd --user)

> ⚠️ **Не используй cron** для Chrome на Linux: у cron нет доступа к keyring/session bus,
> которым Chrome шифрует куки, — расшифровка провалится. `systemd --user` работает внутри
> твоей сессии, поэтому keyring доступен. (Firefox хранит куки без keyring — для него cron
> сработал бы, но systemd-таймер ниже одинаково подходит обоим.)

`~/.config/systemd/user/devtrade-cookies.service`:

```ini
[Unit]
Description=devtrade: экспорт свежих cookies из браузера в cookies/

[Service]
Type=oneshot
WorkingDirectory=/home/<user>/Documents/projects/devtradebot
ExecStart=/home/<user>/.venvs/devtrade-cookies/bin/python scripts/refresh_cookies.py --force
```

`~/.config/systemd/user/devtrade-cookies.timer`:

```ini
[Unit]
Description=devtrade: обновлять cookies каждые 10 минут

[Timer]
OnBootSec=1min
OnUnitActiveSec=10min
Persistent=true

[Install]
WantedBy=timers.target
```

Включение и проверка:

```bash
systemctl --user daemon-reload
systemctl --user enable --now devtrade-cookies.timer
systemctl --user list-timers devtrade-cookies.timer        # расписание
journalctl --user -u devtrade-cookies.service -n 10        # логи последнего прогона
```

> Таймер работает, пока ты залогинен в сессию (а куки и так берутся из твоего браузера —
> логично). Чтобы крутился и без активной сессии: `loginctl enable-linger <user>`.

> ⚠️ Бери аккаунты-«расходники»: YouTube/Instagram могут флагнуть аккаунт за автоскачивание,
> а инстаграмная `sessionid` привязана к IP и живёт недолго — отсюда и нужно автообновление.

---

## Локальная разработка (без Docker)

Для отладки или батч-режима CLI пакеты можно поднять локально, но окружение придётся
собрать руками. Требуется: **Python 3.12**, **ffmpeg**, **PostgreSQL** (БД проще поднять
через `docker compose up -d db`), для YouTube — **deno**.

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu   # CPU-сборка
pip install -r requirements.txt
```

> 💡 Есть GPU + CUDA — выберите подходящую сборку PyTorch на https://pytorch.org.

Бот и воркер — в двух терминалах с активным venv и заполненным `.env`:

```bash
docker compose up -d db         # только PostgreSQL (на localhost:5433)
python -m devtrade_bot          # бот
python -m devtrade_bot.worker   # воркер
```

Батч-режим CLI (заполните `youtube_links.txt` / `insta_links.txt`):

```bash
python -m devtrade_parse all    # команды см. в разделе «Пакет devtrade_parse»
```

---

## Известные ограничения

- **Валидность PineScript не гарантирована.** Валидатор ловит типовые ошибки, но финальную
  проверку и доводку делайте в редакторе TradingView.
- **Качество стратегии зависит от транскрибации.** Whisper (`small`) может искажать термины.
- **Cookies обязательны и протухают.** YouTube/Instagram почти не отдают видео без логина —
  держите `cookies/youtube.txt` и `cookies/instagram.txt` свежими (см. «Cookies»).
- **Скорость.** Модель Whisper скачивается один раз (кэш в томе `whisper-cache`) и держится
  в памяти воркера. Дальше время ролика ≈ скачивание + транскрибация на CPU (несколько минут).
  Самый жирный апгрейд скорости — GPU (CUDA-сборка torch + проброс в контейнер).
- **Сеть.** Бот/воркер ходят в `api.telegram.org` и на YouTube/Instagram — в РФ это часто
  режется DPI (TLS-сброс по SNI). Решается VPN. Под VPN у Docker нужно снизить MTU
  (`networks.default.driver_opts` в `docker-compose.yml`, по умолчанию 1400; при `UNEXPECTED_EOF`
  пробуйте 1280) — иначе крупные TLS-пакеты рвутся.
```
