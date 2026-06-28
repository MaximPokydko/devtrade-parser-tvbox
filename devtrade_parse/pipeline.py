"""Оркестратор полного пайплайна: ссылка → текст → DSL → PineScript → валидация."""

from dataclasses import dataclass
from typing import Optional

from .extract import extract_strategy
from .generate import generate_pine
from .transcribe import transcribe_url
from .validate import ValidationResult, validate_pine


@dataclass
class PipelineResult:
    url: str
    source: str
    title: str
    text: str
    strategy: dict
    is_strategy: bool
    pine: Optional[str]                 # None, если стратегия не найдена
    validation: Optional[ValidationResult]


def process_url(url: str) -> PipelineResult:
    """Полный прогон одной ссылки. Используется ботом-воркером.

    Бросает исключения транскрибации/извлечения наверх — воркер сохранит их в Job.error.
    Если стратегия в тексте не найдена, возвращает результат с is_strategy=False
    и pine=None (это не ошибка).
    """
    transcript = transcribe_url(url)
    strategy = extract_strategy(transcript.text)
    is_strategy = bool(strategy.get("is_strategy"))

    pine = None
    validation = None
    if is_strategy:
        raw_pine = generate_pine(strategy)
        validation = validate_pine(raw_pine)
        pine = validation.code

    return PipelineResult(
        url=url,
        source=transcript.source,
        title=transcript.title,
        text=transcript.text,
        strategy=strategy,
        is_strategy=is_strategy,
        pine=pine,
        validation=validation,
    )
