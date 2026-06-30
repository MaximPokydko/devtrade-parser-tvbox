"""Full pipeline orchestration: link -> text -> DSL -> PineScript -> validation."""

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
    pine: Optional[str]                 # None if no strategy was found
    validation: Optional[ValidationResult]


def process_url(url: str) -> PipelineResult:
    """Run the full pipeline for one link. Used by the bot worker.

    Propagates transcription/extraction exceptions to the caller (worker stores them
    in Job.error). If no strategy is found, returns is_strategy=False and pine=None
    (not an error).
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
