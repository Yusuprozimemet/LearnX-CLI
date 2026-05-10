"""
Integration tests for tutor/visual/__init__.py — run_visual_pipeline and helpers.
Heavy operations (LLM, Playwright, ffmpeg) are mocked.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tutor.visual import _load_timing_json

# ── _load_timing_json tests ───────────────────────────────────────────────────


def test_load_timing_json_returns_none_for_absent_file(tmp_path: Path) -> None:
    assert _load_timing_json(tmp_path) is None


def test_load_timing_json_returns_none_for_wrong_version(tmp_path: Path) -> None:
    (tmp_path / "tutorial.timing.json").write_text(
        json.dumps({"version": 2, "units": {}}), encoding="utf-8"
    )
    assert _load_timing_json(tmp_path) is None


def test_load_timing_json_returns_none_for_corrupt_json(tmp_path: Path) -> None:
    (tmp_path / "tutorial.timing.json").write_text("not json {{{{", encoding="utf-8")
    assert _load_timing_json(tmp_path) is None


# ── run_visual_pipeline tests ─────────────────────────────────────────────────


def _write_units_json(audio_dir: Path, n_units: int = 1) -> None:
    units = []
    for i in range(1, n_units + 1):
        units.append(
            {
                "unit": i,
                "concept": f"Concept {i}",
                "lines": [
                    {"speaker": "ALEX", "text": "Hello", "unit_number": i},
                    {"speaker": "MAYA", "text": "Great", "unit_number": i},
                ],
            }
        )
    (audio_dir / "tutorial.units.json").write_text(json.dumps(units), encoding="utf-8")


def _make_mock_pipeline(tmp_path: Path, video_dir: Path) -> tuple:
    """Return (mock_plan_visuals, mock_plan_segments, mock_render_all, mock_build_srt,
    mock_compute_v3, mock_assemble) all configured with sensible return values."""
    from tutor.models import SlideSegment, VisualSpec

    title_spec = VisualSpec(unit_index=0, slide_type="title_card", title="Test")
    outro_spec = VisualSpec(unit_index=99, slide_type="outro", title="Outro")

    title_path = video_dir / "slides" / "00_title.png"
    outro_path = video_dir / "slides" / "99_outro.png"
    title_path.parent.mkdir(parents=True, exist_ok=True)
    title_path.write_bytes(b"PNG")
    outro_path.write_bytes(b"PNG")

    seg = SlideSegment(
        unit_index=1,
        segment_index=0,
        lines_start=0,
        lines_end=1,
        visual_type="key_insight",
        title="T",
        body=None,
        code=None,
        language=None,
        mermaid=None,
        left=None,
        right=None,
        rows=None,
        png_path=str(video_dir / "slides" / "01_00_key_insight.png"),
    )

    mock_visuals = MagicMock(return_value=[title_spec, outro_spec])
    mock_segments = MagicMock(return_value={1: [seg]})
    mock_render = MagicMock(
        return_value=[title_path, video_dir / "slides" / "01_00_key_insight.png", outro_path]
    )
    mock_srt = MagicMock(return_value="1\n00:00:00,000 --> 00:00:01,000\nALEX: Hello\n")
    mock_compute = MagicMock(return_value=[(title_path, 4.0), (outro_path, 6.0)])
    result_mp4 = video_dir / "full_session.mp4"
    result_mp4.write_bytes(b"fake")
    mock_assemble = MagicMock(return_value=result_mp4)

    return mock_visuals, mock_segments, mock_render, mock_srt, mock_compute, mock_assemble


def test_run_visual_pipeline_six_steps_printed(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    audio_dir = tmp_path / "audio" / "s1"
    video_dir = tmp_path / "video" / "s1"
    audio_dir.mkdir(parents=True)
    video_dir.mkdir(parents=True)
    (audio_dir / "tutorial_units").mkdir()
    _write_units_json(audio_dir)

    mv, ms, mr, msrt, mc, ma = _make_mock_pipeline(tmp_path, video_dir)

    with (
        patch("tutor.generation.visual_planner.plan_visuals", mv),
        patch("tutor.generation.segment_planner.plan_segments", ms),
        patch("tutor.visual.slide_renderer.render_all_slides", mr),
        patch("tutor.visual.subtitle_writer.build_srt", msrt),
        patch("tutor.visual.beat_timer.compute_slide_timings_v3", mc),
        patch("tutor.visual.video_assembler.assemble_session", ma),
        patch("tutor.visual._mp3_duration", return_value=30.0),
    ):
        from tutor.visual import run_visual_pipeline

        run_visual_pipeline("s1", audio_dir, video_dir, MagicMock())

    captured = capsys.readouterr()
    for i in range(1, 7):
        assert f"[{i}/6]" in captured.out


def test_run_visual_pipeline_no_timing_json(tmp_path: Path) -> None:
    audio_dir = tmp_path / "audio" / "s1"
    video_dir = tmp_path / "video" / "s1"
    audio_dir.mkdir(parents=True)
    video_dir.mkdir(parents=True)
    (audio_dir / "tutorial_units").mkdir()
    _write_units_json(audio_dir)
    # Deliberately no tutorial.timing.json

    mv, ms, mr, msrt, mc, ma = _make_mock_pipeline(tmp_path, video_dir)

    with (
        patch("tutor.generation.visual_planner.plan_visuals", mv),
        patch("tutor.generation.segment_planner.plan_segments", ms),
        patch("tutor.visual.slide_renderer.render_all_slides", mr),
        patch("tutor.visual.subtitle_writer.build_srt", msrt),
        patch("tutor.visual.beat_timer.compute_slide_timings_v3", mc),
        patch("tutor.visual.video_assembler.assemble_session", ma),
        patch("tutor.visual._mp3_duration", return_value=30.0),
    ):
        from tutor.visual import run_visual_pipeline

        result = run_visual_pipeline("s1", audio_dir, video_dir, MagicMock())

    assert result is not None


@pytest.mark.slow
def test_output_path_is_under_video_dir(tmp_path: Path) -> None:
    audio_dir = tmp_path / "audio" / "s1"
    video_dir = tmp_path / "video" / "s1"
    audio_dir.mkdir(parents=True)
    video_dir.mkdir(parents=True)
    (audio_dir / "tutorial_units").mkdir()
    _write_units_json(audio_dir)

    mv, ms, mr, msrt, mc, ma = _make_mock_pipeline(tmp_path, video_dir)

    with (
        patch("tutor.generation.visual_planner.plan_visuals", mv),
        patch("tutor.generation.segment_planner.plan_segments", ms),
        patch("tutor.visual.slide_renderer.render_all_slides", mr),
        patch("tutor.visual.subtitle_writer.build_srt", msrt),
        patch("tutor.visual.beat_timer.compute_slide_timings_v3", mc),
        patch("tutor.visual.video_assembler.assemble_session", ma),
        patch("tutor.visual._mp3_duration", return_value=30.0),
    ):
        from tutor.visual import run_visual_pipeline

        result = run_visual_pipeline("s1", audio_dir, video_dir, MagicMock())

    assert str(result).startswith(str(video_dir))
