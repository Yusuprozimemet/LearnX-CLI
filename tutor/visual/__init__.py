"""
Entry point for the v2 visual pipeline.
Reads from audio/<session>/, writes to video/<session>/.
"""

import json
import logging
import re
import subprocess
from pathlib import Path

from tutor.infra.llm import LLMFn
from tutor.models import DialogueLine

_UNIT_MP3_RE = re.compile(r"^unit_\d+$")  # matches unit_01, unit_02 — not unit_00_intro

log = logging.getLogger(__name__)


def run_visual_pipeline(
    session: str,
    audio_dir: Path,
    video_dir: Path,
    llm_fn: LLMFn,
    difficulty: str = "beginner",
    no_cache: bool = False,
) -> Path:
    """
    Full Day 8-11 pipeline for one session.
    Reads from audio_dir, writes to video_dir.
    Returns path to full_session.mp4.
    """
    from tutor.generation.visual_planner import plan_visuals
    from tutor.visual.beat_timer import compute_slide_timings
    from tutor.visual.diagram_renderer import render_diagram
    from tutor.visual.slide_compositor import compose_all
    from tutor.visual.subtitle_writer import build_srt, get_line_start_offsets
    from tutor.visual.video_assembler import assemble_session

    units_json = audio_dir / "tutorial.units.json"
    doc_title = _doc_title_from_units(units_json)
    unit_mp3s = sorted(
        p for p in (audio_dir / "tutorial_units").glob("unit_*.mp3") if _UNIT_MP3_RE.match(p.stem)
    )
    slides_dir = video_dir / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)

    print("\n  [1/4] Generating visual specs...")
    visuals = plan_visuals(units_json, doc_title, session, llm_fn, difficulty, video_dir, no_cache)

    print("  [2/4] Rendering diagrams and compositing slides...")
    diagram_pngs: dict[int, Path] = {}
    for v in visuals:
        if v.slide_type == "unit":
            png = render_diagram(v, slides_dir)
            if png:
                diagram_pngs[v.unit_index] = png
    slide_paths = compose_all(visuals, diagram_pngs, slides_dir, session)

    print("  [3/4] Building SRT subtitles...")
    all_lines = _load_all_lines(units_json)
    unit_durations = [_mp3_duration(mp3) for mp3 in unit_mp3s]
    srt_text = build_srt(all_lines, unit_durations)
    srt_path = video_dir / "subtitles.srt"
    srt_path.write_text(srt_text, encoding="utf-8")

    print("  [4/4] Assembling video...")
    line_offsets = get_line_start_offsets(all_lines, unit_durations)
    slide_timings = compute_slide_timings(
        slide_paths, all_lines, line_offsets, visuals, unit_durations
    )
    return assemble_session(
        video_dir, audio_dir / "tutorial_units", slide_timings, unit_mp3s, srt_path
    )


def _doc_title_from_units(units_json: Path) -> str:
    """
    Priority: H1 from source markdown → source filename stem → first unit concept.
    Reads tutorial.meta.json (written by /generate) for the source file path.
    """
    import re as _re

    meta_path = units_json.parent / "tutorial.meta.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            src = Path(meta.get("source_file", ""))
            if src.exists():
                text = src.read_text(encoding="utf-8", errors="replace")
                # Try H1 first, then first H2 that isn't boilerplate
                _SKIP = {"learning objectives", "introduction", "overview", "contents"}
                for pat in (r"^#\s+(.+)$", r"^##\s+(.+)$"):
                    for m in _re.finditer(pat, text, _re.MULTILINE):
                        raw = m.group(1).strip()
                        # strip leading "1. " / "1) " style numbering
                        raw = _re.sub(r"^\d+[.)]\s*", "", raw)
                        # strip emoji and punctuation, keep words/hyphens
                        candidate = _re.sub(r"[^\w\s\-&]", "", raw).strip()
                        if candidate.lower() not in _SKIP and len(candidate) > 3:
                            return candidate
            # Format the path: week2/3.md → "Week 2 - Part 3"
            if src.stem:
                stem = src.stem.replace("_", " ").replace("-", " ")
                parent = src.parent.name.replace("_", " ").replace("-", " ")
                if stem.isdigit() and parent:
                    return f"{parent.title()} - Part {stem}"
                return stem.title()
        except Exception:
            pass
    try:
        units = json.loads(units_json.read_text(encoding="utf-8"))
        if units:
            return str(units[0].get("concept", "Tutorial"))
    except Exception:
        pass
    return "Tutorial"


def _load_all_lines(units_json: Path) -> list[DialogueLine]:
    """
    Load dialogue lines. Tries units JSON `lines` field first;
    falls back to parsing tutorial.script.txt in the same directory.
    """
    import re as _re

    try:
        units = json.loads(units_json.read_text(encoding="utf-8"))
        lines: list[DialogueLine] = []
        for u in units:
            for raw in u.get("lines", []):
                lines.append(DialogueLine(**raw))
        if lines:
            return lines
    except Exception:
        pass

    # Fallback: parse tutorial.script.txt
    script_path = units_json.parent / "tutorial.script.txt"
    if not script_path.exists():
        log.warning("No dialogue lines source found — subtitles will be empty")
        return []

    try:
        n_units = len(json.loads(units_json.read_text(encoding="utf-8")))
    except Exception:
        n_units = 1

    raw_lines = [
        ln.strip() for ln in script_path.read_text(encoding="utf-8").splitlines() if ln.strip()
    ]
    speaker_re = _re.compile(r"^(ALEX|MAYA|SAM):\s*(.+)$")
    valid = [(m.group(1), m.group(2)) for ln in raw_lines if (m := speaker_re.match(ln))]

    if not valid:
        return []

    # Distribute lines evenly across units (rough heuristic)
    per_unit = max(1, len(valid) // max(n_units, 1))
    result: list[DialogueLine] = []
    for i, (speaker, text) in enumerate(valid):
        unit_num = min(i // per_unit + 1, n_units)
        result.append(DialogueLine(speaker=speaker, text=text, unit_number=unit_num))
    return result


def _mp3_duration(path: Path) -> float:
    """Return duration in seconds via ffprobe. Falls back to 0.0 on error."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            timeout=10,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def _format_duration(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"
