"""
Map slide PNGs to playback durations based on dialogue beat points.
No ffmpeg, no Pillow, no LLM here.
"""

from pathlib import Path

from tutor.models import DialogueLine, SlideSegment, VisualSpec

MIN_SLIDE_DURATION = 3.0  # seconds
MAX_HOOK_DURATION = 30.0  # cap hook slide — ALEX can monologue for a long time before MAYA
TITLE_CARD_DURATION = 4.0
OUTRO_CARD_DURATION = 6.0


def compute_slide_timings_v3(
    title_path: Path,
    outro_path: Path,
    segments_by_unit: dict[int, list[SlideSegment]],
    timing_json: dict | None,
    unit_durations_s: list[float],
) -> list[tuple[Path, float]]:
    """
    Return [(png_path, duration_seconds), ...] in video order, ready for the
    ffmpeg concat script. Prepends title card (4.0 s) and appends outro (6.0 s).

    Duration source per segment:
      timing_json present  → _exact_duration()
      timing_json absent   → _proportional_duration()

    Minimum per-segment: MIN_SLIDE_DURATION (3.0 s).
    """
    result: list[tuple[Path, float]] = [(title_path, TITLE_CARD_DURATION)]

    units_timing = timing_json.get("units", {}) if timing_json else {}

    for unit_num in sorted(segments_by_unit.keys()):
        segs = segments_by_unit[unit_num]
        unit_dur = unit_durations_s[unit_num - 1] if unit_num - 1 < len(unit_durations_s) else 30.0
        total_lines = max(s.lines_end for s in segs) + 1 if segs else 1
        unit_timing: list[dict] = units_timing.get(str(unit_num), [])

        for seg in segs:
            path = Path(seg.png_path)
            if timing_json and unit_timing:
                dur = _exact_duration(seg, unit_timing)
            else:
                dur = _proportional_duration(seg, unit_dur, total_lines)
            result.append((path, dur))

    result.append((outro_path, OUTRO_CARD_DURATION))
    return result


def _exact_duration(seg: SlideSegment, unit_timing: list[dict]) -> float:
    """
    Look up timing entries for lines_start and lines_end in unit_timing.
    Falls back to proportional if either index is out of range.
    """
    try:
        start_ms = unit_timing[seg.lines_start]["start_ms"]
        end_ms = unit_timing[seg.lines_end]["end_ms"]
        return max((end_ms - start_ms) / 1000.0, MIN_SLIDE_DURATION)
    except (IndexError, KeyError, TypeError):
        total_lines = len(unit_timing) if unit_timing else 1
        return _proportional_duration(seg, 30.0, total_lines)


def _proportional_duration(seg: SlideSegment, unit_duration_s: float, total_lines: int) -> float:
    """
    Segment covers (lines_end - lines_start + 1) / total_lines of unit duration.
    Return max(computed, MIN_SLIDE_DURATION).
    """
    lines_covered = seg.lines_end - seg.lines_start + 1
    denom = max(total_lines, 1)
    computed = lines_covered / denom * unit_duration_s
    return max(computed, MIN_SLIDE_DURATION)


def _compute_slide_timings_v2(
    slides: list[Path],
    script_lines: list[DialogueLine],
    line_start_offsets: list[float],
    visuals: list[VisualSpec],
    unit_durations_s: list[float],
) -> list[tuple[Path, float]]:
    """
    Return [(slide_path, duration_seconds), ...] ordered for the ffmpeg concat script.
    Title = 4 s fixed; outro = 6 s fixed; unit slides derived from dialogue beats.
    """
    result: list[tuple[Path, float]] = []

    slide_map = _build_slide_map(slides)
    beat_map = _build_beat_map(script_lines, line_start_offsets, visuals, unit_durations_s)

    # Pre-compute actual cumulative audio end for each unit (no silence inflation)
    unit_audio_end: dict[int, float] = {}
    _cursor = 0.0
    for _ui, _dur in enumerate(unit_durations_s, start=1):
        _cursor += _dur
        unit_audio_end[_ui] = _cursor
    total_audio_end = _cursor

    # Title card
    title_slide = slide_map.get("title")
    if title_slide:
        result.append((title_slide, TITLE_CARD_DURATION))

    # Per-unit slides
    for unit_idx in sorted(beat_map.keys()):
        beats = beat_map[unit_idx]  # {"hook": t, "concept": t, "memory": t}

        hook_t = beats.get("hook", 0.0)
        concept_t = beats.get("concept", hook_t + MIN_SLIDE_DURATION)
        memory_t = beats.get("memory", concept_t + MIN_SLIDE_DURATION)

        # Use actual MP3 boundary (not inflated line offsets) so slides match audio
        unit_end = unit_audio_end.get(unit_idx, total_audio_end)

        raw_hook = concept_t - hook_t
        hook_dur = _clamp(min(raw_hook, MAX_HOOK_DURATION))
        concept_dur = _clamp(memory_t - concept_t + max(0.0, raw_hook - MAX_HOOK_DURATION))
        memory_dur = _clamp(unit_end - memory_t)

        hook_slide = slide_map.get(f"{unit_idx:02d}_hook")
        concept_slide = slide_map.get(f"{unit_idx:02d}_concept")
        memory_slide = slide_map.get(f"{unit_idx:02d}_memory")

        if hook_slide:
            result.append((hook_slide, hook_dur))
        if concept_slide:
            result.append((concept_slide, concept_dur))
        if memory_slide:
            result.append((memory_slide, memory_dur))

    # Outro card
    outro_slide = slide_map.get("outro")
    if outro_slide:
        result.append((outro_slide, OUTRO_CARD_DURATION))

    return result


# Backward-compat alias — callers that used compute_slide_timings still work
compute_slide_timings = _compute_slide_timings_v2


# ── Helpers ──────────────────────────────────────────────────────────────────


def _clamp(duration: float) -> float:
    return max(duration, MIN_SLIDE_DURATION)


def _build_slide_map(slides: list[Path]) -> dict[str, Path]:
    """Map stem identifiers to slide paths."""
    m: dict[str, Path] = {}
    for s in slides:
        stem = s.stem  # e.g. "00_title", "01_hook", "99_outro"
        if "_title" in stem:
            m["title"] = s
        elif "_outro" in stem:
            m["outro"] = s
        elif "_hook" in stem:
            m[f"{stem[:2]}_hook"] = s
        elif "_concept" in stem:
            m[f"{stem[:2]}_concept"] = s
        elif "_memory" in stem:
            m[f"{stem[:2]}_memory"] = s
    return m


def _build_beat_map(
    script_lines: list[DialogueLine],
    line_start_offsets: list[float],
    visuals: list[VisualSpec],
    unit_durations_s: list[float],
) -> dict[int, dict[str, float]]:
    """Return {unit_idx: {hook, concept, memory} in seconds}."""
    unit_specs = {v.unit_index: v for v in visuals if v.slide_type == "unit"}
    beats: dict[int, dict[str, float]] = {i: {} for i in unit_specs}

    # Map unit number → (start offset into audio timeline)
    unit_audio_starts: dict[int, float] = {}
    cursor = 0.0
    for ui, dur in enumerate(unit_durations_s, start=1):
        unit_audio_starts[ui] = cursor
        cursor += dur

    for _i, (ln, offset) in enumerate(zip(script_lines, line_start_offsets, strict=False)):
        u = ln.unit_number
        if u not in beats:
            continue
        b = beats[u]

        if "hook" not in b and ln.speaker == "ALEX":
            b["hook"] = offset

        if "concept" not in b and ln.speaker == "MAYA":
            b["concept"] = offset

    # Memory = last ALEX line of the unit
    for i in range(len(script_lines) - 1, -1, -1):
        ln, offset = script_lines[i], line_start_offsets[i]
        u = ln.unit_number
        if u in beats and "memory" not in beats[u] and ln.speaker == "ALEX":
            beats[u]["memory"] = offset

    # Fill missing beats with audio-based fallbacks
    for u, b in beats.items():
        if "hook" not in b:
            b["hook"] = unit_audio_starts.get(u, 0.0)
        if "concept" not in b:
            b["concept"] = b["hook"] + MIN_SLIDE_DURATION
        if "memory" not in b:
            unit_dur = unit_durations_s[u - 1] if u - 1 < len(unit_durations_s) else 30.0
            b["memory"] = b["hook"] + unit_dur * 0.8

    return beats
