import re

from tutor.models import DialogueLine
from tutor.visual.subtitle_writer import (
    _format_timestamp,
    _line_duration,
    _wrap_subtitle,
    build_srt,
    get_line_start_offsets,
)


def _line(speaker: str, text: str, unit: int = 1) -> DialogueLine:
    return DialogueLine(speaker=speaker, text=text, unit_number=unit)


# ── SRT format ───────────────────────────────────────────────────────────────


def test_srt_numbering_sequential():
    lines = [
        _line("ALEX", "Hello world", 1),
        _line("MAYA", "Great point", 1),
        _line("ALEX", "Indeed", 1),
    ]
    srt = build_srt(lines, [30.0])
    numbers = re.findall(r"^(\d+)$", srt, re.MULTILINE)
    assert numbers == ["1", "2", "3"]


def test_timestamp_format_correct():
    result = _format_timestamp(83.456)
    assert result == "00:01:23,456"


def test_timestamp_zero():
    assert _format_timestamp(0.0) == "00:00:00,000"


def test_timestamp_hours():
    assert _format_timestamp(3661.5) == "01:01:01,500"


# ── Subtitle wrapping ─────────────────────────────────────────────────────────


def test_line_wrap_at_60_chars():
    short = _wrap_subtitle("ALEX", "Short text.")
    assert len(short) <= 60
    assert "\n" not in short


def test_line_wrap_long_text_splits():
    long_text = (
        "This is an extremely long piece of dialogue that definitely exceeds sixty characters"
    )
    result = _wrap_subtitle("MAYA", long_text)
    for segment in result.split("\n"):
        assert len(segment) <= 60


def test_wrap_preserves_speaker():
    result = _wrap_subtitle("SAM", "Hello world")
    assert result.startswith("SAM: ")


# ── Unit duration scaling ─────────────────────────────────────────────────────


def test_unit_scaling_when_duration_mismatch():
    lines = [
        _line("ALEX", "One two three four five six seven eight nine ten", 1),
        _line("MAYA", "One two three four five six seven eight nine ten", 1),
    ]
    estimated = sum(_line_duration(ln.text) for ln in lines)
    # Supply actual = 150% of estimated — should scale up
    actual_s = estimated * 1.5
    _srt = build_srt(lines, [actual_s])
    offsets = get_line_start_offsets(lines, [actual_s])
    # The second line's start should be later than without scaling
    offsets_noscale = get_line_start_offsets(lines, [estimated])
    assert offsets[1] > offsets_noscale[1]


def test_no_scaling_within_10_percent():
    lines = [_line("ALEX", "Short line", 1)]
    estimated = _line_duration(lines[0].text)
    actual = estimated * 1.08  # 8% difference, below threshold
    offsets_scaled = get_line_start_offsets(lines, [actual])
    offsets_exact = get_line_start_offsets(lines, [estimated])
    assert offsets_scaled[0] == offsets_exact[0]


# ── Offset consistency ────────────────────────────────────────────────────────


def test_get_line_start_offsets_matches_srt_timestamps():
    lines = [
        _line("ALEX", "First line here now", 1),
        _line("MAYA", "Second line here now", 1),
    ]
    unit_dur = [30.0]
    offsets = get_line_start_offsets(lines, unit_dur)
    srt = build_srt(lines, unit_dur)

    # Extract first timestamp from SRT
    match = re.search(r"(\d{2}:\d{2}:\d{2},\d{3}) -->", srt)
    assert match
    ts_str = match.group(1)
    # First line always starts at 0.0
    assert offsets[0] == 0.0
    assert ts_str == "00:00:00,000"
