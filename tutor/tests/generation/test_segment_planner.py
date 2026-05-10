from __future__ import annotations

import json
from pathlib import Path

from tutor.generation.segment_planner import plan_segments
from tutor.models import DialogueLine, TeachingUnit

# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

N_LINES = 6


def _line(i: int, speaker: str = "ALEX", unit: int = 1) -> DialogueLine:
    return DialogueLine(speaker=speaker, text=f"Line {i}", unit_number=unit)


def _make_lines(n: int = N_LINES, unit: int = 1) -> list[DialogueLine]:
    speakers = ["ALEX", "MAYA", "ALEX", "MAYA", "ALEX", "ALEX"]
    return [_line(i, speakers[i % len(speakers)], unit) for i in range(n)]


def _make_unit_entry(
    unit_num: int = 1, concept: str = "Test Concept", n_lines: int = N_LINES
) -> dict:
    lines = [
        {"speaker": "ALEX" if i % 2 == 0 else "MAYA", "text": f"Line {i}", "unit_number": unit_num}
        for i in range(n_lines)
    ]
    return {
        "unit": unit_num,
        "concept": concept,
        "lines": lines,
        "source_sections": [],
        "complexity": 1,
        "word_budget": 200,
        "key_facts": [],
        "common_misconception": "",
        "good_analogy": "",
        "question_style": "",
        "memory_hook": "",
    }


def _units_json(tmp_path: Path, units: list[dict]) -> Path:
    p = tmp_path / "tutorial.units.json"
    p.write_text(json.dumps(units), encoding="utf-8")
    return p


def _valid_response(lines: list[DialogueLine]) -> str:
    n = len(lines)
    mid_end = max(1, n - 2)
    return json.dumps(
        [
            {
                "lines_start": 0,
                "lines_end": 0,
                "visual_type": "hook_question",
                "title": "Opening",
                "body": None,
                "code": None,
                "language": None,
                "mermaid": None,
                "left": None,
                "right": None,
                "rows": None,
            },
            {
                "lines_start": 1,
                "lines_end": mid_end,
                "visual_type": "key_insight",
                "title": "Key Point",
                "body": None,
                "code": None,
                "language": None,
                "mermaid": None,
                "left": None,
                "right": None,
                "rows": None,
            },
            {
                "lines_start": mid_end + 1,
                "lines_end": n - 1,
                "visual_type": "memory_hook",
                "title": "Remember",
                "body": None,
                "code": None,
                "language": None,
                "mermaid": None,
                "left": None,
                "right": None,
                "rows": None,
            },
        ]
    )


def _fake_llm(lines: list[DialogueLine]):
    def _llm(messages, call_type="segments"):
        return _valid_response(lines)

    return _llm


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_plan_segments_returns_dict_keyed_by_unit(tmp_path):
    units = [_make_unit_entry(1), _make_unit_entry(2)]
    units_json = _units_json(tmp_path, units)
    lines = _make_lines()
    result = plan_segments(units_json, tmp_path / "video", _fake_llm(lines))
    assert isinstance(result, dict)
    assert 1 in result
    assert 2 in result
    assert all(isinstance(k, int) for k in result)


def test_all_lines_covered(tmp_path):
    n = N_LINES
    units = [_make_unit_entry(1, n_lines=n)]
    units_json = _units_json(tmp_path, units)
    lines = _make_lines(n)
    result = plan_segments(units_json, tmp_path / "video", _fake_llm(lines))
    segs = result[1]
    covered = set()
    for seg in segs:
        covered.update(range(seg.lines_start, seg.lines_end + 1))
    assert covered == set(range(n))


def test_no_line_covered_twice(tmp_path):
    n = N_LINES
    units = [_make_unit_entry(1, n_lines=n)]
    units_json = _units_json(tmp_path, units)
    lines = _make_lines(n)
    result = plan_segments(units_json, tmp_path / "video", _fake_llm(lines))
    segs = result[1]
    covered = []
    for seg in segs:
        covered.extend(range(seg.lines_start, seg.lines_end + 1))
    assert len(covered) == len(set(covered)), "Some lines covered twice"


def test_first_segment_is_hook_question(tmp_path):
    units = [_make_unit_entry(1)]
    units_json = _units_json(tmp_path, units)
    lines = _make_lines()
    result = plan_segments(units_json, tmp_path / "video", _fake_llm(lines))
    assert result[1][0].visual_type == "hook_question"


def test_last_segment_is_memory_hook(tmp_path):
    units = [_make_unit_entry(1)]
    units_json = _units_json(tmp_path, units)
    lines = _make_lines()
    result = plan_segments(units_json, tmp_path / "video", _fake_llm(lines))
    assert result[1][-1].visual_type == "memory_hook"


def test_segment_index_is_sequential(tmp_path):
    units = [_make_unit_entry(1)]
    units_json = _units_json(tmp_path, units)
    lines = _make_lines()
    result = plan_segments(units_json, tmp_path / "video", _fake_llm(lines))
    indices = [s.segment_index for s in result[1]]
    assert indices == list(range(len(indices)))


def test_invalid_json_from_llm_returns_fallback(tmp_path):
    units = [_make_unit_entry(1)]
    units_json = _units_json(tmp_path, units)

    def bad_llm(messages, call_type="segments"):
        return "this is not JSON at all !!!"

    result = plan_segments(units_json, tmp_path / "video", bad_llm)
    segs = result[1]
    assert len(segs) >= 1
    assert segs[0].visual_type == "hook_question"
    assert segs[-1].visual_type == "memory_hook"


def test_unknown_visual_type_replaced_with_key_insight(tmp_path):
    def banana_llm(messages, call_type="segments"):
        return json.dumps(
            [
                {
                    "lines_start": 0,
                    "lines_end": 0,
                    "visual_type": "hook_question",
                    "title": "Open",
                    "body": None,
                    "code": None,
                    "language": None,
                    "mermaid": None,
                    "left": None,
                    "right": None,
                    "rows": None,
                },
                {
                    "lines_start": 1,
                    "lines_end": 2,
                    "visual_type": "banana",
                    "title": "Unknown",
                    "body": None,
                    "code": None,
                    "language": None,
                    "mermaid": None,
                    "left": None,
                    "right": None,
                    "rows": None,
                },
                {
                    "lines_start": 3,
                    "lines_end": 3,
                    "visual_type": "memory_hook",
                    "title": "Remember",
                    "body": None,
                    "code": None,
                    "language": None,
                    "mermaid": None,
                    "left": None,
                    "right": None,
                    "rows": None,
                },
            ]
        )

    units = [_make_unit_entry(1, n_lines=4)]
    units_json = _units_json(tmp_path, units)
    result = plan_segments(units_json, tmp_path / "video", banana_llm)
    types = [s.visual_type for s in result[1]]
    assert "banana" not in types
    assert "key_insight" in types


def test_out_of_bounds_indices_clamped(tmp_path):
    n = 5

    def oob_llm(messages, call_type="segments"):
        return json.dumps(
            [
                {
                    "lines_start": 0,
                    "lines_end": 0,
                    "visual_type": "hook_question",
                    "title": "Open",
                    "body": None,
                    "code": None,
                    "language": None,
                    "mermaid": None,
                    "left": None,
                    "right": None,
                    "rows": None,
                },
                {
                    "lines_start": 1,
                    "lines_end": 999,
                    "visual_type": "key_insight",
                    "title": "Key",
                    "body": None,
                    "code": None,
                    "language": None,
                    "mermaid": None,
                    "left": None,
                    "right": None,
                    "rows": None,
                },
            ]
        )

    units = [_make_unit_entry(1, n_lines=n)]
    units_json = _units_json(tmp_path, units)
    result = plan_segments(units_json, tmp_path / "video", oob_llm)
    for seg in result[1]:
        assert seg.lines_end <= n - 1
        assert seg.lines_start >= 0


def test_gap_filled_with_key_insight(tmp_path):
    n = 8

    def gap_llm(messages, call_type="segments"):
        # Returns only lines 0-2; lines 3-7 are a gap
        return json.dumps(
            [
                {
                    "lines_start": 0,
                    "lines_end": 0,
                    "visual_type": "hook_question",
                    "title": "Open",
                    "body": None,
                    "code": None,
                    "language": None,
                    "mermaid": None,
                    "left": None,
                    "right": None,
                    "rows": None,
                },
                {
                    "lines_start": 1,
                    "lines_end": 2,
                    "visual_type": "key_insight",
                    "title": "Key",
                    "body": None,
                    "code": None,
                    "language": None,
                    "mermaid": None,
                    "left": None,
                    "right": None,
                    "rows": None,
                },
            ]
        )

    units = [_make_unit_entry(1, n_lines=n)]
    units_json = _units_json(tmp_path, units)
    result = plan_segments(units_json, tmp_path / "video", gap_llm)
    segs = result[1]
    # All lines must be covered
    covered = set()
    for seg in segs:
        covered.update(range(seg.lines_start, seg.lines_end + 1))
    assert covered == set(range(n))
    # The gap fill should have used key_insight
    gap_segs = [s for s in segs if s.lines_start >= 3]
    assert any(s.visual_type == "key_insight" for s in gap_segs)


def test_cache_hit_skips_llm_call(tmp_path):
    units = [_make_unit_entry(1)]
    units_json = _units_json(tmp_path, units)
    lines = _make_lines()
    call_count = 0

    def counting_llm(messages, call_type="segments"):
        nonlocal call_count
        call_count += 1
        return _valid_response(lines)

    video_dir = tmp_path / "video"
    # no_cache=True guarantees LLM is called even if stale cache exists
    plan_segments(units_json, video_dir, counting_llm, no_cache=True)
    assert call_count == 1

    # Second call without no_cache — hits the freshly-written cache
    plan_segments(units_json, video_dir, counting_llm)
    assert call_count == 1  # cache hit — LLM not called again


def test_no_cache_forces_regeneration(tmp_path):
    units = [_make_unit_entry(1)]
    units_json = _units_json(tmp_path, units)
    lines = _make_lines()
    call_count = 0

    def counting_llm(messages, call_type="segments"):
        nonlocal call_count
        call_count += 1
        return _valid_response(lines)

    video_dir = tmp_path / "video"
    # Prime the cache
    plan_segments(units_json, video_dir, counting_llm, no_cache=True)
    assert call_count == 1

    # no_cache=True deletes cache and forces another LLM call
    plan_segments(units_json, video_dir, counting_llm, no_cache=True)
    assert call_count == 2


def test_segments_json_written_to_video_dir(tmp_path):
    units = [_make_unit_entry(1)]
    units_json = _units_json(tmp_path, units)
    lines = _make_lines()
    video_dir = tmp_path / "video"
    plan_segments(units_json, video_dir, _fake_llm(lines))
    assert (video_dir / "tutorial.segments.json").exists()


def test_segments_json_has_version_1(tmp_path):
    units = [_make_unit_entry(1)]
    units_json = _units_json(tmp_path, units)
    lines = _make_lines()
    video_dir = tmp_path / "video"
    plan_segments(units_json, video_dir, _fake_llm(lines))
    data = json.loads((video_dir / "tutorial.segments.json").read_text())
    assert data["version"] == 1


def test_unit_with_zero_lines_skipped_not_crashed(tmp_path):
    units = [_make_unit_entry(1, n_lines=0), _make_unit_entry(2, n_lines=N_LINES)]
    units_json = _units_json(tmp_path, units)
    lines = _make_lines()
    result = plan_segments(units_json, tmp_path / "video", _fake_llm(lines))
    assert 1 not in result  # unit with 0 lines skipped
    assert 2 in result


def test_mermaid_null_for_non_diagram_types(tmp_path):
    def mermaid_llm(messages, call_type="segments"):
        return json.dumps(
            [
                {
                    "lines_start": 0,
                    "lines_end": 0,
                    "visual_type": "hook_question",
                    "title": "Open",
                    "body": None,
                    "code": None,
                    "language": None,
                    "mermaid": "classDiagram\n  A --> B",  # should be nulled
                    "left": None,
                    "right": None,
                    "rows": None,
                },
                {
                    "lines_start": 1,
                    "lines_end": 2,
                    "visual_type": "key_insight",
                    "title": "Key",
                    "body": None,
                    "code": None,
                    "language": None,
                    "mermaid": "classDiagram\n  A --> B",  # should be nulled
                    "left": None,
                    "right": None,
                    "rows": None,
                },
                {
                    "lines_start": 3,
                    "lines_end": 3,
                    "visual_type": "memory_hook",
                    "title": "Rem",
                    "body": None,
                    "code": None,
                    "language": None,
                    "mermaid": None,
                    "left": None,
                    "right": None,
                    "rows": None,
                },
            ]
        )

    units = [_make_unit_entry(1, n_lines=4)]
    units_json = _units_json(tmp_path, units)
    result = plan_segments(units_json, tmp_path / "video", mermaid_llm)
    for seg in result[1]:
        if seg.visual_type != "diagram":
            assert seg.mermaid is None


def test_visual_planner_plan_visuals_still_callable(tmp_path):
    from dataclasses import asdict as _asdict

    from tutor.generation.visual_planner import plan_visuals

    unit = TeachingUnit(
        unit=1,
        concept="Test Concept",
        source_sections=["s01"],
        complexity=1,
        word_budget=200,
        key_facts=["fact1"],
        common_misconception="none",
        good_analogy="like a box",
        question_style="recall",
        memory_hook="remember the box",
    )
    units_json = tmp_path / "tutorial.units.json"
    units_json.write_text(json.dumps([_asdict(unit)]), encoding="utf-8")

    def stub_llm(messages, call_type="visual"):
        return json.dumps(
            {
                "hook_question": "What is it?",
                "key_points": ["Point one"],
                "code_snippet": None,
                "diagram_type": "none",
                "diagram_spec": None,
                "memory_hook": "remember",
                "analogy": "",
            }
        )

    video_dir = tmp_path / "video"
    specs = plan_visuals(units_json, "Test", "test_session", stub_llm, "beginner", video_dir)
    assert len(specs) >= 1
