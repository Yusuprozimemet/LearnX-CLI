from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from tutor.constants import SUMMARY_CACHE_DIR
from tutor.generation.segment_parser import fallback_segments, parse_segments_response
from tutor.infra.llm import load_prompt
from tutor.models import DialogueLine, SlideSegment

log = logging.getLogger(__name__)


def plan_segments(
    units_json_path: Path,
    video_dir: Path,
    llm_fn: Callable,
    no_cache: bool = False,
) -> dict[int, list[SlideSegment]]:
    """For each teaching unit call LLM with its dialogue lines.

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

    Returns fallback_segments() on any LLM or parse error.
    """
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
        segs = parse_segments_response(raw, unit_index, lines)
    except Exception as exc:
        log.warning(
            "Segment planning failed for unit %d (%s): %s — using fallback",
            unit_index,
            unit_concept,
            exc,
        )
        return fallback_segments(unit_index, lines)

    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(
        json.dumps([asdict(s) for s in segs], ensure_ascii=False),
        encoding="utf-8",
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
    Only includes teaching units (unit_number >= 1).
    Falls back to script.txt + timing.json when units.json has no lines.
    """
    import re

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

    if any(len(lines) > 0 for _, lines in result.values()):
        return result

    script_path = units_json_path.parent / "tutorial.script.txt"
    if not script_path.exists():
        return result

    speaker_re = re.compile(r"^(ALEX|MAYA|SAM):\s*(.+)$")
    all_pairs = [
        (m.group(1), m.group(2))
        for ln in script_path.read_text(encoding="utf-8").splitlines()
        if (m := speaker_re.match(ln.strip()))
    ]
    if not all_pairs:
        return result

    timing_path = units_json_path.parent / "tutorial.timing.json"
    lines_per_unit: dict[int, int] = {}
    if timing_path.exists():
        try:
            timing = json.loads(timing_path.read_text(encoding="utf-8"))
            if timing.get("version") == 1:
                for uk, entries in timing.get("units", {}).items():
                    lines_per_unit[int(uk)] = len(entries)
        except Exception:
            pass

    if lines_per_unit and all(u in lines_per_unit for u in result):
        n_teaching = sum(lines_per_unit.values())
        n_non = max(0, len(all_pairs) - n_teaching)
        n_intro = (n_non + 1) // 2
        cursor = n_intro
        for unit_num in sorted(result.keys()):
            concept = result[unit_num][0]
            count = lines_per_unit[unit_num]
            pairs = all_pairs[cursor : cursor + count]
            cursor += count
            result[unit_num] = (
                concept,
                [DialogueLine(speaker=s, text=t, unit_number=unit_num) for s, t in pairs],
            )
    else:
        n_units = len(result)
        n_lines = len(all_pairs)
        per_unit = max(1, n_lines // max(n_units, 1))
        for i, unit_num in enumerate(sorted(result.keys())):
            concept = result[unit_num][0]
            start = i * per_unit
            end = n_lines if i == n_units - 1 else min(start + per_unit, n_lines)
            pairs = all_pairs[start:end]
            result[unit_num] = (
                concept,
                [DialogueLine(speaker=s, text=t, unit_number=unit_num) for s, t in pairs],
            )

    return result
