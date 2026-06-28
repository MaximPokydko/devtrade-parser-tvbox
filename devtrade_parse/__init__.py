"""devtrade_parse — пайплайн «видео про трейдинг → торговая идея → PineScript».

Публичный API (импортируется лениво, чтобы `import devtrade_parse` не тянул
тяжёлые зависимости вроде whisper/torch без необходимости):
    process_url(url)          — полный пайплайн для одной ссылки (используется ботом)
    transcribe_url(url)       — видео → текст
    extract_strategy(text)    — текст → DSL-стратегия (JSON)
    generate_pine(strategy)   — DSL → PineScript
    validate_pine(code)       — статическая проверка/починка PineScript
"""

import importlib

__all__ = [
    "process_url",
    "PipelineResult",
    "transcribe_url",
    "extract_strategy",
    "generate_pine",
    "validate_pine",
    "ValidationResult",
    "ValidationIssue",
]

# имя атрибута -> (модуль, имя в модуле)
_LAZY = {
    "process_url": ("pipeline", "process_url"),
    "PipelineResult": ("pipeline", "PipelineResult"),
    "transcribe_url": ("transcribe", "transcribe_url"),
    "extract_strategy": ("extract", "extract_strategy"),
    "generate_pine": ("generate", "generate_pine"),
    "validate_pine": ("validate", "validate_pine"),
    "ValidationResult": ("validate", "ValidationResult"),
    "ValidationIssue": ("validate", "ValidationIssue"),
}


def __getattr__(name):  # PEP 562
    target = _LAZY.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = importlib.import_module(f".{target[0]}", __name__)
    return getattr(module, target[1])
