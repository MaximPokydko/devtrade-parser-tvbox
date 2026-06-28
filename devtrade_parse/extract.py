"""Текст → DSL-стратегия (JSON) через OpenAI."""

import json

from . import config
from .openai_client import get_client

PROMPT = """
Ты — трейдер-аналитик.

Определи, есть ли в тексте торговая стратегия.

Если НЕТ:
верни:
{"is_strategy": false}

Если ДА:
верни строго JSON:
{
  "is_strategy": true,
  "type": "",
  "entry": "",
  "exit": "",
  "indicators": [],
  "logic": ""
}
Отвечай строго валидным JSON.
Без markdown.
Без ```json.
Без пояснений.

Текст:
"""


def extract_strategy(text: str) -> dict:
    """Извлекает структуру стратегии из текста.

    Возвращает dict вида {"is_strategy": bool, ...}.
    Бросает ValueError, если модель вернула невалидный JSON.
    """
    response = get_client().chat.completions.create(
        model=config.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "Ты строгий парсер. Отвечай только JSON."},
            {"role": "user", "content": PROMPT + text},
        ],
        temperature=0,
    )

    content = response.choices[0].message.content
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"LLM вернул невалидный JSON: {exc}") from exc
