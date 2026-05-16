"""Parse and normalise raw LLM segment responses into SlideSegment lists."""

from __future__ import annotations

import logging

from tutor.infra.llm import parse_json_response
from tutor.models import VALID_VISUAL_TYPES, DialogueLine, SlideSegment

log = logging.getLogger(__name__)


def parse_segments_response(
    raw: str,
    unit_index: int,
    lines: list[DialogueLine],
) -> list[SlideSegment]:
    """Parse LLM JSON array into SlideSegment objects.

    Validates visual_type, clamps indices, fills gaps.
    Falls back to fallback_segments() on any parse failure.
    """
    try:
        data = parse_json_response(raw)
    except Exception:
        return fallback_segments(unit_index, lines)

    if not isinstance(data, list):
        return fallback_segments(unit_index, lines)

    n = len(lines)
    result: list[SlideSegment] = []

    for item in data:
        if not isinstance(item, dict):
            continue

        vtype = item.get("visual_type", "key_insight")
        if vtype not in VALID_VISUAL_TYPES:
            vtype = "key_insight"

        ls = int(item.get("lines_start", 0))
        le = int(item.get("lines_end", 0))

        if ls > le:
            ls, le = le, ls

        ls = max(0, ls)
        le = min(n - 1, le) if n > 0 else 0

        title = item.get("title") or vtype.replace("_", " ").title()
        body = item.get("body") or None
        code = item.get("code") or None
        language = item.get("language") or None
        mermaid = item.get("mermaid") if vtype == "diagram" else None
        left = item.get("left") or None
        right = item.get("right") or None
        rows = item.get("rows") or None

        if rows is not None:
            if not (isinstance(rows, list) and all(isinstance(r, list) for r in rows)):
                rows = None

        seg = SlideSegment(
            unit_index=unit_index,
            segment_index=0,
            lines_start=ls,
            lines_end=le,
            visual_type=vtype,
            title=title,
            body=body,
            code=code,
            language=language,
            mermaid=mermaid,
            left=left,
            right=right,
            rows=rows,
        )
        result.append(_validate_segment(seg))

    if not result:
        return fallback_segments(unit_index, lines)

    return fill_gaps(result, unit_index, n)


def fill_gaps(
    raw_segments: list[SlideSegment],
    unit_index: int,
    total_lines: int,
) -> list[SlideSegment]:
    """Ensure every line 0..total_lines-1 is covered by exactly one segment.

    Inserts key_insight segments for uncovered ranges and renumbers segment_index.
    """
    if total_lines == 0:
        return raw_segments

    segs = sorted(raw_segments, key=lambda s: s.lines_start)
    result: list[SlideSegment] = []
    cursor = 0

    for seg in segs:
        if seg.lines_end < cursor:
            continue

        start = max(seg.lines_start, cursor)

        if start > cursor:
            result.append(_make_gap_segment(unit_index, cursor, start - 1))

        adjusted = (
            seg
            if seg.lines_start == start
            else SlideSegment(
                unit_index=seg.unit_index,
                segment_index=seg.segment_index,
                lines_start=start,
                lines_end=seg.lines_end,
                visual_type=seg.visual_type,
                title=seg.title,
                body=seg.body,
                code=seg.code,
                language=seg.language,
                mermaid=seg.mermaid,
                left=seg.left,
                right=seg.right,
                rows=seg.rows,
            )
        )
        result.append(adjusted)
        cursor = adjusted.lines_end + 1

    if cursor < total_lines:
        result.append(_make_gap_segment(unit_index, cursor, total_lines - 1))

    for i, seg in enumerate(result):
        seg.segment_index = i

    return result


def fallback_segments(
    unit_index: int,
    lines: list[DialogueLine],
) -> list[SlideSegment]:
    """Produce minimal valid segments without LLM. Never returns an empty list."""
    n = len(lines)
    if n == 0:
        return [_make_segment(unit_index, 0, 0, 0, "hook_question", "Introduction")]

    segs: list[SlideSegment] = []
    idx = 0

    hook_end = 0 if n <= 2 else min(1, n - 2)
    segs.append(_make_segment(unit_index, idx, 0, hook_end, "hook_question", "Opening Question"))
    idx += 1
    cursor = hook_end + 1

    while cursor < n - 1:
        end = min(cursor + 2, n - 2)
        segs.append(_make_segment(unit_index, idx, cursor, end, "key_insight", "Key Insight"))
        idx += 1
        cursor = end + 1

    if cursor <= n - 1:
        segs.append(_make_segment(unit_index, idx, cursor, n - 1, "memory_hook", "Remember This"))
    elif len(segs) == 1:
        segs.append(_make_segment(unit_index, idx, 0, 0, "memory_hook", "Remember This"))

    return segs


# ── private helpers ───────────────────────────────────────────────────────────


def _validate_segment(seg: SlideSegment) -> SlideSegment:
    """Post-process a segment: reclassify types that would produce blank slides."""
    if seg.visual_type == "step_sequence" and not seg.body:
        log.warning(
            "segment %d-%d is step_sequence but body is empty — falling back to definition",
            seg.lines_start,
            seg.lines_end,
        )
        seg.visual_type = "definition"
        seg.body = seg.title
    if seg.visual_type == "callout" and not seg.body:
        log.warning(
            "segment %d-%d is callout but body is empty — falling back to key_insight",
            seg.lines_start,
            seg.lines_end,
        )
        seg.visual_type = "key_insight"
    return seg


def _make_segment(
    unit_index: int,
    segment_index: int,
    lines_start: int,
    lines_end: int,
    visual_type: str,
    title: str,
) -> SlideSegment:
    return SlideSegment(
        unit_index=unit_index,
        segment_index=segment_index,
        lines_start=lines_start,
        lines_end=lines_end,
        visual_type=visual_type,
        title=title,
        body=None,
        code=None,
        language=None,
        mermaid=None,
        left=None,
        right=None,
        rows=None,
    )


def _make_gap_segment(unit_index: int, start: int, end: int) -> SlideSegment:
    return _make_segment(unit_index, -1, start, end, "key_insight", "Key Insight")
