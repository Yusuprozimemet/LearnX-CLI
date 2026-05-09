from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path

from tutor.audio import sanitizer
from tutor.constants import SUMMARY_CACHE_DIR
from tutor.infra.llm import LLMFn, load_prompt
from tutor.models import Chunk, DialogueLine, TeachingUnit

log = logging.getLogger(__name__)

NARRATE_VERSION = "narrate_v1"
_WORDS_PER_SOURCE_WORD = 1.25


def narrate_all(
    chunks: list[Chunk],
    doc_title: str,
    llm_fn: LLMFn,
    cache_dir: str = SUMMARY_CACHE_DIR,
) -> tuple[list[TeachingUnit], list[list[DialogueLine]]]:
    """Narrate every chunk in document order. Returns (units, all_lines)."""
    units: list[TeachingUnit] = []
    all_lines: list[list[DialogueLine]] = []
    total = len(chunks)

    for i, chunk in enumerate(chunks):
        lines = _narrate_chunk(chunk, i + 1, total, doc_title, llm_fn, cache_dir)
        units.append(_chunk_to_unit(chunk, i + 1))
        all_lines.append(lines)

    return units, all_lines


def _chunk_to_unit(chunk: Chunk, unit_index: int) -> TeachingUnit:
    word_budget = max(100, int(len(chunk.text.split()) * _WORDS_PER_SOURCE_WORD))
    return TeachingUnit(
        unit=unit_index,
        concept=chunk.heading or f"Section {unit_index}",
        source_sections=[chunk.chunk_id],
        complexity=1,
        word_budget=word_budget,
        key_facts=[],
        common_misconception="",
        good_analogy="",
        question_style="recall",
        memory_hook="",
    )


def _narrate_chunk(
    chunk: Chunk,
    section_index: int,
    total_sections: int,
    doc_title: str,
    llm_fn: LLMFn,
    cache_dir: str,
) -> list[DialogueLine]:
    cache_key = hashlib.md5((chunk.chunk_id + chunk.text + NARRATE_VERSION).encode()).hexdigest()
    cache_file = Path(cache_dir) / f"{cache_key}.narrate.json"

    if cache_file.exists():
        log.debug(
            "Cache hit for narration %d/%d (%s)", section_index, total_sections, chunk.heading
        )
        raw = json.loads(cache_file.read_text(encoding="utf-8"))
        return [DialogueLine(**d) for d in raw]

    word_budget = max(100, int(len(chunk.text.split()) * _WORDS_PER_SOURCE_WORD))
    prompt = load_prompt("narrate.txt").format(
        doc_title=doc_title,
        section_index=section_index,
        total_sections=total_sections,
        heading=chunk.heading,
        word_budget=word_budget,
        section_text=chunk.text,
    )

    log.info("Narrating section %d/%d: %s", section_index, total_sections, chunk.heading)
    raw_text = llm_fn([{"role": "user", "content": prompt}], call_type="dialogue")
    lines = _parse_narration(raw_text, section_index)

    if not lines:
        log.warning("No lines parsed for section %d, retrying", section_index)
        raw_text = llm_fn([{"role": "user", "content": prompt}], call_type="dialogue")
        lines = _parse_narration(raw_text, section_index)

    for line in lines:
        line.text = sanitizer.apply(line.text)

    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    cache_file.write_text(
        json.dumps(
            [
                {"speaker": ln.speaker, "text": ln.text, "unit_number": ln.unit_number}
                for ln in lines
            ]
        ),
        encoding="utf-8",
    )

    return lines


def _parse_narration(raw: str, unit_number: int) -> list[DialogueLine]:
    lines: list[DialogueLine] = []
    for raw_line in raw.split("\n"):
        stripped = raw_line.strip()
        if not stripped:
            continue
        match = re.match(r"^ALEX\s*[:\-]\s*(.+)", stripped, re.IGNORECASE)
        if match:
            lines.append(
                DialogueLine(speaker="ALEX", text=match.group(1).strip(), unit_number=unit_number)
            )
        else:
            log.debug("Skipping unparseable narration line: %s", stripped[:80])
    return lines
