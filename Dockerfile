# Общий образ для бота и воркера (различаются только командой запуска).
FROM python:3.12-slim

# deno нужен yt-dlp для решения YouTube «n challenge» (иначе доступны только превью).
# Берём готовый бинарь из официального образа на Docker Hub — надёжнее, чем
# `curl deno.land/install.sh | sh` (тот падает, если TLS до dl.deno.land/GitHub режется).
COPY --from=denoland/deno:bin /deno /usr/local/bin/deno
ENV DENO_PATH=/usr/local/bin/deno

# Системные зависимости: ffmpeg — извлечение аудио из видео (yt-dlp postprocessor).
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Кэш Whisper-моделей: whisper.load_model уважает XDG_CACHE_HOME, том /cache
# переживает рестарты — модель не качается заново при каждом старте воркера.
ENV XDG_CACHE_HOME=/cache

# torch ставим отдельно из CPU-индекса (на сервере без GPU), иначе с PyPI прилетит
# тяжёлая CUDA-сборка. Остальное — из requirements.txt (torch там уже удовлетворён).
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements.txt

COPY devtrade_parse ./devtrade_parse
COPY devtrade_bot ./devtrade_bot

# Команда по умолчанию — бот; воркер переопределяет её в docker-compose.
CMD ["python", "-m", "devtrade_bot"]
