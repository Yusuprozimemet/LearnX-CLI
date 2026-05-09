"""
Primitive drawing functions for slide rendering.
Each function receives a draw/img and modifies it in place.
No VisualSpec logic here — only layout primitives.
"""
from pathlib import Path

from PIL import Image, ImageDraw

from tutor.visual.slide_theme import (
    ACCENT_AMBER,
    ACCENT_CYAN,
    ACCENT_GREEN,
    ACCENT_STRIP_W,
    BG_CARD,
    BG_DEEP,
    BG_PANEL,
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
    MARGIN,
    TEXT_CODE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TITLE_Y,
    _load_font,
    wrap_text,
)

# Left gutter for bullet dot
_BULLET_DOT_X  = CONTENT_LEFT
_BULLET_TEXT_X = CONTENT_LEFT + 44


def draw_background(img: Image.Image, colour: str = BG_DEEP) -> None:
    img.paste(Image.new("RGB", (CANVAS_W, CANVAS_H), colour))


def draw_accent_strip(draw: ImageDraw.ImageDraw, colour: str = ACCENT_CYAN) -> None:
    draw.rectangle([0, 0, ACCENT_STRIP_W - 1, CANVAS_H], fill=colour)


def draw_subtle_grid(draw: ImageDraw.ImageDraw) -> None:
    """Faint dot-grid background for visual depth."""
    for x in range(0, CANVAS_W, 60):
        for y in range(0, CANVAS_H, 60):
            draw.ellipse([x - 1, y - 1, x + 1, y + 1], fill="#1a2030")


def draw_top_bar(draw: ImageDraw.ImageDraw, unit_idx: int, total: int) -> None:
    font  = _load_font(24)
    label = f"UNIT {unit_idx} / {total}"
    draw.text((CONTENT_LEFT, 22), label, font=font, fill=TEXT_SECONDARY)


def draw_footer_bar(draw: ImageDraw.ImageDraw, memory_hook: str) -> None:
    draw.rectangle([0, FOOTER_BAR_Y, CANVAS_W, CANVAS_H], fill=BG_CARD)
    # Green left accent bar
    draw.rectangle([0, FOOTER_BAR_Y, ACCENT_STRIP_W + 2, CANVAS_H], fill=ACCENT_GREEN)

    font_icon = _load_font(22, bold=True)
    font_hook = _load_font(36, bold=True)
    text_y    = FOOTER_BAR_Y + (FOOTER_BAR_H - 36) // 2

    draw.text((_BULLET_DOT_X + 16, text_y + 2), ">", font=font_icon, fill=ACCENT_GREEN)
    draw.text((_BULLET_TEXT_X + 4, text_y), memory_hook, font=font_hook, fill=TEXT_PRIMARY)


def draw_concept_title(draw: ImageDraw.ImageDraw, text: str) -> None:
    font  = _load_font(62, bold=True)
    lines = wrap_text(draw, text, font, CONTENT_WIDTH - 60)
    y = TITLE_Y
    for line in lines[:2]:
        draw.text((CONTENT_LEFT, y), line, font=font, fill=TEXT_PRIMARY)
        y += 72


def draw_divider(draw: ImageDraw.ImageDraw, colour: str = ACCENT_CYAN) -> None:
    draw.line(
        [(CONTENT_LEFT, DIVIDER_Y), (CONTENT_RIGHT, DIVIDER_Y)],
        fill=colour,
        width=2,
    )


def draw_bullets(
    draw: ImageDraw.ImageDraw,
    points: list[str],
    x: int,
    y: int,
    max_w: int,
) -> int:
    """Draw bullet points on a subtle panel card. Returns y after last bullet."""
    if not points:
        return y

    font      = _load_font(38)
    font_dot  = _load_font(38, bold=True)
    shown     = points[:5]

    # Measure total height for background panel
    line_h    = 50
    pad       = 24
    est_h     = len(shown) * (line_h + 10) + pad * 2
    panel_x1  = x - 16
    panel_y1  = y - pad
    panel_x2  = x + max_w + 16
    panel_y2  = y + est_h

    draw.rounded_rectangle(
        [panel_x1, panel_y1, panel_x2, panel_y2],
        radius=10, fill=BG_PANEL,
    )
    # Left cyan accent bar on panel
    draw.rectangle([panel_x1, panel_y1, panel_x1 + 4, panel_y2], fill=ACCENT_CYAN)

    cur_y = y
    for point in shown:
        draw.text((x + 4, cur_y + 4), "->", font=font_dot, fill=ACCENT_CYAN)
        lines = wrap_text(draw, point, font, max_w - 50)
        for line in lines:
            draw.text((x + 50, cur_y), line, font=font, fill=TEXT_PRIMARY)
            cur_y += line_h
        cur_y += 10

    return cur_y


def draw_code_block(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    code: str,
    y_start: int,
) -> int:
    """Draw rounded code block. Returns y position after block."""
    lines    = code.split("\n")[:6]
    pad      = 20
    line_h   = 34
    header_h = 32
    block_h  = min(header_h + pad + len(lines) * line_h + pad, 220)

    x0, y0 = CONTENT_LEFT, y_start
    x1, y1 = CONTENT_LEFT + 880, y0 + block_h

    draw.rounded_rectangle([x0, y0, x1, y1], radius=8, fill=BG_CARD, outline=DIVIDER, width=1)
    draw.rectangle([x0, y0, x0 + 4, y1], fill=ACCENT_CYAN)

    font_hdr  = _load_font(20, mono=True)
    font_code = _load_font(28, mono=True)

    draw.text((x1 - 70, y0 + 6), "Java", font=font_hdr, fill=TEXT_SECONDARY)

    code_y = y0 + header_h + pad // 2
    for line in lines:
        if code_y + line_h > y1 - 8:
            break
        draw.text((x0 + 20, code_y), line, font=font_code, fill=TEXT_CODE)
        code_y += line_h

    return y1 + 20


def paste_diagram(img: Image.Image, diagram_path: Path) -> None:
    """Paste diagram PNG at DIAGRAM_X/DIAGRAM_Y, scaled to fill (upscale allowed)."""
    try:
        diag = Image.open(diagram_path).convert("RGB")
    except (OSError, IOError):
        return

    dw, dh = diag.size
    # Allow upscaling small diagrams to fill the area
    scale  = min(DIAGRAM_W / dw, DIAGRAM_H / dh)
    new_w  = max(1, int(dw * scale))
    new_h  = max(1, int(dh * scale))

    diag = diag.resize((new_w, new_h), Image.LANCZOS)

    # Draw a panel behind the diagram
    pad = 24
    panel_x0 = DIAGRAM_X - pad
    panel_y0 = DIAGRAM_Y - pad
    panel_x1 = DIAGRAM_X + DIAGRAM_W + pad
    panel_y1 = DIAGRAM_Y + DIAGRAM_H + pad
    img_draw = ImageDraw.Draw(img)
    img_draw.rounded_rectangle(
        [panel_x0, panel_y0, panel_x1, panel_y1], radius=12, fill=BG_PANEL
    )

    offset_x = DIAGRAM_X + (DIAGRAM_W - new_w) // 2
    offset_y = DIAGRAM_Y + (DIAGRAM_H - new_h) // 2
    img.paste(diag, (offset_x, offset_y))


def draw_logo(draw: ImageDraw.ImageDraw) -> None:
    """Draw 'LX' pill at top-right corner."""
    x0, y0 = CANVAS_W - 90, 14
    x1, y1 = CANVAS_W - 14, 56
    draw.rounded_rectangle([x0, y0, x1, y1], radius=8, fill=ACCENT_CYAN)
    font = _load_font(24, bold=True)
    draw.text((x0 + 10, y0 + 6), "LX", font=font, fill=BG_DEEP)


def draw_tag(draw: ImageDraw.ImageDraw, text: str, x: int, y: int, colour: str) -> None:
    """Draw a small coloured pill tag."""
    font = _load_font(20, bold=True)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw   = bbox[2] - bbox[0]
    pad  = 12
    draw.rounded_rectangle(
        [x, y, x + tw + pad * 2, y + 30], radius=6, fill=colour
    )
    draw.text((x + pad, y + 5), text, font=font, fill=BG_DEEP)
