from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from tutor.constants import SUMMARY_CACHE_DIR
from tutor.infra.llm import load_prompt, parse_json_response
from tutor.models import VALID_VISUAL_TYPES, DialogueLine, SlideSegment

log = logging.getLogger(__name__)


def plan_segments(
    units_json_path: Path,
    video_dir: Path,
    llm_fn: Callable,
    no_cache: bool = False,
) -> dict[int, list[SlideSegment]]:
    """
    For each teaching unit, call LLM with its dialogue lines.
    Returns dict keyed by unit_index (int) → list[SlideSegment] in line order.
    Writes tutorial.segments.json to video_dir.
    Skips units with no dialogue lines — logs a warning, does not crash.
    Never raises; returns fallback segments on any LLM or parse error.
    """
    unit_lines = _load_unit_lines(units_json_path)
    all_segments: dict[int, list[SlideSegment]] = {}

    for unit_index, (concept, lines) in sorted(unit_lines.items()):
        if not lines:
            log.warning("Unit %d has no dialogue lines — skipping", unit_index)
            continue

        cache_file = _cache_path(unit_index, lines)
        if no_cache and cache_file.exists():
            cache_file.unlink()

        segs = _plan_unit_segments(unit_index, concept, lines, llm_fn, cache_file)
        all_segments[unit_index] = segs

    video_dir.mkdir(parents=True, exist_ok=True)
    segments_path = video_dir / "tutorial.segments.json"
    segments_path.write_text(
        json.dumps(
            {
                "version": 1,
                "units": {str(k): [asdict(s) for s in v] for k, v in sorted(all_segments.items())},
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    log.info("Segments written: %s (%d units)", segments_path, len(all_segments))
    return all_segments


def _plan_unit_segments(
    unit_index: int,
    unit_concept: str,
    lines: list[DialogueLine],
    llm_fn: Callable,
    cache_file: Path,
) -> list[SlideSegment]:
    """Call LLM for one unit. Use file cache when available.
    Return _fallback_segments() on any LLM or parse error."""
    if cache_file.exists():
        log.debug("Cache hit for segments unit %d (%s)", unit_index, unit_concept)
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            return [SlideSegment(**s) for s in data]
        except Exception:
            pass

    prompt = load_prompt("visual_v3.txt")
    dialogue_text = "\n".join(f"{i}: [{ln.speaker}] {ln.text}" for i, ln in enumerate(lines))
    unit_context = json.dumps(
        {
            "unit_index": unit_index,
            "concept": unit_concept,
            "total_lines": len(lines),
            "dialogue": dialogue_text,
        },
        ensure_ascii=False,
    )
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": unit_context},
    ]

    try:
        raw = llm_fn(messages, call_type="segments")
        segs = _parse_segments_response(raw, unit_index, lines)
    except Exception as exc:
        log.warning(
            "Segment planning failed for unit %d (%s): %s — using fallback",
            unit_index,
            unit_concept,
            exc,
        )
        return _fallback_segments(unit_index, lines)

    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(
        json.dumps([asdict(s) for s in segs], ensure_ascii=False),
        encoding="utf-8",
    )
    return segs


def _parse_segments_response(
    raw: str,
    unit_index: int,
    lines: list[DialogueLine],
) -> list[SlideSegment]:
    """Parse LLM JSON array into SlideSegment objects.
    Validate: visual_type in VALID_VISUAL_TYPES; indices in bounds; required
    fields present. Fill gaps. Fall back to _fallback_segments() on failure."""
    try:
        data = parse_json_response(raw)
    except Exception:
        return _fallback_segments(unit_index, lines)

    if not isinstance(data, list):
        return _fallback_segments(unit_index, lines)

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

        result.append(
            SlideSegment(
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
        )

    if not result:
        return _fallback_segments(unit_index, lines)

    return _fill_gaps(result, unit_index, n)


def _fill_gaps(
    raw_segments: list[SlideSegment],
    unit_index: int,
    total_lines: int,
) -> list[SlideSegment]:
    """Ensure every line 0..total_lines-1 is covered by exactly one segment.
    Insert key_insight segments for uncovered ranges.
    Clamp out-of-bound indices to valid range."""
    if total_lines == 0:
        return raw_segments

    segs = sorted(raw_segments, key=lambda s: s.lines_start)
    result: list[SlideSegment] = []
    cursor = 0

    for seg in segs:
        if seg.lines_end < cursor:
            continue  # fully overlapped by previous — skip

        start = max(seg.lines_start, cursor)

        if start > cursor:
            result.append(
                SlideSegment(
                    unit_index=unit_index,
                    segment_index=-1,
                    lines_start=cursor,
                    lines_end=start - 1,
                    visual_type="key_insight",
                    title="Key Insight",
                    body=None,
                    code=None,
                    language=None,
                    mermaid=None,
                    left=None,
                    right=None,
                    rows=None,
                )
            )

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
        result.append(
            SlideSegment(
                unit_index=unit_index,
                segment_index=-1,
                lines_start=cursor,
                lines_end=total_lines - 1,
                visual_type="key_insight",
                title="Key Insight",
                body=None,
                code=None,
                language=None,
                mermaid=None,
                left=None,
                right=None,
                rows=None,
            )
        )

    for i, seg in enumerate(result):
        seg.segment_index = i

    return result


def _fallback_segments(
    unit_index: int,
    lines: list[DialogueLine],
) -> list[SlideSegment]:
    """Produce minimal valid segments without LLM.
    Never returns an empty list."""
    n = len(lines)
    if n == 0:
        return [
            SlideSegment(
                unit_index=unit_index,
                segment_index=0,
                lines_start=0,
                lines_end=0,
                visual_type="hook_question",
                title="Introduction",
                body=None,
                code=None,
                language=None,
                mermaid=None,
                left=None,
                right=None,
                rows=None,
            )
        ]

    segs: list[SlideSegment] = []
    idx = 0

    # First 1-2 lines → hook_question
    hook_end = 0 if n <= 2 else min(1, n - 2)
    segs.append(
        SlideSegment(
            unit_index=unit_index,
            segment_index=idx,
            lines_start=0,
            lines_end=hook_end,
            visual_type="hook_question",
            title="Opening Question",
            body=None,
            code=None,
            language=None,
            mermaid=None,
            left=None,
            right=None,
            rows=None,
        )
    )
    idx += 1
    cursor = hook_end + 1

    # Middle blocks of 3 → key_insight
    while cursor < n - 1:
        end = min(cursor + 2, n - 2)
        segs.append(
            SlideSegment(
                unit_index=unit_index,
                segment_index=idx,
                lines_start=cursor,
                lines_end=end,
                visual_type="key_insight",
                title="Key Insight",
                body=None,
                code=None,
                language=None,
                mermaid=None,
                left=None,
                right=None,
                rows=None,
            )
        )
        idx += 1
        cursor = end + 1

    # Last lines → memory_hook
    if cursor <= n - 1:
        segs.append(
            SlideSegment(
                unit_index=unit_index,
                segment_index=idx,
                lines_start=cursor,
                lines_end=n - 1,
                visual_type="memory_hook",
                title="Remember This",
                body=None,
                code=None,
                language=None,
                mermaid=None,
                left=None,
                right=None,
                rows=None,
            )
        )
    elif len(segs) == 1:
        # n == 1: add memory_hook covering the same line
        segs.append(
            SlideSegment(
                unit_index=unit_index,
                segment_index=idx,
                lines_start=0,
                lines_end=0,
                visual_type="memory_hook",
                title="Remember This",
                body=None,
                code=None,
                language=None,
                mermaid=None,
                left=None,
                right=None,
                rows=None,
            )
        )

    return segs


def _cache_path(unit_index: int, lines: list[DialogueLine]) -> Path:
    """MD5 of all dialogue texts + 'segments_v3' → .tutor_cache/<hash>.segments.json"""
    content = "segments_v3" + "".join(ln.text for ln in lines)
    digest = hashlib.md5(content.encode()).hexdigest()
    return Path(SUMMARY_CACHE_DIR) / f"{digest}.segments.json"


def _load_unit_lines(units_json_path: Path) -> dict[int, tuple[str, list[DialogueLine]]]:
    """Parse tutorial.units.json.
    Returns dict: unit_number → (concept, list[DialogueLine]).
    Only includes teaching units (unit_number >= 1)."""
    raw_units = json.loads(units_json_path.read_text(encoding="utf-8"))
    result: dict[int, tuple[str, list[DialogueLine]]] = {}
    for u in raw_units:
        unit_num = int(u.get("unit", 0))
        if unit_num < 1:
            continue
        concept = str(u.get("concept", ""))
        raw_lines = u.get("lines", [])
        lines = [DialogueLine(**ln) for ln in raw_lines]
        result[unit_num] = (concept, lines)
    return result
