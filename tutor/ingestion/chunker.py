import logging
import re

from tutor.constants import MAX_CHUNK_TOKENS, MIN_CHUNK_TOKENS
from tutor.exceptions import IngestionError
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
            "Document has no headings — falling back to sliding window chunking. "
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
    raise NotImplementedError(
        "Strategy C (sliding window) — implement on Day 3.\n"
        "This document is too large for current ingestion strategies. "
        "Add ## headings to enable Strategy B, or use a smaller document."
    )


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
