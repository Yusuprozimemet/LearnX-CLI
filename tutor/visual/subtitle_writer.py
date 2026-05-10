"""
Convert a flat list of DialogueLines into a SRT subtitle file.
No ffmpeg, no Pillow, no LLM calls here.
"""

from tutor.constants import SILENCE_TURN_MS, SILENCE_UNIT_MS, WPM
from tutor.models import DialogueLine

MIN_LINE_DURATION_S = 1.5
MAX_SUBTITLE_CHARS = 60


def build_srt(
    all_lines: list[DialogueLine],
    unit_durations_s: list[float],
    timing_json: dict | None = None,
) -> str:
    """
    Build a complete SRT string for the session.
    If timing_json provided: use exact start_ms/end_ms per line.
    If timing_json is None: use WPM estimation (existing behaviour, unchanged).
    """
    offsets = get_line_start_offsets(all_lines, unit_durations_s, timing_json)
    _, durations = _compute_timing(all_lines, unit_durations_s)
    entries: list[str] = []
    for idx, (line, start, dur) in enumerate(
        zip(all_lines, offsets, durations, strict=False), start=1
    ):
        end = start + dur
        text = _wrap_subtitle(line.speaker, line.text)
        entries.append(f"{idx}\n{_format_timestamp(start)} --> {_format_timestamp(end)}\n{text}\n")
    return "\n".join(entries)


def get_line_start_offsets(
    all_lines: list[DialogueLine],
    unit_durations_s: list[float],
    timing_json: dict | None = None,
) -> list[float]:
    """
    Return the start time (seconds) of each line.
    If timing_json provided: use exact offsets.
    If timing_json is None: use WPM estimation (existing behaviour, unchanged).
    """
    if timing_json is not None:
        return _exact_line_offsets(all_lines, unit_durations_s, timing_json)
    offsets, _ = _compute_timing(all_lines, unit_durations_s)
    return offsets


# ── Internals ────────────────────────────────────────────────────────────────


def _exact_line_offsets(
    all_lines: list[DialogueLine],
    unit_durations_s: list[float],
    timing_json: dict,
) -> list[float]:
    """
    Compute session-global start time for each line using timing_json.

    unit_start[u] accumulates unit durations + inter-unit silence so
    subtitle timestamps align with the concatenated video.
    Lines not in timing_json (intro/outro) fall back to WPM estimation.
    """
    # Build cumulative unit start offsets
    unit_start: dict[int, float] = {}
    cursor = 0.0
    for u_idx, dur in enumerate(unit_durations_s, start=1):
        unit_start[u_idx] = cursor
        cursor += dur + SILENCE_UNIT_MS / 1000

    units_timing: dict[str, list] = timing_json.get("units", {})
    wpm_offsets, _ = _compute_timing(all_lines, unit_durations_s)

    # Track within-unit line index per unit
    unit_line_idx: dict[int, int] = {}
    offsets: list[float] = []

    for i, ln in enumerate(all_lines):
        u = ln.unit_number
        key = str(u)
        unit_entries = units_timing.get(key)

        if unit_entries is None:
            offsets.append(wpm_offsets[i])
            continue

        within_idx = unit_line_idx.get(u, 0)
        unit_line_idx[u] = within_idx + 1

        if within_idx >= len(unit_entries):
            offsets.append(wpm_offsets[i])
            continue

        entry = unit_entries[within_idx]
        offsets.append(unit_start.get(u, 0.0) + entry["start_ms"] / 1000)

    return offsets


def _compute_timing(
    all_lines: list[DialogueLine],
    unit_durations_s: list[float],
) -> tuple[list[float], list[float]]:
    """Return (start_offsets, durations) for every line."""
    # Group lines by unit number (preserving order)
    unit_groups: dict[int, list[int]] = {}
    for i, ln in enumerate(all_lines):
        unit_groups.setdefault(ln.unit_number, []).append(i)

    raw_durations: list[float] = [_line_duration(ln.text) for ln in all_lines]

    # Scale per-unit durations to match actual MP3 lengths
    for unit_num, indices in unit_groups.items():
        if unit_num < 1:
            continue
        unit_idx = unit_num - 1
        if unit_idx >= len(unit_durations_s):
            continue
        actual_s = unit_durations_s[unit_idx]
        estimated_s = sum(raw_durations[i] for i in indices) + (
            SILENCE_TURN_MS / 1000 * (len(indices) - 1)
        )
        if estimated_s > 0 and abs(estimated_s - actual_s) / estimated_s > 0.10:
            scaled = _scale_unit_lines([raw_durations[i] for i in indices], actual_s)
            for i, d in zip(indices, scaled, strict=False):
                raw_durations[i] = d

    # Build offsets with silence gaps
    offsets: list[float] = []
    cursor = 0.0
    prev_unit: int | None = None

    for i, ln in enumerate(all_lines):
        if prev_unit is not None and ln.unit_number != prev_unit:
            cursor += SILENCE_UNIT_MS / 1000
        elif prev_unit is not None:
            cursor += SILENCE_TURN_MS / 1000
        offsets.append(cursor)
        cursor += raw_durations[i]
        prev_unit = ln.unit_number

    return offsets, raw_durations


def _line_duration(text: str) -> float:
    words = len(text.split())
    return max(words / WPM * 60, MIN_LINE_DURATION_S)


def _scale_unit_lines(durations: list[float], actual_s: float) -> list[float]:
    total = sum(durations)
    if total == 0:
        return durations
    factor = actual_s / total
    return [d * factor for d in durations]


def _format_timestamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    hh = ms // 3_600_000
    ms -= hh * 3_600_000
    mm = ms // 60_000
    ms -= mm * 60_000
    ss = ms // 1_000
    ms -= ss * 1_000
    return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"


def _wrap_subtitle(speaker: str, text: str, max_chars: int = MAX_SUBTITLE_CHARS) -> str:
    prefix = f"{speaker}: "
    full = prefix + text
    if len(full) <= max_chars:
        return full
    # Wrap: keep prefix on first line, spill remainder
    words = text.split()
    line1_words: list[str] = []
    for word in words:
        candidate = prefix + " ".join(line1_words + [word])
        if len(candidate) <= max_chars:
            line1_words.append(word)
        else:
            break
    remainder = " ".join(words[len(line1_words) :])
    line1 = prefix + " ".join(line1_words)
    return f"{line1}\n{remainder}" if remainder else line1
