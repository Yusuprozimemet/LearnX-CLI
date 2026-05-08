"""
Convert a flat list of DialogueLines into a SRT subtitle file.
No ffmpeg, no Pillow, no LLM calls here.
"""
from tutor.constants import SILENCE_TURN_MS, SILENCE_UNIT_MS, WPM
from tutor.models import DialogueLine

MIN_LINE_DURATION_S = 1.5
MAX_SUBTITLE_CHARS  = 60


def build_srt(
    all_lines: list[DialogueLine],
    unit_durations_s: list[float],
) -> str:
    """
    Build a complete SRT string for the session.
    all_lines: flat list in play order; unit_durations_s: actual MP3 duration per unit.
    """
    offsets, durations = _compute_timing(all_lines, unit_durations_s)
    entries: list[str] = []
    for idx, (line, start, dur) in enumerate(zip(all_lines, offsets, durations), start=1):
        end = start + dur
        text = _wrap_subtitle(line.speaker, line.text)
        entries.append(
            f"{idx}\n{_format_timestamp(start)} --> {_format_timestamp(end)}\n{text}\n"
        )
    return "\n".join(entries)


def get_line_start_offsets(
    all_lines: list[DialogueLine],
    unit_durations_s: list[float],
) -> list[float]:
    """Return the start time (seconds) of each line. Shares logic with build_srt."""
    offsets, _ = _compute_timing(all_lines, unit_durations_s)
    return offsets


# ── Internals ────────────────────────────────────────────────────────────────

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
            scaled = _scale_unit_lines(
                [raw_durations[i] for i in indices], actual_s
            )
            for i, d in zip(indices, scaled):
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
    ms       = int(round(seconds * 1000))
    hh       = ms // 3_600_000;  ms -= hh * 3_600_000
    mm       = ms //    60_000;  ms -= mm *    60_000
    ss       = ms //     1_000;  ms -= ss *     1_000
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
    remainder = " ".join(words[len(line1_words):])
    line1 = prefix + " ".join(line1_words)
    return f"{line1}\n{remainder}" if remainder else line1
