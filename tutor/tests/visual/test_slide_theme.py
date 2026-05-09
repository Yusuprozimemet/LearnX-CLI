"""Tests for tutor/visual/slide_theme.py — _load_font and wrap_text."""
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from tutor.visual.slide_theme import (
    ACCENT_AMBER,
    ACCENT_CYAN,
    ACCENT_GREEN,
    ACCENT_RED,
    ACCENT_STRIP_W,
    BG_CARD,
    BG_DEEP,
    BODY_Y,
    BULLET_AREA_W,
    BULLET_AREA_W_FULL,
    BULLET_LEAD,
    CANVAS_H,
    CANVAS_W,
    CONTENT_LEFT,
    CONTENT_RIGHT,
    CONTENT_WIDTH,
    DIAGRAM_H,
    DIAGRAM_W,
    DIAGRAM_X,
    DIAGRAM_Y,
    DIVIDER,
    DIVIDER_Y,
    FOOTER_BAR_H,
    FOOTER_BAR_Y,
    TEXT_CODE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TITLE_Y,
    _load_font,
    wrap_text,
)


# ── Constants sanity checks ──────────────────────────────────────────────────

def test_canvas_dimensions():
    assert CANVAS_W == 1920
    assert CANVAS_H == 1080


def test_content_bounds_within_canvas():
    assert CONTENT_LEFT < CONTENT_RIGHT
    assert CONTENT_RIGHT <= CANVAS_W
    assert CONTENT_LEFT >= 0
    assert CONTENT_WIDTH == CONTENT_RIGHT - CONTENT_LEFT


def test_footer_bar_below_body():
    assert FOOTER_BAR_Y > BODY_Y
    assert FOOTER_BAR_Y + FOOTER_BAR_H == CANVAS_H


def test_diagram_area_within_canvas():
    assert DIAGRAM_X >= 0
    assert DIAGRAM_Y >= 0
    assert DIAGRAM_X + DIAGRAM_W <= CANVAS_W
    assert DIAGRAM_Y + DIAGRAM_H <= CANVAS_H


def test_colour_strings_are_hex():
    """All colour constants should be valid #rrggbb hex strings."""
    colours = [
        BG_DEEP, BG_CARD, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_CODE,
        ACCENT_CYAN, ACCENT_GREEN, ACCENT_AMBER, ACCENT_RED, DIVIDER,
    ]
    for c in colours:
        assert c.startswith("#"), f"{c!r} does not start with '#'"
        assert len(c) == 7, f"{c!r} is not #rrggbb length"
        int(c[1:], 16)  # raises if not valid hex


def test_bullet_area_widths():
    assert BULLET_AREA_W < BULLET_AREA_W_FULL
    assert BULLET_AREA_W_FULL == CONTENT_WIDTH


# ── _load_font ───────────────────────────────────────────────────────────────

def test_load_font_returns_a_font():
    font = _load_font(24)
    assert font is not None
    assert isinstance(font, ImageFont.ImageFont)


def test_load_font_bold_returns_a_font():
    font = _load_font(24, bold=True)
    assert font is not None


def test_load_font_mono_returns_a_font():
    font = _load_font(20, mono=True)
    assert font is not None


def test_load_font_mono_bold_returns_a_font():
    font = _load_font(18, bold=True, mono=True)
    assert font is not None


def test_load_font_never_raises_for_any_size():
    """_load_font must not raise regardless of size, bold, or mono flags."""
    for size in (8, 12, 24, 48, 72, 120):
        for bold in (False, True):
            for mono in (False, True):
                font = _load_font(size, bold=bold, mono=mono)
                assert font is not None


def test_load_font_falls_back_when_primary_missing(monkeypatch):
    """When bundled font paths are missing, falls back gracefully."""
    from tutor.visual import slide_theme
    monkeypatch.setattr(slide_theme, "_SANS_REGULAR", Path("/nonexistent/Inter-Regular.ttf"))
    monkeypatch.setattr(slide_theme, "_SANS_BOLD",    Path("/nonexistent/Inter-Bold.ttf"))
    monkeypatch.setattr(slide_theme, "_MONO_REGULAR", Path("/nonexistent/JetBrainsMono-Regular.ttf"))
    monkeypatch.setattr(slide_theme, "_MONO_BOLD",    Path("/nonexistent/JetBrainsMono-Bold.ttf"))

    font = _load_font(24)
    assert font is not None


# ── wrap_text ────────────────────────────────────────────────────────────────

def _make_draw() -> ImageDraw.ImageDraw:
    return ImageDraw.Draw(Image.new("RGB", (CANVAS_W, CANVAS_H)))


def test_wrap_text_short_fits_one_line():
    draw = _make_draw()
    font = _load_font(24)
    lines = wrap_text(draw, "Short text", font, CANVAS_W)
    assert lines == ["Short text"]


def test_wrap_text_empty_returns_empty_string_list():
    draw = _make_draw()
    font = _load_font(24)
    lines = wrap_text(draw, "", font, 800)
    assert lines == [""]


def test_wrap_text_long_text_splits_into_multiple_lines():
    draw = _make_draw()
    font = _load_font(36)
    long_text = "This is a very long sentence that definitely will not fit into 300 pixels width"
    lines = wrap_text(draw, long_text, font, 300)
    assert len(lines) > 1


def test_wrap_text_each_line_within_pixel_width():
    draw = _make_draw()
    font = _load_font(36)
    max_w = 400
    text = "Interfaces define a contract between a class and the outside world and must be implemented"
    lines = wrap_text(draw, text, font, max_w)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        assert bbox[2] - bbox[0] <= max_w, f"Line '{line}' exceeds {max_w}px"


def test_wrap_text_single_very_long_word_still_wraps():
    """A word longer than max_width should still appear on its own line."""
    draw = _make_draw()
    font = _load_font(24)
    result = wrap_text(draw, "Superlongwordwithnospacesatall", font, 1)
    assert len(result) >= 1
    assert "Superlongwordwithnospacesatall" in result


def test_wrap_text_preserves_all_words():
    draw = _make_draw()
    font = _load_font(28)
    text = "one two three four five six"
    lines = wrap_text(draw, text, font, 200)
    rejoined = " ".join(lines)
    assert rejoined == text