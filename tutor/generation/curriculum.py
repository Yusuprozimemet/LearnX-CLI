import logging

from tutor.constants import (
    DIFFICULTY_CONTEXT,
    DIFFICULTY_MULTIPLIERS,
    OVERHEAD_WORDS,
    WORDS_PER_COMPLEXITY,
    WPM,
)
from tutor.exceptions import LLMError
from tutor.infra.llm import load_prompt, parse_json_response
from tutor.models import Chunk, DocProfile, TeachingUnit

log = logging.getLogger(__name__)


def plan(
    chunks: list[Chunk],
    profile: DocProfile,
    duration_min: int,
    llm_fn,
    difficulty: str = "beginner",
    topic: str | None = None,
) -> list[TeachingUnit]:
    summaries = "\n".join(f"[{c.chunk_id}] {c.summary}" for c in chunks)
    difficulty_context = DIFFICULTY_CONTEXT.get(difficulty, DIFFICULTY_CONTEXT["beginner"])

    prompt = load_prompt("curriculum.txt").format(
        doc_title=profile.filepath,
        duration_min=duration_min,
        difficulty=difficulty,
        difficulty_context=difficulty_context,
        summaries=summaries,
    )

    if topic:
        topic_instruction = (
            f'IMPORTANT: You must include a unit that covers the topic "{topic}". '
            "If the source document does not mention it, create a unit that acknowledges "
            "it is out of scope but explains why it matters in relation to what was covered."
        )
        prompt = topic_instruction + "\n\n" + prompt

    messages = [{"role": "user", "content": prompt}]
    log.info("Planning curriculum for %d chunks, %d min target", len(chunks), duration_min)

    raw = llm_fn(messages, call_type="curriculum")
    try:
        data = parse_json_response(raw)
    except LLMError:
        retry_messages = messages + [
            {"role": "assistant", "content": raw},
            {"role": "user", "content": "Your previous response could not be parsed as JSON. Reply with the raw JSON array only, no other text."},
        ]
        raw = llm_fn(retry_messages, call_type="curriculum")
        data = parse_json_response(raw)

    if not isinstance(data, list) or len(data) == 0:
        raise LLMError("Curriculum planner returned no units")

    total_budget = duration_min * WPM - OVERHEAD_WORDS
    total_complexity = sum(int(u.get("complexity", 2)) for u in data)
    if total_complexity == 0:
        total_complexity = len(data)
    multiplier = DIFFICULTY_MULTIPLIERS.get(difficulty, 1.0)
    base = total_budget / total_complexity

    units: list[TeachingUnit] = []
    for i, u in enumerate(data):
        complexity = max(1, min(3, int(u.get("complexity", 2))))
        word_budget = max(
            round(base * complexity * multiplier),
            WORDS_PER_COMPLEXITY[1],  # floor: min 200 words even for advanced
        )
        units.append(
            TeachingUnit(
                unit=i + 1,
                concept=u.get("concept", f"Unit {i + 1}"),
                source_sections=u.get("source_sections", []),
                complexity=complexity,
                word_budget=word_budget,
                key_facts=u.get("key_facts", []),
                common_misconception=u.get("common_misconception", ""),
                good_analogy=u.get("good_analogy", ""),
                question_style=u.get("question_style", "recall"),
                memory_hook=u.get("memory_hook", ""),
                prerequisite_concepts=u.get("prerequisite_concepts", []),
            )
        )

    log.info("Curriculum planned: %d units", len(units))
    return units
