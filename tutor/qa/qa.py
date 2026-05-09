import json
import logging
from datetime import datetime
from pathlib import Path

from tutor.exceptions import LLMError
from tutor.infra.llm import LLMFn
from tutor.models import Chunk, QAExchange, SessionLog, TeachingUnit

log = logging.getLogger(__name__)

QA_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "qa.txt"


def answer(
    question: str,
    current_unit: TeachingUnit,
    all_chunks: list[Chunk],
    session: SessionLog,
    llm_fn: LLMFn,
    position_seconds: int = 0,
) -> str:
    context = _build_context(current_unit, all_chunks, session)
    log.debug("Q&A context length: %d chars", len(context))
    prompt = _load_qa_prompt(current_unit.concept)
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"{context}\n\nStudent's question: {question}"},
    ]

    try:
        raw = llm_fn(messages, call_type="qa")
    except LLMError as e:
        log.error("Q&A LLM call failed: %s", e)
        return f"Sorry — could not generate an answer right now. ({e})"

    answer_text = raw.strip()
    _append_exchange(session, current_unit, question, answer_text, position_seconds)
    return answer_text


def _build_context(
    current_unit: TeachingUnit,
    all_chunks: list[Chunk],
    session: SessionLog,
) -> str:
    chunk_map = {c.chunk_id: c for c in all_chunks}

    current_chunks = [chunk_map[s] for s in current_unit.source_sections if s in chunk_map]

    recent = session.exchanges[-3:] if session.exchanges else []

    parts: list[str] = []

    if current_chunks:
        parts.append("=== Source Content ===")
        for chunk in current_chunks:
            parts.append(f"[{chunk.breadcrumb}]\n{chunk.text}")

    if recent:
        parts.append("\n=== Prior Questions This Session ===")
        for ex in recent:
            parts.append(f"Q: {ex.question}\nA: {ex.answer}")

    return "\n\n".join(parts) if parts else "No source content available."


def _append_exchange(
    session: SessionLog,
    unit: TeachingUnit,
    question: str,
    answer: str,
    position_seconds: int,
) -> None:
    exchange = QAExchange(
        id=len(session.exchanges) + 1,
        unit_number=unit.unit,
        unit_concept=unit.concept,
        position_seconds=position_seconds,
        question=question,
        answer=answer,
        source_sections=unit.source_sections,
        timestamp=datetime.utcnow().isoformat(),
    )
    session.exchanges.append(exchange)
    _save_session(session)


def _save_session(session: SessionLog) -> None:
    from dataclasses import asdict

    path = Path("tutorial.session.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(session), f, indent=2, ensure_ascii=False)


def _load_qa_prompt(concept: str) -> str:
    try:
        template = QA_PROMPT_PATH.read_text(encoding="utf-8")
        return template.replace("{concept}", concept)
    except FileNotFoundError:
        return (
            f"Answer the student's question about: {concept}. "
            "Be concise, cite sources, end with a follow-up question."
        )
