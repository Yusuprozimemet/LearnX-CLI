from pathlib import Path

import pytest

from tutor.models import DialogueLine, SlideSegment, VisualSpec
from tutor.visual.beat_timer import (
    MIN_SLIDE_DURATION,
    OUTRO_CARD_DURATION,
    TITLE_CARD_DURATION,
    _compute_slide_timings_v2,
    compute_slide_timings,
    compute_slide_timings_v3,
)


def _line(speaker: str, unit: int) -> DialogueLine:
    return DialogueLine(speaker=speaker, text="Some text here", unit_number=unit)


def _unit_spec(idx: int) -> VisualSpec:
    return VisualSpec(
        unit_index=idx,
        slide_type="unit",
        concept=f"Concept {idx}",
        memory_hook="remember this",
    )


def _slides(n_units: int) -> list[Path]:
    paths = [Path("slides/00_title.png")]
    for i in range(1, n_units + 1):
        paths += [
            Path(f"slides/{i:02d}_hook.png"),
            Path(f"slides/{i:02d}_concept.png"),
            Path(f"slides/{i:02d}_memory.png"),
        ]
    paths.append(Path("slides/99_outro.png"))
    return paths


def test_title_card_fixed_4_seconds():
    script = [_line("ALEX", 1), _line("MAYA", 1)]
    offsets = [0.0, 5.0]
    visuals = [
        VisualSpec(unit_index=0, slide_type="title_card"),
        _unit_spec(1),
        VisualSpec(unit_index=2, slide_type="outro"),
    ]
    slides = _slides(1)
    timings = compute_slide_timings(slides, script, offsets, visuals, [30.0])

    title_timing = next((d for p, d in timings if "_title" in p.stem), None)
    assert title_timing == TITLE_CARD_DURATION


def test_outro_card_fixed_6_seconds():
    script = [_line("ALEX", 1), _line("MAYA", 1)]
    offsets = [0.0, 5.0]
    visuals = [
        VisualSpec(unit_index=0, slide_type="title_card"),
        _unit_spec(1),
        VisualSpec(unit_index=2, slide_type="outro"),
    ]
    slides = _slides(1)
    timings = compute_slide_timings(slides, script, offsets, visuals, [30.0])

    outro_timing = next((d for p, d in timings if "_outro" in p.stem), None)
    assert outro_timing == OUTRO_CARD_DURATION


def test_hook_slide_assigned_to_first_alex_line():
    script = [_line("ALEX", 1), _line("MAYA", 1), _line("ALEX", 1)]
    offsets = [2.0, 10.0, 20.0]
    visuals = [
        VisualSpec(unit_index=0, slide_type="title_card"),
        _unit_spec(1),
        VisualSpec(unit_index=2, slide_type="outro"),
    ]
    slides = _slides(1)
    timings = compute_slide_timings(slides, script, offsets, visuals, [30.0])

    hook_dur = next((d for p, d in timings if "_hook" in p.stem), None)
    # Hook starts at 2.0 (first ALEX), concept at 10.0 → duration = 8.0
    assert hook_dur == pytest.approx(8.0, abs=0.01)


def test_concept_slide_assigned_to_first_maya_line():
    script = [_line("ALEX", 1), _line("MAYA", 1), _line("ALEX", 1)]
    offsets = [2.0, 10.0, 20.0]
    visuals = [
        VisualSpec(unit_index=0, slide_type="title_card"),
        _unit_spec(1),
        VisualSpec(unit_index=2, slide_type="outro"),
    ]
    slides = _slides(1)
    timings = compute_slide_timings(slides, script, offsets, visuals, [30.0])

    # concept starts at 10.0, memory starts at 20.0 (last ALEX) → dur = 10.0
    concept_dur = next((d for p, d in timings if "_concept" in p.stem), None)
    assert concept_dur == pytest.approx(10.0, abs=0.01)


def test_minimum_slide_duration_enforced():
    # All lines packed into 1 second — every slide should be clamped to MIN
    script = [_line("ALEX", 1), _line("MAYA", 1), _line("ALEX", 1)]
    offsets = [0.0, 0.1, 0.2]
    visuals = [
        VisualSpec(unit_index=0, slide_type="title_card"),
        _unit_spec(1),
        VisualSpec(unit_index=2, slide_type="outro"),
    ]
    slides = _slides(1)
    timings = compute_slide_timings(slides, script, offsets, visuals, [0.3])

    for path, dur in timings:
        if "_title" in path.stem or "_outro" in path.stem:
            continue
        assert dur >= MIN_SLIDE_DURATION


# ── v3 beat timer tests ───────────────────────────────────────────────────────


def _make_seg(
    unit_index: int = 1,
    segment_index: int = 0,
    lines_start: int = 0,
    lines_end: int = 1,
    visual_type: str = "key_insight",
    png_path: str = "slides/01_00_key_insight.png",
) -> SlideSegment:
    return SlideSegment(
        unit_index=unit_index,
        segment_index=segment_index,
        lines_start=lines_start,
        lines_end=lines_end,
        visual_type=visual_type,
        title="Test",
        body=None,
        code=None,
        language=None,
        mermaid=None,
        left=None,
        right=None,
        rows=None,
        png_path=png_path,
    )


def _timing_json(unit_timings: dict) -> dict:
    return {"version": 1, "units": unit_timings}


def test_exact_duration_from_timing_json() -> None:
    seg = _make_seg(lines_start=0, lines_end=0)
    unit_timing = [{"line_index": 0, "start_ms": 0, "end_ms": 3240}]
    tj = _timing_json({"1": unit_timing})
    timings = compute_slide_timings_v3(
        Path("slides/00_title.png"),
        Path("slides/99_outro.png"),
        {1: [seg]},
        tj,
        [30.0],
    )
    # title, seg, outro
    # raw = 3240ms, +1 line * SILENCE_TURN_MS(500ms) = 3740ms = 3.74 s
    seg_dur = timings[1][1]
    assert seg_dur == pytest.approx(3.74, abs=0.01)


def test_exact_duration_uses_lines_start_and_end() -> None:
    seg = _make_seg(lines_start=2, lines_end=4)
    unit_timing = [
        {"line_index": 0, "start_ms": 0, "end_ms": 1000},
        {"line_index": 1, "start_ms": 1000, "end_ms": 2000},
        {"line_index": 2, "start_ms": 2000, "end_ms": 3000},
        {"line_index": 3, "start_ms": 3000, "end_ms": 4000},
        {"line_index": 4, "start_ms": 4000, "end_ms": 9000},
    ]
    tj = _timing_json({"1": unit_timing})
    timings = compute_slide_timings_v3(
        Path("slides/00_title.png"),
        Path("slides/99_outro.png"),
        {1: [seg]},
        tj,
        [30.0],
    )
    # raw = 9000-2000 = 7000ms, +3 lines * SILENCE_TURN_MS(500ms) = 8500ms = 8.5 s
    assert timings[1][1] == pytest.approx(8.5, abs=0.01)


def test_proportional_fallback_when_timing_absent() -> None:
    seg = _make_seg(lines_start=0, lines_end=4)
    timings = compute_slide_timings_v3(
        Path("slides/00_title.png"),
        Path("slides/99_outro.png"),
        {1: [seg]},
        None,
        [30.0],
    )
    # proportional: 5/5 lines of 30 s = 30.0 s
    assert timings[1][1] == pytest.approx(30.0, abs=0.01)


def test_min_slide_duration_enforced() -> None:
    # Very short segment (0.5 s) should be clamped to MIN_SLIDE_DURATION
    seg = _make_seg(lines_start=0, lines_end=0)
    unit_timing = [{"line_index": 0, "start_ms": 0, "end_ms": 500}]
    tj = _timing_json({"1": unit_timing})
    timings = compute_slide_timings_v3(
        Path("slides/00_title.png"),
        Path("slides/99_outro.png"),
        {1: [seg]},
        tj,
        [30.0],
    )
    assert timings[1][1] >= MIN_SLIDE_DURATION


def test_title_duration_is_4_seconds() -> None:
    title_path = Path("slides/00_title.png")
    seg = _make_seg()
    timings = compute_slide_timings_v3(
        title_path, Path("slides/99_outro.png"), {1: [seg]}, None, [30.0]
    )
    assert timings[0] == (title_path, TITLE_CARD_DURATION)


def test_outro_duration_is_6_seconds() -> None:
    outro_path = Path("slides/99_outro.png")
    seg = _make_seg()
    timings = compute_slide_timings_v3(
        Path("slides/00_title.png"), outro_path, {1: [seg]}, None, [30.0]
    )
    assert timings[-1] == (outro_path, OUTRO_CARD_DURATION)


def test_all_segments_present_in_output() -> None:
    segs_u1 = [_make_seg(unit_index=1, segment_index=i) for i in range(3)]
    segs_u2 = [_make_seg(unit_index=2, segment_index=i) for i in range(2)]
    timings = compute_slide_timings_v3(
        Path("slides/00_title.png"),
        Path("slides/99_outro.png"),
        {1: segs_u1, 2: segs_u2},
        None,
        [30.0, 30.0],
    )
    # title + 3 + 2 + outro = 7
    assert len(timings) == 7


def test_timing_gap_accounted_in_exact_duration() -> None:
    from tutor.constants import SILENCE_TURN_MS
    from tutor.visual.beat_timer import _exact_duration

    seg = _make_seg(lines_start=0, lines_end=2)  # 3 lines
    unit_timing = [
        {"line_index": 0, "start_ms": 0, "end_ms": 1000},
        {"line_index": 1, "start_ms": 1500, "end_ms": 2500},
        {"line_index": 2, "start_ms": 3000, "end_ms": 4000},
    ]
    raw_ms = 4000 - 0  # end_ms of last - start_ms of first
    expected_s = (raw_ms + 3 * SILENCE_TURN_MS) / 1000.0
    assert _exact_duration(seg, unit_timing) == pytest.approx(expected_s, abs=0.01)


def test_single_line_segment_includes_one_gap() -> None:
    from tutor.constants import SILENCE_TURN_MS
    from tutor.visual.beat_timer import MIN_SLIDE_DURATION, _exact_duration

    seg = _make_seg(lines_start=1, lines_end=1)  # 1 line
    unit_timing = [
        {"line_index": 0, "start_ms": 0, "end_ms": 800},
        {"line_index": 1, "start_ms": 1300, "end_ms": 5500},  # long enough to exceed MIN
    ]
    raw_ms = 5500 - 1300
    expected_s = max((raw_ms + 1 * SILENCE_TURN_MS) / 1000.0, MIN_SLIDE_DURATION)
    assert _exact_duration(seg, unit_timing) == pytest.approx(expected_s, abs=0.01)


def test_v2_function_still_callable() -> None:
    script = [_line("ALEX", 1), _line("MAYA", 1)]
    offsets = [0.0, 5.0]
    visuals = [
        VisualSpec(unit_index=0, slide_type="title_card"),
        _unit_spec(1),
        VisualSpec(unit_index=2, slide_type="outro"),
    ]
    slides = _slides(1)
    result = _compute_slide_timings_v2(slides, script, offsets, visuals, [30.0])
    assert isinstance(result, list)
