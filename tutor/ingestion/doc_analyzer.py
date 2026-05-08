import re
from pathlib import Path

from tutor.constants import STRATEGY_A_TOKEN_LIMIT, STRATEGY_B_TOKEN_LIMIT
from tutor.exceptions import IngestionError
from tutor.models import DocProfile


def analyze(filepath: str) -> DocProfile:
    path = Path(filepath)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise IngestionError(f"Cannot read file: {filepath}") from e

    raw_bytes = path.stat().st_size
    word_count = len(text.split())
    estimated_tokens = int(word_count * 1.3)

    if estimated_tokens <= STRATEGY_A_TOKEN_LIMIT:
        strategy = "A"
    elif estimated_tokens <= STRATEGY_B_TOKEN_LIMIT:
        strategy = "B"
    else:
        strategy = "C"

    section_count = len(re.findall(r"^#{1,3}\s", text, re.MULTILINE))
    has_code_blocks = "```" in text
    language_hint = "java" if "```java" in text.lower() else "general"

    return DocProfile(
        filepath=filepath,
        raw_bytes=raw_bytes,
        estimated_tokens=estimated_tokens,
        strategy=strategy,
        section_count=section_count,
        has_code_blocks=has_code_blocks,
        language_hint=language_hint,
    )
