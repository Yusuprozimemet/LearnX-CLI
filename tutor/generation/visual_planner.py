import hashlib
import json
import logging
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from tutor.constants import SUMMARY_CACHE_DIR
from tutor.exceptions import LLMError
from tutor.infra.llm import load_prompt, parse_json_response
from tutor.models import TeachingUnit, VisualSpec

log = logging.getLogger(__name__)

VISUAL_PROMPT_VERSION = "visual_v1"
VALID_DIAGRAM_TYPES = frozenset(
    {"class_diagram", "flowchart", "code_comparison", "concept_map", "none"}
)


def plan_visuals(
    units_json_path: Path,
    doc_title: str,
    session: str,
    llm_fn: Callable,
    difficulty: str,
    video_dir: Path,
    no_cache: bool = False,
) -> list[VisualSpec]:
    """
    Read units from units_json_path, generate one VisualSpec per unit via LLM.
    Returns [title_card, unit_1, ..., unit_N, outro].
    Writes tutorial.visuals.json to video_dir.
    """
    raw_units = json.loads(units_json_path.read_text(encoding="utf-8"))
    for u in raw_units:
        u.setdefault("prerequisite_concepts", [])
    units = [TeachingUnit(**u) for u in raw_units]

    video_dir.mkdir(parents=True, exist_ok=True)

    specs: list[VisualSpec] = [_build_title_card(doc_title, units, session)]
    for unit in units:
        cache_file = _cache_path(unit, difficulty)
        if no_cache and cache_file.exists():
            cache_file.unlink()
        specs.append(_plan_unit(unit, llm_fn, difficulty, cache_file))
    specs.append(_build_outro(units))

    visuals_path = video_dir / "tutorial.visuals.json"
    visuals_path.write_text(
        json.dumps([asdict(s) for s in specs], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log.info("Visual specs written to %s (%d entries)", visuals_path, len(specs))
    return specs


def _plan_unit(
    unit: TeachingUnit,
    llm_fn: Callable,
    difficulty: str,
    cache_file: Path,
) -> VisualSpec:
    if cache_file.exists():
        log.debug("Cache hit for visual spec unit %d (%s)", unit.unit, unit.concept)
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        return VisualSpec(**data)

    prompt = load_prompt("visual.txt")
    unit_context = json.dumps(
        {
            "concept": unit.concept,
            "key_facts": unit.key_facts,
            "common_misconception": unit.common_misconception,
            "good_analogy": unit.good_analogy,
            "memory_hook": unit.memory_hook,
            "word_budget": unit.word_budget,
            "difficulty": difficulty,
        },
        indent=2,
    )
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": unit_context},
    ]

    log.info("Generating visual spec for unit %d: %s", unit.unit, unit.concept)
    try:
        raw = llm_fn(messages, call_type="visual")
        spec = _parse_visual_response(raw, unit)
    except Exception as exc:
        log.warning(
            "Visual spec failed for unit %d (%s): %s — using fallback",
            unit.unit,
            unit.concept,
            exc,
        )
        spec = _fallback_spec(unit)

    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(
        json.dumps(asdict(spec), ensure_ascii=False),
        encoding="utf-8",
    )
    return spec


def _parse_visual_response(raw: str, unit: TeachingUnit) -> VisualSpec:
    try:
        data = parse_json_response(raw)
    except LLMError:
        log.warning("Cannot parse visual spec JSON for unit %d", unit.unit)
        return _fallback_spec(unit)

    if not isinstance(data, dict):
        log.warning("Visual spec is not a JSON object for unit %d", unit.unit)
        return _fallback_spec(unit)

    diagram_type = data.get("diagram_type", "none")
    if diagram_type not in VALID_DIAGRAM_TYPES:
        log.warning(
            "Unknown diagram_type %r for unit %d — falling back to 'none'", diagram_type, unit.unit
        )
        diagram_type = "none"

    diagram_spec = data.get("diagram_spec")
    diagram_type, diagram_spec = _validate_diagram(diagram_type, diagram_spec, unit.unit)

    return VisualSpec(
        unit_index=unit.unit,
        slide_type="unit",
        concept=unit.concept,
        hook_question=str(data.get("hook_question", "")),
        key_points=list(data.get("key_points", unit.key_facts[:5])),
        code_snippet=data.get("code_snippet") or None,
        diagram_type=diagram_type,
        diagram_spec=diagram_spec,
        memory_hook=str(data.get("memory_hook", unit.memory_hook)),
        analogy=unit.good_analogy,
    )


def _validate_diagram(diagram_type: str, diagram_spec: object, unit_idx: int) -> tuple[str, object]:
    if diagram_type in ("class_diagram", "flowchart", "concept_map"):
        if not isinstance(diagram_spec, str) or not _looks_like_dot(diagram_spec):
            log.warning("diagram_spec for unit %d is not valid DOT — setting to 'none'", unit_idx)
            return "none", None
    elif diagram_type == "code_comparison":
        if not isinstance(diagram_spec, dict) or not all(
            k in diagram_spec for k in ("wrong", "right")
        ):
            log.warning(
                "code_comparison spec for unit %d is not a valid dict — setting to 'none'", unit_idx
            )
            return "none", None
    else:
        diagram_spec = None
    return diagram_type, diagram_spec


def _fallback_spec(unit: TeachingUnit) -> VisualSpec:
    return VisualSpec(
        unit_index=unit.unit,
        slide_type="unit",
        concept=unit.concept,
        hook_question=f"What do you know about {unit.concept}?",
        key_points=unit.key_facts[:5],
        code_snippet=None,
        diagram_type="none",
        diagram_spec=None,
        memory_hook=unit.memory_hook,
        analogy=unit.good_analogy,
    )


def _build_title_card(doc_title: str, units: list[TeachingUnit], doc_source: str) -> VisualSpec:
    n = len(units)
    return VisualSpec(
        unit_index=0,
        slide_type="title_card",
        title=doc_title,
        subtitle=f"{n} unit{'s' if n != 1 else ''} - beginner",
        doc_source=doc_source,
    )


def _build_outro(units: list[TeachingUnit]) -> VisualSpec:
    return VisualSpec(
        unit_index=len(units) + 1,
        slide_type="outro",
        memory_hooks=[u.memory_hook for u in units if u.memory_hook],
        session_stats=f"{len(units)} unit{'s' if len(units) != 1 else ''}",
    )


def _cache_path(unit: TeachingUnit, difficulty: str) -> Path:
    key = hashlib.md5(
        (unit.concept + str(unit.key_facts) + difficulty + VISUAL_PROMPT_VERSION).encode()
    ).hexdigest()
    return Path(SUMMARY_CACHE_DIR) / f"{key}.visual.json"


def _looks_like_dot(text: str) -> bool:
    stripped = text.strip()
    return stripped.startswith(("digraph", "graph", "strict"))
