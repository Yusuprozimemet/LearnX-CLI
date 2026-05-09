from pathlib import Path

import pytest

from tutor.models import DialogueLine, VisualSpec
from tutor.visual.beat_timer import (
    MIN_SLIDE_DURATION,
    OUTRO_CARD_DURATION,
    TITLE_CARD_DURATION,
    compute_slide_timings,
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

