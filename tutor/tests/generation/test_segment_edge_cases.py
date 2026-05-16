"""Tests for edge cases: fallback, gap filling, invalid LLM responses, field validation."""

from __future__ import annotations

import json

from tutor.generation.segment_planner import plan_segments

from .conftest import (
    _make_unit_entry,
    _units_json,
)

# ---------------------------------------------------------------------------
# Fallback on bad LLM response
# ---------------------------------------------------------------------------


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


def test_llm_exception_returns_fallback(tmp_path):
    units = [_make_unit_entry(1)]
    units_json = _units_json(tmp_path, units)

    def exploding_llm(messages, call_type="segments"):
        raise RuntimeError("network failure")

    result = plan_segments(units_json, tmp_path / "video", exploding_llm)
    segs = result[1]
    assert len(segs) >= 1
    assert segs[0].visual_type == "hook_question"


# ---------------------------------------------------------------------------
# Field validation
# ---------------------------------------------------------------------------


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
                    "mermaid": "classDiagram\n  A --> B",
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
                    "mermaid": "classDiagram\n  A --> B",
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


# ---------------------------------------------------------------------------
# Gap filling
# ---------------------------------------------------------------------------


def test_gap_filled_with_key_insight(tmp_path):
    n = 8

    def gap_llm(messages, call_type="segments"):
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
    covered = set()
    for seg in segs:
        covered.update(range(seg.lines_start, seg.lines_end + 1))
    assert covered == set(range(n))
    gap_segs = [s for s in segs if s.lines_start >= 3]
    assert any(s.visual_type == "key_insight" for s in gap_segs)


def test_single_line_unit_fallback_has_two_segments(tmp_path):
    units = [_make_unit_entry(1, n_lines=1)]
    units_json = _units_json(tmp_path, units)

    def bad_llm(messages, call_type="segments"):
        return "not json"

    result = plan_segments(units_json, tmp_path / "video", bad_llm)
    segs = result[1]
    assert len(segs) == 2
    assert segs[0].visual_type == "hook_question"
    assert segs[1].visual_type == "memory_hook"


def test_two_line_unit_fallback_covers_both(tmp_path):
    units = [_make_unit_entry(1, n_lines=2)]
    units_json = _units_json(tmp_path, units)

    def bad_llm(messages, call_type="segments"):
        return "not json"

    result = plan_segments(units_json, tmp_path / "video", bad_llm)
    segs = result[1]
    covered = set()
    for seg in segs:
        covered.update(range(seg.lines_start, seg.lines_end + 1))
    assert covered == {0, 1}
