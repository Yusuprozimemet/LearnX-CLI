"""
Entry point for the v2 visual pipeline.
Reads from audio/<session>/, writes to video/<session>/.
"""
import json
import logging
import subprocess
from pathlib import Path
from typing import Callable

from tutor.models import DialogueLine

log = logging.getLogger(__name__)


def run_visual_pipeline(
    session: str,
    audio_dir: Path,
    video_dir: Path,
    llm_fn: Callable,
    difficulty: str = "beginner",
    no_cache: bool = False,
) -> Path:
    """
    Full Day 8-11 pipeline for one session.
    Reads from audio_dir, writes to video_dir.
    Returns path to full_session.mp4.
    """
    from tutor.generation.visual_planner import plan_visuals
    from tutor.visual.diagram_renderer import render_diagram
    from tutor.visual.slide_compositor import compose_all
    from tutor.visual.subtitle_writer import build_srt, get_line_start_offsets
    from tutor.visual.beat_timer import compute_slide_timings
    from tutor.visual.video_assembler import assemble_session

    units_json = audio_dir / "tutorial.units.json"
    doc_title  = _doc_title_from_units(units_json)
    unit_mp3s  = sorted((audio_dir / "tutorial_units").glob("unit_*.mp3"))
    slides_dir = video_dir / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)

    print("\n  [1/4] Generating visual specs...")
    visuals = plan_visuals(
        units_json, doc_title, session, llm_fn, difficulty, video_dir, no_cache
    )

    print("  [2/4] Rendering diagrams and compositing slides...")
    diagram_pngs: dict[int, Path] = {}
    for v in visuals:
        if v.slide_type == "unit":
            png = render_diagram(v, slides_dir)
            if png:
                diagram_pngs[v.unit_index] = png
    slide_paths = compose_all(visuals, diagram_pngs, slides_dir, session)

    print("  [3/4] Building SRT subtitles...")
    all_lines      = _load_all_lines(units_json)
    unit_durations = [_mp3_duration(mp3) for mp3 in unit_mp3s]
    srt_text       = build_srt(all_lines, unit_durations)
    srt_path       = video_dir / "subtitles.srt"
    srt_path.write_text(srt_text, encoding="utf-8")

    print("  [4/4] Assembling video...")
    line_offsets  = get_line_start_offsets(all_lines, unit_durations)
    slide_timings = compute_slide_timings(
        slide_paths, all_lines, line_offsets, visuals, unit_durations
    )
    return assemble_session(
        video_dir, audio_dir / "tutorial_units", slide_timings, unit_mp3s, srt_path
    )


def _doc_title_from_units(units_json: Path) -> str:
    try:
        units = json.loads(units_json.read_text(encoding="utf-8"))
        if units:
            return str(units[0].get("concept", "Tutorial"))
    except Exception:
        pass
    return "Tutorial"


def _load_all_lines(units_json: Path) -> list[DialogueLine]:
    """Load dialogue lines from the units JSON if a script field is present."""
    try:
        units = json.loads(units_json.read_text(encoding="utf-8"))
        lines: list[DialogueLine] = []
        for u in units:
            for raw in u.get("lines", []):
                lines.append(DialogueLine(**raw))
        return lines
    except Exception:
        log.warning("Could not load dialogue lines from %s", units_json)
        return []


def _mp3_duration(path: Path) -> float:
    """Return duration in seconds via ffprobe. Falls back to 0.0 on error."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
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
