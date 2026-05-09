import json
from dataclasses import asdict

from tutor.generation.visual_planner import (
    _build_outro,
    _build_title_card,
    _cache_path,
    _fallback_spec,
    _parse_visual_response,
    _plan_unit,
    plan_visuals,
)
from tutor.models import TeachingUnit, VisualSpec

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_unit(idx: int = 1, concept: str = "Pass-by-Value") -> TeachingUnit:
    return TeachingUnit(
        unit=idx,
        concept=concept,
        source_sections=["s01"],
        complexity=2,
        word_budget=400,
        key_facts=["Java passes copies", "Primitives copy values", "References copy the pointer"],
        common_misconception="Java passes objects by reference",
        good_analogy="Copying an address, not a house",
        question_style="recall",
        memory_hook="Copy the address, not the house",
    )


def _make_units(n: int = 2) -> list[TeachingUnit]:
    concepts = ["Pass-by-Value", "String Equality", "Interfaces", "Abstract Classes"]
    return [_make_unit(i + 1, concepts[i % len(concepts)]) for i in range(n)]


GOOD_LLM_RESPONSE = json.dumps(
    {
        "hook_question": "What really happens when Java passes an object?",
        "key_points": [
            "Java always passes copies",
            "Primitive copies hold the value directly",
            "Reference copies hold the memory address",
        ],
        "code_snippet": "void mutate(int x) { x = 99; }",
        "diagram_type": "flowchart",
        "diagram_spec": "digraph G { rankdir=TB\n A -> B }",
        "memory_hook": "Copy the address, not the house",
    }
)

CODE_COMPARISON_RESPONSE = json.dumps(
    {
        "hook_question": "Which equality check should you use?",
        "key_points": ["Use .equals() for content", "== checks identity"],
        "code_snippet": None,
        "diagram_type": "code_comparison",
        "diagram_spec": {
            "wrong": "if (a == b) {}",
            "right": "if (a.equals(b)) {}",
            "label_wrong": "compares references",
            "label_right": "compares content",
        },
        "memory_hook": "equals for content, == for identity",
    }
)


def fake_llm(messages, call_type="dialogue"):
    return GOOD_LLM_RESPONSE


# ---------------------------------------------------------------------------
# _parse_visual_response
# ---------------------------------------------------------------------------


def test_parse_good_response_returns_visual_spec():
    unit = _make_unit()
    spec = _parse_visual_response(GOOD_LLM_RESPONSE, unit)
    assert isinstance(spec, VisualSpec)
    assert spec.slide_type == "unit"
    assert spec.concept == unit.concept
    assert spec.diagram_type == "flowchart"
    assert spec.hook_question != ""


def test_parse_code_comparison_response():
    unit = _make_unit()
    spec = _parse_visual_response(CODE_COMPARISON_RESPONSE, unit)
    assert spec.diagram_type == "code_comparison"
    assert isinstance(spec.diagram_spec, dict)
    assert "wrong" in spec.diagram_spec
    assert "right" in spec.diagram_spec


def test_invalid_json_returns_fallback():
    unit = _make_unit()
    spec = _parse_visual_response("not json at all %%%", unit)
    assert spec.diagram_type == "none"
    assert spec.diagram_spec is None
    assert spec.concept == unit.concept


def test_invalid_diagram_type_becomes_none():
    unit = _make_unit()
    bad = json.dumps(
        {
            "hook_question": "Q?",
            "key_points": ["fact"],
            "code_snippet": None,
            "diagram_type": "pie_chart",
            "diagram_spec": None,
            "memory_hook": "remember this",
        }
    )
    spec = _parse_visual_response(bad, unit)
    assert spec.diagram_type == "none"


def test_dot_diagram_without_valid_dot_string_becomes_none():
    unit = _make_unit()
    bad = json.dumps(
        {
            "hook_question": "Q?",
            "key_points": ["fact"],
            "code_snippet": None,
            "diagram_type": "class_diagram",
            "diagram_spec": "this is not dot syntax",
            "memory_hook": "remember",
        }
    )
    spec = _parse_visual_response(bad, unit)
    assert spec.diagram_type == "none"
    assert spec.diagram_spec is None


def test_code_comparison_missing_keys_becomes_none():
    unit = _make_unit()
    bad = json.dumps(
        {
            "hook_question": "Q?",
            "key_points": ["fact"],
            "code_snippet": None,
            "diagram_type": "code_comparison",
            "diagram_spec": {"only_wrong": "x = 1"},
            "memory_hook": "remember",
        }
    )
    spec = _parse_visual_response(bad, unit)
    assert spec.diagram_type == "none"


# ---------------------------------------------------------------------------
# _fallback_spec
# ---------------------------------------------------------------------------


def test_fallback_spec_fields():
    unit = _make_unit()
    spec = _fallback_spec(unit)
    assert spec.slide_type == "unit"
    assert spec.diagram_type == "none"
    assert spec.diagram_spec is None
    assert spec.unit_index == unit.unit
    assert len(spec.key_points) <= 5


# ---------------------------------------------------------------------------
# _build_title_card / _build_outro
# ---------------------------------------------------------------------------


def test_title_card_slide_type():
    units = _make_units(3)
    card = _build_title_card("Java Basics", units, "week1_1")
    assert card.slide_type == "title_card"
    assert card.unit_index == 0
    assert "3 units" in card.subtitle
    assert card.title == "Java Basics"


def test_outro_collects_memory_hooks():
    units = _make_units(2)
    outro = _build_outro(units)
    assert outro.slide_type == "outro"
    assert outro.unit_index == len(units) + 1
    assert len(outro.memory_hooks) == len(units)
    assert units[0].memory_hook in outro.memory_hooks


# ---------------------------------------------------------------------------
# _plan_unit — caching
# ---------------------------------------------------------------------------


def test_cache_hit_skips_llm(tmp_path):
    unit = _make_unit()
    cache_file = tmp_path / "test.visual.json"
    spec = _fallback_spec(unit)
    cache_file.write_text(json.dumps(asdict(spec)), encoding="utf-8")

    call_count = {"n": 0}

    def counting_llm(messages, call_type="dialogue"):
        call_count["n"] += 1
        return GOOD_LLM_RESPONSE

    result = _plan_unit(unit, counting_llm, "beginner", cache_file)
    assert call_count["n"] == 0
    assert result.concept == unit.concept


def test_cache_miss_calls_llm(tmp_path):
    unit = _make_unit()
    cache_file = tmp_path / "missing.visual.json"

    call_count = {"n": 0}

    def counting_llm(messages, call_type="dialogue"):
        call_count["n"] += 1
        return GOOD_LLM_RESPONSE

    _plan_unit(unit, counting_llm, "beginner", cache_file)
    assert call_count["n"] == 1
    assert cache_file.exists()


def test_llm_failure_produces_fallback_not_crash(tmp_path):
    unit = _make_unit()
    cache_file = tmp_path / "x.visual.json"

    def bad_llm(messages, call_type="dialogue"):
        raise RuntimeError("API exploded")

    spec = _plan_unit(unit, bad_llm, "beginner", cache_file)
    assert spec.diagram_type == "none"
    assert spec.concept == unit.concept


# ---------------------------------------------------------------------------
# plan_visuals — integration
# ---------------------------------------------------------------------------


def test_plan_visuals_returns_title_and_outro(tmp_path):
    units = _make_units(2)
    units_json = tmp_path / "tutorial.units.json"
    units_json.write_text(
        json.dumps([asdict(u) for u in units], ensure_ascii=False),
        encoding="utf-8",
    )
    video_dir = tmp_path / "video"

    specs = plan_visuals(units_json, "Java Basics", "week1_1", fake_llm, "beginner", video_dir)

    assert specs[0].slide_type == "title_card"
    assert specs[-1].slide_type == "outro"
    assert len(specs) == len(units) + 2


def test_plan_visuals_writes_json_to_video_dir(tmp_path):
    units = _make_units(1)
    units_json = tmp_path / "tutorial.units.json"
    units_json.write_text(json.dumps([asdict(u) for u in units]), encoding="utf-8")
    video_dir = tmp_path / "video"

    plan_visuals(units_json, "Java Basics", "week1_1", fake_llm, "beginner", video_dir)

    out = video_dir / "tutorial.visuals.json"
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert data[0]["slide_type"] == "title_card"


def test_plan_visuals_no_cache_clears_cache(tmp_path):
    unit = _make_unit()
    cache_file = _cache_path(unit, "beginner")
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(asdict(_fallback_spec(unit))), encoding="utf-8")

    units_json = tmp_path / "tutorial.units.json"
    units_json.write_text(json.dumps([asdict(unit)]), encoding="utf-8")
    video_dir = tmp_path / "video"

    call_count = {"n": 0}

    def counting_llm(messages, call_type="dialogue"):
        call_count["n"] += 1
        return GOOD_LLM_RESPONSE

    plan_visuals(units_json, "T", "s", counting_llm, "beginner", video_dir, no_cache=True)
    assert call_count["n"] == 1


def test_unit_specs_have_required_fields(tmp_path):
    units = _make_units(2)
    units_json = tmp_path / "tutorial.units.json"
    units_json.write_text(json.dumps([asdict(u) for u in units]), encoding="utf-8")
    video_dir = tmp_path / "video"

    specs = plan_visuals(units_json, "T", "s", fake_llm, "beginner", video_dir)
    unit_specs = [s for s in specs if s.slide_type == "unit"]

    for spec in unit_specs:
        assert spec.concept
        assert isinstance(spec.key_points, list)
        assert spec.diagram_type in {
            "class_diagram",
            "flowchart",
            "code_comparison",
            "concept_map",
            "none",
        }
        assert spec.memory_hook is not None
