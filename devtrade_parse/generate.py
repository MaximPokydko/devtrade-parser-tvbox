"""Strategy DSL -> PineScript via OpenAI."""

import json

from openai import OpenAI

from . import config

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


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
    """Generate raw PineScript from a strategy DSL.

    Returns the model's raw output; cleanup/validation is done by validate.validate_pine.
    """
    prompt = PROMPT.format(max_lines=config.PINE_MAX_LINES)
    response = _get_client().chat.completions.create(
        model=config.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "Ты пишешь только код PineScript."},
            {"role": "user", "content": prompt + json.dumps(strategy, ensure_ascii=False)},
        ],
        temperature=0,
    )
    return response.choices[0].message.content or ""
