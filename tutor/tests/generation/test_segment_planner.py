"""Tests for plan_segments() public API (output shape, JSON output, caching)."""

from __future__ import annotations

import json

from tutor.generation.segment_planner import plan_segments

from .conftest import (
    N_LINES,
    _fake_llm,
    _make_lines,
    _make_unit_entry,
    _units_json,
    _valid_response,
)

# ---------------------------------------------------------------------------
# Output shape
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


def test_unit_with_zero_lines_skipped_not_crashed(tmp_path):
    units = [_make_unit_entry(1, n_lines=0), _make_unit_entry(2, n_lines=N_LINES)]
    units_json = _units_json(tmp_path, units)
    lines = _make_lines()
    result = plan_segments(units_json, tmp_path / "video", _fake_llm(lines))
    assert 1 not in result
    assert 2 in result


# ---------------------------------------------------------------------------
# JSON output file
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------


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
    plan_segments(units_json, video_dir, counting_llm, no_cache=True)
    assert call_count == 1

    plan_segments(units_json, video_dir, counting_llm)
    assert call_count == 1


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
    plan_segments(units_json, video_dir, counting_llm, no_cache=True)
    assert call_count == 1

    plan_segments(units_json, video_dir, counting_llm, no_cache=True)
    assert call_count == 2


# ---------------------------------------------------------------------------
# Backward-compat: visual_planner API still callable
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# New types: step_sequence and callout
# ---------------------------------------------------------------------------


def test_step_sequence_in_valid_types():
    from tutor.models import VALID_VISUAL_TYPES

    assert "step_sequence" in VALID_VISUAL_TYPES


def test_callout_in_valid_types():
    from tutor.models import VALID_VISUAL_TYPES

    assert "callout" in VALID_VISUAL_TYPES


def test_step_sequence_fallback_on_empty_body(caplog):
    """step_sequence with empty body is reclassified to definition."""
    import logging

    from tutor.generation.segment_parser import _validate_segment
    from tutor.models import SlideSegment

    seg = SlideSegment(
        unit_index=1,
        segment_index=0,
        lines_start=0,
        lines_end=1,
        visual_type="step_sequence",
        title="Steps to deploy",
        body=None,
        code=None,
        language=None,
        mermaid=None,
        left=None,
        right=None,
        rows=None,
    )
    with caplog.at_level(logging.WARNING):
        result = _validate_segment(seg)
    assert result.visual_type == "definition"
    assert "step_sequence" in caplog.text
    assert "body is empty" in caplog.text


def test_callout_fallback_on_empty_body(caplog):
    """callout with empty body is reclassified to key_insight."""
    import logging

    from tutor.generation.segment_parser import _validate_segment
    from tutor.models import SlideSegment

    seg = SlideSegment(
        unit_index=1,
        segment_index=0,
        lines_start=0,
        lines_end=1,
        visual_type="callout",
        title="WARNING",
        body=None,
        code=None,
        language=None,
        mermaid=None,
        left=None,
        right=None,
        rows=None,
    )
    with caplog.at_level(logging.WARNING):
        result = _validate_segment(seg)
    assert result.visual_type == "key_insight"
    assert "callout" in caplog.text


def test_valid_step_sequence_passes_validation():
    """step_sequence with body is accepted without reclassification."""
    from tutor.generation.segment_parser import _validate_segment
    from tutor.models import SlideSegment

    seg = SlideSegment(
        unit_index=1,
        segment_index=0,
        lines_start=0,
        lines_end=2,
        visual_type="step_sequence",
        title="How to deploy",
        body="Open the terminal\nRun the build script\nPush to staging",
        code=None,
        language=None,
        mermaid=None,
        left=None,
        right=None,
        rows=None,
    )
    result = _validate_segment(seg)
    assert result.visual_type == "step_sequence"


def test_valid_callout_passes_validation():
    """callout with title and body is accepted without reclassification."""
    from tutor.generation.segment_parser import _validate_segment
    from tutor.models import SlideSegment

    seg = SlideSegment(
        unit_index=1,
        segment_index=0,
        lines_start=4,
        lines_end=5,
        visual_type="callout",
        title="TIP",
        body="Always run the linter before committing — it catches 80% of review feedback.",
        code=None,
        language=None,
        mermaid=None,
        left=None,
        right=None,
        rows=None,
    )
    result = _validate_segment(seg)
    assert result.visual_type == "callout"


def test_visual_planner_plan_visuals_still_callable(tmp_path):
    from dataclasses import asdict as _asdict

    from tutor.generation.visual_planner import plan_visuals
    from tutor.models import TeachingUnit

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
