import hashlib
import json
import logging
import re
from pathlib import Path

from tutor.constants import PROMPT_VERSION, SUMMARY_CACHE_DIR
from tutor.exceptions import LLMError
from tutor.infra.llm import LIMITS, LLMFn, load_prompt
from tutor.models import Chunk, DialogueLine, TeachingUnit

log = logging.getLogger(__name__)


def generate(
    unit: TeachingUnit,
    source_chunks: list[Chunk],
    fmt: str,
    llm_fn: LLMFn,
    difficulty: str = "beginner",
    cache_dir: str = SUMMARY_CACHE_DIR,
) -> list[DialogueLine]:
    cache_key = hashlib.md5(
        (unit.concept + str(unit.word_budget) + fmt + difficulty + PROMPT_VERSION).encode()
    ).hexdigest()
    cache_file = Path(cache_dir) / f"{cache_key}.dialogue.json"

    if cache_file.exists():
        log.debug("Cache hit for dialogue unit %d (%s)", unit.unit, unit.concept)
        raw_lines = json.loads(cache_file.read_text(encoding="utf-8"))
        return [DialogueLine(**d) for d in raw_lines]

    relevant = [c for c in source_chunks if c.chunk_id in unit.source_sections]
    if not relevant:
        relevant = source_chunks[:2]
    source_text = "\n\n".join(f"## {c.heading}\n{c.text}" for c in relevant)
    source_text = _truncate_source(source_text, LIMITS["max_source_tokens"])

    unit_json = json.dumps(
        {
            "concept": unit.concept,
            "complexity": unit.complexity,
            "word_budget": unit.word_budget,
            "key_facts": unit.key_facts,
            "common_misconception": unit.common_misconception,
            "good_analogy": unit.good_analogy,
            "question_style": unit.question_style,
            "memory_hook": unit.memory_hook,
        },
        indent=2,
    )

    speaker_constraint = (
        "IMPORTANT: Only use ALEX and SAM speakers. Do NOT use MAYA."
        if fmt == "dual-tutor"
        else "IMPORTANT: Only use ALEX and MAYA speakers. Do NOT use SAM."
    )
    system_prompt = (
        load_prompt("dialogue.txt").format(
            format=fmt,
            word_budget=unit.word_budget,
        )
        + f"\n\n{speaker_constraint}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Unit:\n{unit_json}\n\nSource:\n{source_text}"},
    ]

    log.info("Generating dialogue for unit %d: %s", unit.unit, unit.concept)
    raw = llm_fn(messages, call_type="dialogue")
    lines = _parse_dialogue(raw, unit.unit)

    if len(lines) < 4:
        log.warning("Only %d lines parsed, retrying dialogue generation", len(lines))
        raw = llm_fn(messages, call_type="dialogue")
        lines = _parse_dialogue(raw, unit.unit)
        if len(lines) < 4:
            raise LLMError(
                f"Dialogue generation returned fewer than 4 lines for unit {unit.unit}: {unit.concept}"
            )

    lines = _normalize_speakers(lines, fmt)
    _validate_speakers(lines, fmt)

    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    cache_file.write_text(
        json.dumps(
            [{"speaker": ln.speaker, "text": ln.text, "unit_number": ln.unit_number} for ln in lines]
        ),
        encoding="utf-8",
    )

    return lines


def _truncate_source(text: str, max_tokens: int) -> str:
    words = text.split()
    max_words = int(max_tokens / 1.3)
    if len(words) <= max_words:
        return text
    log.warning(
        "Source text truncated from %d to %d words for context limit", len(words), max_words
    )
    return " ".join(words[:max_words])


def _parse_dialogue_line(raw_line: str, unit_number: int) -> DialogueLine | None:
    match = re.match(r"^(ALEX|MAYA|SAM)\s*[:\-]\s*(.+)", raw_line.strip(), re.IGNORECASE)
    if not match:
        return None
    return DialogueLine(
        speaker=match.group(1).upper(),
        text=match.group(2).strip(),
        unit_number=unit_number,
    )


def _normalize_speakers(lines: list[DialogueLine], fmt: str) -> list[DialogueLine]:
    """Remap speakers so the output matches the requested format."""
    if fmt == "dual-tutor":
        return [
            DialogueLine(
                speaker="SAM" if ln.speaker == "MAYA" else ln.speaker,
                text=ln.text,
                unit_number=ln.unit_number,
            )
            for ln in lines
        ]
    return [
        DialogueLine(
            speaker="MAYA" if ln.speaker == "SAM" else ln.speaker,
            text=ln.text,
            unit_number=ln.unit_number,
        )
        for ln in lines
    ]


def _validate_speakers(lines: list[DialogueLine], fmt: str) -> None:
    speakers = {line.speaker for line in lines}
    if fmt == "tutor-student":
        if "ALEX" not in speakers:
            raise LLMError("tutor-student dialogue missing ALEX lines")
        if "SAM" in speakers:
            raise LLMError("tutor-student dialogue contains SAM — wrong format")
    elif fmt == "dual-tutor":
        if "MAYA" in speakers:
            raise LLMError("dual-tutor dialogue contains MAYA — wrong format")
        expected = {"ALEX", "SAM"}
        if not expected.issubset(speakers):
            raise LLMError(f"dual-tutor dialogue missing speakers: {expected - speakers}")


def _parse_dialogue(raw: str, unit_number: int) -> list[DialogueLine]:
    lines: list[DialogueLine] = []
    for raw_line in raw.split("\n"):
        if not raw_line.strip():
            continue
        parsed = _parse_dialogue_line(raw_line, unit_number)
        if parsed:
            lines.append(parsed)
        else:
            log.debug("Skipping unparseable line: %s", raw_line[:80])
    return lines
