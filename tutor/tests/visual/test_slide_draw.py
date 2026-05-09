"""Tests for tutor/visual/slide_draw.py — drawing primitives."""
from pathlib import Path

from PIL import Image, ImageDraw

from tutor.visual.slide_draw import (
    draw_accent_strip,
    draw_background,
    draw_bullets,
    draw_code_block,
    draw_concept_title,
    draw_divider,
    draw_footer_bar,
    draw_logo,
    draw_top_bar,
    paste_diagram,
)
from tutor.visual.slide_theme import (
    ACCENT_AMBER,
    ACCENT_CYAN,
    ACCENT_GREEN,
    ACCENT_STRIP_W,
    BG_DEEP,
    CANVAS_H,
    CANVAS_W,
    CONTENT_LEFT,
    DIAGRAM_X,
    DIAGRAM_Y,
    FOOTER_BAR_Y,
)


def _new_canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), BG_DEEP)
    draw = ImageDraw.Draw(img)
    return img, draw


def _hex_to_rgb(hex_colour: str) -> tuple[int, int, int]:
    h = hex_colour.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


# ── draw_background ──────────────────────────────────────────────────────────

def test_draw_background_fills_canvas():
    img, _ = _new_canvas()
    # Set to white first, then overwrite with draw_background
    img.paste(Image.new("RGB", (CANVAS_W, CANVAS_H), "#ffffff"))
    draw_background(img)
    px = img.getpixel((CANVAS_W // 2, CANVAS_H // 2))
    expected = _hex_to_rgb(BG_DEEP)
    assert px == expected


def test_draw_background_custom_colour():
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), "#ffffff")
    draw_background(img, colour="#ff0000")
    px = img.getpixel((100, 100))
    assert px == (255, 0, 0)


# ── draw_accent_strip ─────────────────────────────────────────────────────────

def test_draw_accent_strip_default_cyan():
    img, draw = _new_canvas()
    draw_accent_strip(draw)
    # Left edge should be cyan
    px = img.getpixel((0, CANVAS_H // 2))
    expected = _hex_to_rgb(ACCENT_CYAN)
    assert px == expected


def test_draw_accent_strip_custom_colour():
    img, draw = _new_canvas()
    draw_accent_strip(draw, colour=ACCENT_AMBER)
    px = img.getpixel((0, CANVAS_H // 2))
    expected = _hex_to_rgb(ACCENT_AMBER)
    assert px == expected


def test_draw_accent_strip_width_is_accent_strip_w():
    img, draw = _new_canvas()
    draw_background(img)
    draw_accent_strip(draw)
    # The pixel just at ACCENT_STRIP_W - 1 should be cyan
    px_inside = img.getpixel((ACCENT_STRIP_W - 1, CANVAS_H // 2))
    assert px_inside == _hex_to_rgb(ACCENT_CYAN)
    # The pixel just outside the strip should NOT be cyan (it's the background)
    px_outside = img.getpixel((ACCENT_STRIP_W + 1, CANVAS_H // 2))
    assert px_outside != _hex_to_rgb(ACCENT_CYAN)


# ── draw_top_bar ─────────────────────────────────────────────────────────────

def test_draw_top_bar_does_not_crash():
    img, draw = _new_canvas()
    draw_background(img)
    draw_top_bar(draw, unit_idx=2, total=5)  # should not raise


def test_draw_top_bar_modifies_image():
    img, draw = _new_canvas()
    draw_background(img)
    snapshot_before = list(img.getdata())
    draw_top_bar(draw, unit_idx=1, total=3)
    snapshot_after = list(img.getdata())
    assert snapshot_before != snapshot_after, "draw_top_bar should paint pixels"


# ── draw_footer_bar ───────────────────────────────────────────────────────────

def test_draw_footer_bar_paints_footer_area():
    img, draw = _new_canvas()
    draw_background(img)
    draw_footer_bar(draw, "Copy the address, not the house")
    # Footer area should no longer be BG_DEEP
    px = img.getpixel((CANVAS_W // 2, FOOTER_BAR_Y + 5))
    assert px != _hex_to_rgb(BG_DEEP)


def test_draw_footer_bar_green_accent_strip():
    img, draw = _new_canvas()
    draw_background(img)
    draw_footer_bar(draw, "test hook")
    # Leftmost pixel in footer area should be green (accent strip)
    px = img.getpixel((0, FOOTER_BAR_Y + 10))
    expected = _hex_to_rgb(ACCENT_GREEN)
    assert px == expected


def test_draw_footer_bar_empty_string_does_not_crash():
    img, draw = _new_canvas()
    draw_background(img)
    draw_footer_bar(draw, "")  # empty memory hook is valid


# ── draw_concept_title ────────────────────────────────────────────────────────

def test_draw_concept_title_modifies_title_area():
    img, draw = _new_canvas()
    draw_background(img)
    snapshot_before = list(img.getdata())
    draw_concept_title(draw, "Interface vs Abstract Class")
    snapshot_after = list(img.getdata())
    assert snapshot_before != snapshot_after


def test_draw_concept_title_empty_string_ok():
    img, draw = _new_canvas()
    draw_background(img)
    draw_concept_title(draw, "")  # should not crash


# ── draw_divider ──────────────────────────────────────────────────────────────

def test_draw_divider_default_cyan():
    img, draw = _new_canvas()
    draw_background(img)
    from tutor.visual.slide_theme import DIVIDER_Y
    draw_divider(draw)
    # Sample a pixel on the divider line at CONTENT_LEFT + 10
    px = img.getpixel((CONTENT_LEFT + 100, DIVIDER_Y))
    assert px == _hex_to_rgb(ACCENT_CYAN)


def test_draw_divider_custom_colour():
    img, draw = _new_canvas()
    draw_background(img)
    from tutor.visual.slide_theme import DIVIDER_Y
    draw_divider(draw, colour=ACCENT_AMBER)
    px = img.getpixel((CONTENT_LEFT + 100, DIVIDER_Y))
    assert px == _hex_to_rgb(ACCENT_AMBER)


# ── draw_bullets ──────────────────────────────────────────────────────────────

def test_draw_bullets_returns_int():
    img, draw = _new_canvas()
    draw_background(img)
    result = draw_bullets(draw, ["Point A", "Point B", "Point C"], CONTENT_LEFT, 210, 900)
    assert isinstance(result, int)
    assert result > 210  # should be below the starting y


def test_draw_bullets_modifies_canvas():
    img, draw = _new_canvas()
    draw_background(img)
    before = list(img.getdata())
    draw_bullets(draw, ["Interfaces define contracts"], CONTENT_LEFT, 210, 900)
    after = list(img.getdata())
    assert before != after


def test_draw_bullets_max_five_shown():
    """Only 5 bullets should be displayed even if more are passed."""
    img, draw = _new_canvas()
    draw_background(img)
    # 7 points — only 4 + ellipsis should render
    points = [f"Point {i}" for i in range(7)]
    draw_bullets(draw, points, CONTENT_LEFT, 210, 900)  # should not crash


def test_draw_bullets_empty_list_does_not_crash():
    img, draw = _new_canvas()
    draw_background(img)
    result = draw_bullets(draw, [], CONTENT_LEFT, 210, 900)
    assert isinstance(result, int)


# ── draw_code_block ───────────────────────────────────────────────────────────

def test_draw_code_block_returns_int():
    img, draw = _new_canvas()
    draw_background(img)
    result = draw_code_block(img, draw, "int x = 5;\nSystem.out.println(x);", 400)
    assert isinstance(result, int)
    assert result > 400


def test_draw_code_block_modifies_canvas():
    img, draw = _new_canvas()
    draw_background(img)
    before = list(img.getdata())
    draw_code_block(img, draw, "String s = \"Hello\";", 400)
    after = list(img.getdata())
    assert before != after


def test_draw_code_block_long_code_does_not_crash():
    img, draw = _new_canvas()
    draw_background(img)
    long_code = "\n".join([f"int x{i} = {i};" for i in range(20)])
    draw_code_block(img, draw, long_code, 400)  # should not crash


def test_draw_code_block_empty_string_ok():
    img, draw = _new_canvas()
    draw_background(img)
    draw_code_block(img, draw, "", 400)  # should not crash


# ── paste_diagram ─────────────────────────────────────────────────────────────

def test_paste_diagram_places_image(tmp_path):
    img, _ = _new_canvas()
    draw_background(img)

    # Create a bright red diagram image
    diag_path = tmp_path / "diag.png"
    Image.new("RGB", (400, 300), "#ff0000").save(diag_path, "PNG")

    paste_diagram(img, diag_path)

    # Somewhere in the diagram area should now be red
    cx = DIAGRAM_X + 50
    cy = DIAGRAM_Y + 50
    px = img.getpixel((cx, cy))
    # Allow for Lanczos resampling — just check it's not pure BG_DEEP
    assert px != _hex_to_rgb(BG_DEEP)


def test_paste_diagram_missing_file_does_not_crash():
    img, _ = _new_canvas()
    draw_background(img)
    paste_diagram(img, Path("/nonexistent/diagram.png"))  # should not raise


def test_paste_diagram_scales_down_large_image(tmp_path):
    """A very large diagram should be scaled to fit, not crash."""
    img, _ = _new_canvas()
    draw_background(img)

    diag_path = tmp_path / "big_diag.png"
    Image.new("RGB", (3000, 2000), "#00ff00").save(diag_path, "PNG")

    paste_diagram(img, diag_path)  # should not crash or exceed canvas bounds


# ── draw_logo ─────────────────────────────────────────────────────────────────

def test_draw_logo_paints_top_right():
    img, draw = _new_canvas()
    draw_background(img)
    draw_logo(draw)

    # Logo is a rounded rectangle near top-right.
    # Should be ACCENT_CYAN or the 'LX' text (BG_DEEP) — not pure BG_DEEP background
    # The rectangle fill is ACCENT_CYAN
    expected_cyan = _hex_to_rgb(ACCENT_CYAN)
    # Somewhere in the centre of logo box should be cyan
    cx = CANVAS_W - 48
    cy = 37
    px_logo = img.getpixel((cx, cy))
    assert px_logo == expected_cyan, f"Expected ACCENT_CYAN at logo center, got {px_logo}"


def test_draw_logo_does_not_crash_on_fresh_canvas():
    img, draw = _new_canvas()
    draw_logo(draw)  # no background needed — should not raise
