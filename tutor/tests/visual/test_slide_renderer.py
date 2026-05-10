from pathlib import Path

import pytest
from jinja2 import TemplateNotFound

from tutor.models import SlideSegment, VisualSpec
from tutor.visual.slide_renderer import _render_html, render_all_slides

# ── Fixtures ─────────────────────────────────────────────────────────────────


def _make_seg(
    unit_index: int = 1,
    segment_index: int = 0,
    visual_type: str = "key_insight",
    title: str = "Test Slide",
    **kwargs: object,
) -> SlideSegment:
    return SlideSegment(
        unit_index=unit_index,
        segment_index=segment_index,
        lines_start=0,
        lines_end=1,
        visual_type=visual_type,
        title=title,
        body=kwargs.get("body", "Some body text"),  # type: ignore[arg-type]
        code=kwargs.get("code"),  # type: ignore[arg-type]
        language=kwargs.get("language"),  # type: ignore[arg-type]
        mermaid=kwargs.get("mermaid"),  # type: ignore[arg-type]
        left=kwargs.get("left"),  # type: ignore[arg-type]
        right=kwargs.get("right"),  # type: ignore[arg-type]
        rows=kwargs.get("rows"),  # type: ignore[arg-type]
    )


def _make_spec(title: str = "Test Tutorial", subtitle: str = "Subtitle") -> VisualSpec:
    return VisualSpec(unit_index=0, slide_type="title_card", title=title, subtitle=subtitle)


def _make_segments_by_unit() -> dict[int, list[SlideSegment]]:
    return {
        1: [
            _make_seg(unit_index=1, segment_index=0, visual_type="hook_question"),
            _make_seg(unit_index=1, segment_index=1, visual_type="definition"),
            _make_seg(unit_index=1, segment_index=2, visual_type="key_insight"),
        ],
        2: [
            _make_seg(unit_index=2, segment_index=0, visual_type="hook_question"),
            _make_seg(unit_index=2, segment_index=1, visual_type="memory_hook"),
            _make_seg(unit_index=2, segment_index=2, visual_type="key_insight"),
        ],
    }


# ── Non-browser tests ─────────────────────────────────────────────────────────


def test_render_html_returns_string() -> None:
    seg = _make_seg(visual_type="key_insight", body="Remember this!")
    result = _render_html("key_insight", seg=seg, current_dot=1, total_dots=3)
    assert isinstance(result, str)
    assert len(result) > 0
    assert "html" in result.lower()


def test_template_missing_raises_clearly() -> None:
    seg = _make_seg()
    with pytest.raises(TemplateNotFound):
        _render_html("nonexistent_type", seg=seg)


# ── Browser tests (slow) ──────────────────────────────────────────────────────


@pytest.mark.slow
def test_render_all_slides_returns_correct_count(tmp_path: Path) -> None:
    # 2 units × 3 segments + title + outro = 8 paths
    title_spec = _make_spec("My Tutorial")
    outro_spec = _make_spec("Thanks!", "See you next time")
    segs = _make_segments_by_unit()
    paths = render_all_slides(title_spec, outro_spec, segs, tmp_path / "slides", "test")
    assert len(paths) == 8


@pytest.mark.slow
def test_title_is_first_path(tmp_path: Path) -> None:
    title_spec = _make_spec()
    outro_spec = _make_spec("Outro")
    paths = render_all_slides(
        title_spec, outro_spec, _make_segments_by_unit(), tmp_path / "slides", "test"
    )
    assert paths[0].name.startswith("00_title")


@pytest.mark.slow
def test_outro_is_last_path(tmp_path: Path) -> None:
    title_spec = _make_spec()
    outro_spec = _make_spec("Outro")
    paths = render_all_slides(
        title_spec, outro_spec, _make_segments_by_unit(), tmp_path / "slides", "test"
    )
    assert paths[-1].name.startswith("99_outro")


@pytest.mark.slow
def test_png_path_populated_on_segments(tmp_path: Path) -> None:
    title_spec = _make_spec()
    outro_spec = _make_spec("Outro")
    segs_by_unit = _make_segments_by_unit()
    render_all_slides(title_spec, outro_spec, segs_by_unit, tmp_path / "slides", "test")
    for unit_segs in segs_by_unit.values():
        for seg in unit_segs:
            assert seg.png_path != ""


@pytest.mark.slow
def test_output_files_exist_on_disk(tmp_path: Path) -> None:
    title_spec = _make_spec()
    outro_spec = _make_spec("Outro")
    paths = render_all_slides(
        title_spec, outro_spec, _make_segments_by_unit(), tmp_path / "slides", "test"
    )
    for p in paths:
        assert p.exists(), f"Missing: {p}"


@pytest.mark.slow
def test_image_dimensions_are_1920x1080(tmp_path: Path) -> None:
    from PIL import Image  # noqa: PLC0415

    title_spec = _make_spec()
    outro_spec = _make_spec("Outro")
    paths = render_all_slides(
        title_spec, outro_spec, _make_segments_by_unit(), tmp_path / "slides", "test"
    )
    for p in paths:
        img = Image.open(p)
        assert img.size == (1920, 1080), f"{p.name}: expected 1920×1080, got {img.size}"


def test_screenshot_uses_file_url_not_set_content(tmp_path: Path) -> None:
    """_screenshot must call page.goto with a file:// URL, never page.set_content."""
    from unittest.mock import MagicMock, patch

    from tutor.visual.slide_renderer import _screenshot

    mock_page = MagicMock()
    out = tmp_path / "out.png"

    with (
        patch("tutor.visual.slide_renderer.tempfile.NamedTemporaryFile") as mock_ntf,
        patch("tutor.visual.slide_renderer.os.unlink"),
    ):
        mock_file = MagicMock()
        mock_file.__enter__ = lambda s: s
        mock_file.__exit__ = MagicMock(return_value=False)
        mock_file.name = str(tmp_path / "tmp.html")
        mock_ntf.return_value = mock_file
        _screenshot(mock_page, "<html></html>", out, False, False)

    mock_page.goto.assert_called_once()
    call_url = mock_page.goto.call_args[0][0]
    assert call_url.startswith("file:///")
    mock_page.set_content.assert_not_called()


def test_tmp_file_cleaned_up_after_screenshot(tmp_path: Path) -> None:
    """Temp HTML file must be deleted even if screenshot succeeds."""
    import os
    from unittest.mock import MagicMock

    from tutor.visual.slide_renderer import _screenshot

    recorded: list[str] = []

    mock_page = MagicMock()
    out = tmp_path / "out.png"

    original_unlink = os.unlink

    def tracking_unlink(path: str) -> None:
        recorded.append(path)
        try:
            original_unlink(path)
        except OSError:
            pass

    import tutor.visual.slide_renderer as sr

    original = sr.os.unlink
    sr.os.unlink = tracking_unlink  # type: ignore[assignment]
    try:
        _screenshot(mock_page, "<html></html>", out, False, False)
    finally:
        sr.os.unlink = original  # type: ignore[assignment]

    assert len(recorded) == 1
    assert recorded[0].endswith(".html")


@pytest.mark.slow
def test_invalid_mermaid_does_not_crash(tmp_path: Path) -> None:
    title_spec = _make_spec()
    outro_spec = _make_spec("Outro")
    bad_diagram = _make_seg(
        unit_index=1,
        segment_index=0,
        visual_type="diagram",
        mermaid="this is not valid mermaid @@##!!",
    )
    segs = {1: [bad_diagram]}
    paths = render_all_slides(title_spec, outro_spec, segs, tmp_path / "slides", "test")
    diagram_path = next((p for p in paths if "diagram" in p.name), None)
    assert diagram_path is not None
    assert diagram_path.exists()
