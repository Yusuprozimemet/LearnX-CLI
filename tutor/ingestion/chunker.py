import logging
import re

from tutor.constants import (
    MAX_CHUNK_TOKENS,
    MIN_CHUNK_TOKENS,
    STRATEGY_C_OVERLAP_TOKENS,
    STRATEGY_C_WINDOW_TOKENS,
)
from tutor.ingestion import parse_content
from tutor.models import Chunk, DocProfile

log = logging.getLogger(__name__)


def chunk(text: str, profile: DocProfile) -> list[Chunk]:
    if profile.strategy == "A":
        chunks = _strategy_a(text)
    elif profile.strategy == "B":
        chunks = _strategy_b(text)
    else:
        chunks = _strategy_c(text)
    return _apply_quality_rules(chunks)


def _slugify(heading: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", heading.lower()).strip("_")


def _estimate_tokens(text: str) -> int:
    return int(len(text.split()) * 1.3)


def _strategy_a(text: str) -> list[Chunk]:
    return [
        Chunk(
            chunk_id="full_doc",
            breadcrumb="Full Document",
            heading="Full Document",
            level=0,
            token_count=_estimate_tokens(text),
            text=text,
        )
    ]


def _strategy_b(text: str) -> list[Chunk]:
    sections = re.split(r"\n(?=## )", text)
    sections = [s for s in sections if s.strip()]

    if len(sections) < 2:
        log.warning(
            "Document has no headings — falling back to Strategy C (sliding window). "
            "Consider adding ## headings to improve chunk quality."
        )
        return _strategy_c(text)

    chunks: list[Chunk] = []
    for section in sections:
        lines = section.strip().split("\n")
        heading_line = lines[0].lstrip("#").strip()
        chunks.extend(_split_section(section, heading_line, parent_heading=None))

    return chunks


def _split_section(section: str, heading: str, parent_heading: str | None) -> list[Chunk]:
    token_count = _estimate_tokens(section)

    if token_count <= MAX_CHUNK_TOKENS:
        prefix = f"## {parent_heading}\n\n" if parent_heading else ""
        return [
            Chunk(
                chunk_id=_slugify(heading),
                breadcrumb=f"{parent_heading} > {heading}" if parent_heading else heading,
                heading=heading,
                level=2,
                token_count=token_count,
                text=prefix + section,
            )
        ]

    subsections = re.split(r"\n(?=### )", section)
    if len(subsections) < 2:
        prefix = f"## {parent_heading}\n\n" if parent_heading else ""
        return [
            Chunk(
                chunk_id=_slugify(heading),
                breadcrumb=heading,
                heading=heading,
                level=2,
                token_count=token_count,
                text=prefix + section,
            )
        ]

    result: list[Chunk] = []
    for sub in subsections:
        sub_lines = sub.strip().split("\n")
        sub_heading = sub_lines[0].lstrip("#").strip()
        prefix = f"## {heading}\n\n"
        result.append(
            Chunk(
                chunk_id=_slugify(f"{heading}_{sub_heading}"),
                breadcrumb=f"{heading} > {sub_heading}",
                heading=sub_heading,
                level=3,
                token_count=_estimate_tokens(sub),
                text=prefix + sub,
            )
        )
    return result


def _strategy_c(text: str) -> list[Chunk]:
    word_window = int(STRATEGY_C_WINDOW_TOKENS / 1.3)
    word_overlap = int(STRATEGY_C_OVERLAP_TOKENS / 1.3)

    words = text.split()
    chunks: list[Chunk] = []
    start = 0
    idx = 0

    while start < len(words):
        end = min(start + word_window, len(words))
        window_words = words[start:end]

        if end < len(words):
            window_text = " ".join(window_words)
            last_period = window_text.rfind(". ")
            if last_period > len(window_text) // 2:
                window_text = window_text[: last_period + 1]
                window_words = window_text.split()

        chunk_text = " ".join(window_words)
        token_count = int(len(window_words) * 1.3)

        chunks.append(
            Chunk(
                chunk_id=f"window_{idx:03d}",
                breadcrumb=f"Window {idx + 1}",
                heading=f"Window {idx + 1}",
                level=0,
                token_count=token_count,
                text=chunk_text,
                has_code=False,
                overlapping=(idx > 0),
            )
        )

        idx += 1
        step = word_window - word_overlap
        start += max(step, 1)

    return chunks


def _apply_quality_rules(chunks: list[Chunk]) -> list[Chunk]:
    merged: list[Chunk] = []
    for c in chunks:
        if c.token_count < MIN_CHUNK_TOKENS and merged:
            prev = merged[-1]
            prev.text += "\n\n" + c.text
            prev.token_count = _estimate_tokens(prev.text)
        else:
            merged.append(c)

    for c in merged:
        parse_content.enrich(c)

    return merged
