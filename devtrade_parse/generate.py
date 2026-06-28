"""DSL-стратегия → PineScript через OpenAI."""

import json

from . import config
from .openai_client import get_client

PROMPT = """
Ты — разработчик PineScript.

На основе структуры стратегии сгенерируй PineScript (до {max_lines} строк).

Требования:
- version=5
- strategy()
- entry/exit логика
- чистый код без комментариев лишних

Отвечай строго валидным pinescript.
Без markdown.
Без ```pinescript.
Без пояснений.

Стратегия:
"""


def generate_pine(strategy: dict) -> str:
    """Генерирует PineScript-код по DSL-стратегии (сырой ответ модели).

    Возвращает строку с кодом. Очистку/валидацию выполняет validate.validate_pine.
    """
    prompt = PROMPT.format(max_lines=config.PINE_MAX_LINES)
    response = get_client().chat.completions.create(
        model=config.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "Ты пишешь только код PineScript."},
            {"role": "user", "content": prompt + json.dumps(strategy, ensure_ascii=False)},
        ],
        temperature=0,
    )
    return response.choices[0].message.content or ""
