"""devtrade_parse — pipeline "trading video -> trade idea -> PineScript".

Public API is imported lazily so that `import devtrade_parse` does not pull heavy
dependencies (whisper/torch) unless they are actually used:
    process_url(url)          — full pipeline for one link (used by the bot)
    transcribe_url(url)       — video -> text
    extract_strategy(text)    — text -> strategy DSL (JSON)
    generate_pine(strategy)   — DSL -> PineScript
    validate_pine(code)       — static check/fix of PineScript
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

# attribute name -> (module, name in module)
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
