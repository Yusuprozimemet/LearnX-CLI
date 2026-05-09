"""
Map slide PNGs to playback durations based on dialogue beat points.
No ffmpeg, no Pillow, no LLM here.
"""
from pathlib import Path

from tutor.models import DialogueLine, VisualSpec

MIN_SLIDE_DURATION  = 3.0   # seconds
MAX_HOOK_DURATION   = 30.0  # cap hook slide — ALEX can monologue for a long time before MAYA
TITLE_CARD_DURATION = 4.0
OUTRO_CARD_DURATION = 6.0


def compute_slide_timings(
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
    unit_count = len([v for v in visuals if v.slide_type == "unit"])
    result: list[tuple[Path, float]] = []

    slide_map = _build_slide_map(slides)
    beat_map  = _build_beat_map(script_lines, line_start_offsets, visuals, unit_durations_s)

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
        beats = beat_map[unit_idx]   # {"hook": t, "concept": t, "memory": t}

        hook_t    = beats.get("hook", 0.0)
        concept_t = beats.get("concept", hook_t + MIN_SLIDE_DURATION)
        memory_t  = beats.get("memory", concept_t + MIN_SLIDE_DURATION)

        # Use actual MP3 boundary (not inflated line offsets) so slides match audio
        unit_end = unit_audio_end.get(unit_idx, total_audio_end)

        raw_hook    = concept_t - hook_t
        hook_dur    = _clamp(min(raw_hook, MAX_HOOK_DURATION))
        concept_dur = _clamp(memory_t - concept_t + max(0.0, raw_hook - MAX_HOOK_DURATION))
        memory_dur  = _clamp(unit_end - memory_t)

        hook_slide    = slide_map.get(f"{unit_idx:02d}_hook")
        concept_slide = slide_map.get(f"{unit_idx:02d}_concept")
        memory_slide  = slide_map.get(f"{unit_idx:02d}_memory")

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


# ── Helpers ──────────────────────────────────────────────────────────────────

def _clamp(duration: float) -> float:
    return max(duration, MIN_SLIDE_DURATION)


def _build_slide_map(slides: list[Path]) -> dict[str, Path]:
    """Map stem identifiers to slide paths."""
    m: dict[str, Path] = {}
    for s in slides:
        stem = s.stem           # e.g. "00_title", "01_hook", "99_outro"
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

    for i, (ln, offset) in enumerate(zip(script_lines, line_start_offsets)):
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
