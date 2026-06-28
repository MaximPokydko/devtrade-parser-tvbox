# devtrade_bot — вариант tvbox

Облегчённая сборка для слабого «всегда включённого» хоста (TV-приставка Rombica Smart Box 4K:
Hisilicon, **armv7l / 32-бит, 1 ГБ RAM, Debian CLI**).

Отличия от основной версии (ветки `dev`/`main`):

| | основная | **tvbox** |
|---|---|---|
| Транскрибация | локальный Whisper (torch) | **OpenAI audio API** (`gpt-4o-mini-transcribe`) |
| БД | PostgreSQL (Docker) | **SQLite** (файл `devtrade.db`) |
| Тяжёлые зависимости | torch, whisper, asyncpg | **нет** — чистый Python, без компиляции |

Вся ML-нагрузка уходит в облако: коробка только скачивает аудио (yt-dlp) и шлёт HTTP.

---

## Установка на коробке

```bash
sudo apt update && sudo apt install -y python3-venv ffmpeg
python3 -m venv venv
source venv/bin/activate
pip install -U pip
pip install -r requirements.txt        # без torch — ставится быстро, без сборки
```

## Настройка `.env`

```env
OPENAI_API_KEY=sk-proj-...
OPENAI_TRANSCRIBE_MODEL=gpt-4o-mini-transcribe
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
DATABASE_URL=sqlite+aiosqlite:///devtrade.db
# Cookies: на коробке нет браузера → только файл (экспорт ЗАЛОГИНЕННОЙ сессии, Netscape-формат)
COOKIES_FILE=cookies.txt
```

## Фикс нестабильной сети (приоритет IPv4)

Если ловишь `Network is unreachable [Errno 101]` — у коробки кривой IPv6. Заставь систему
предпочитать IPv4:

```bash
echo 'precedence ::ffff:0:0/96 100' | sudo tee -a /etc/gai.conf
```

## Запуск

Два процесса (оба лёгкие, без Whisper):

```bash
python -m devtrade_bot          # приём ссылок
python -m devtrade_bot.worker   # обработка очереди
```

Для постоянной работы — обернуть в systemd-юниты или `nohup ... &`. БД (`devtrade.db`)
создаётся автоматически при первом старте.

---

## Ограничения коробки

- **Целевой источник — Instagram Reels.** У YouTube есть JS-«n challenge», для которого нужен
  `deno`, а **под 32-бит ARM сборок deno нет** (остаётся капризный `node`+EJS). У Reels этой
  проблемы нет.
- Скорость теперь зависит от сети (аплоад аудио в OpenAI) и rate-limit OpenAI, а не от CPU.
- Стоимость: ~полцента-цент за один полный прогон «ссылка → PineScript».
