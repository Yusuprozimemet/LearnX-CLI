import logging

from tutor.constants import OVERHEAD_WORDS, WPM
from tutor.exceptions import LLMError
from tutor.infra.llm import load_prompt, parse_json_response
from tutor.models import Chunk, DocProfile, TeachingUnit

log = logging.getLogger(__name__)

_DIFFICULTY_CONTEXT = {
    "beginner": "The student has never written Java before. Use more scaffolding and mandatory analogies.",
    "intermediate": "The student has written Java for 3 months. Assume JVM basics are known.",
    "advanced": "The student knows OOP basics but makes design-level mistakes. Focus on contracts and concurrency.",
}


def plan(
    chunks: list[Chunk],
    profile: DocProfile,
    duration_min: int,
    llm_fn,
    difficulty: str = "beginner",
) -> list[TeachingUnit]:
    summaries = "\n".join(f"[{c.chunk_id}] {c.summary}" for c in chunks)
    difficulty_context = _DIFFICULTY_CONTEXT.get(difficulty, _DIFFICULTY_CONTEXT["beginner"])

    prompt = load_prompt("curriculum.txt").format(
        doc_title=profile.filepath,
        duration_min=duration_min,
        difficulty=difficulty,
        difficulty_context=difficulty_context,
        summaries=summaries,
    )

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
    base = total_budget / total_complexity

    units: list[TeachingUnit] = []
    for i, u in enumerate(data):
        complexity = max(1, min(3, int(u.get("complexity", 2))))
        word_budget = round(base * complexity)
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
