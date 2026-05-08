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


def draw_background(img: Image.Image, colour: str = BG_DEEP) -> None:
    img.paste(Image.new("RGB", (CANVAS_W, CANVAS_H), colour))


def draw_accent_strip(
    draw: ImageDraw.ImageDraw, colour: str = ACCENT_CYAN
) -> None:
    draw.rectangle([0, 0, ACCENT_STRIP_W - 1, CANVAS_H], fill=colour)


def draw_top_bar(
    draw: ImageDraw.ImageDraw, unit_idx: int, total: int
) -> None:
    font = _load_font(26)
    label = f"UNIT {unit_idx} / {total}"
    draw.text((CONTENT_LEFT, 20), label, font=font, fill=TEXT_SECONDARY)


def draw_footer_bar(draw: ImageDraw.ImageDraw, memory_hook: str) -> None:
    draw.rectangle(
        [0, FOOTER_BAR_Y, CANVAS_W, CANVAS_H], fill=BG_CARD
    )
    draw.rectangle(
        [0, FOOTER_BAR_Y, 4, CANVAS_H], fill=ACCENT_GREEN
    )
    font_bullet = _load_font(20)
    font_hook   = _load_font(38, bold=True)
    bullet_x = CONTENT_LEFT
    text_y   = FOOTER_BAR_Y + (FOOTER_BAR_H - 38) // 2
    draw.text((bullet_x, text_y), "⬡ ", font=font_bullet, fill=ACCENT_GREEN)
    draw.text((bullet_x + 36, text_y), memory_hook, font=font_hook, fill=TEXT_PRIMARY)


def draw_concept_title(draw: ImageDraw.ImageDraw, text: str) -> None:
    font = _load_font(64, bold=True)
    draw.text((CONTENT_LEFT, TITLE_Y), text, font=font, fill=TEXT_PRIMARY)


def draw_divider(
    draw: ImageDraw.ImageDraw, colour: str = ACCENT_CYAN
) -> None:
    draw.line(
        [(CONTENT_LEFT, DIVIDER_Y), (CONTENT_RIGHT, DIVIDER_Y)],
        fill=colour,
        width=1,
    )


def draw_bullets(
    draw: ImageDraw.ImageDraw,
    points: list[str],
    x: int,
    y: int,
    max_w: int,
) -> int:
    """Draw bullet points. Returns y position after last bullet."""
    font   = _load_font(38)
    bullet = _load_font(38, bold=True)
    shown  = points[:5]
    if len(points) > 5:
        shown = points[:4] + ["…"]

    cur_y = y
    for point in shown:
        draw.text((x, cur_y), "•", font=bullet, fill=ACCENT_CYAN)
        lines = wrap_text(draw, point, font, max_w - 36)
        for line in lines:
            draw.text((x + 36, cur_y), line, font=font, fill=TEXT_PRIMARY)
            cur_y += 48
        cur_y += 52 - 48   # BULLET_LEAD minus one line height already advanced

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
    line_h   = 32
    header_h = 28
    block_h  = header_h + pad + len(lines) * line_h + pad
    block_h  = min(block_h, 200)

    x0, y0 = CONTENT_LEFT, y_start
    x1      = CONTENT_LEFT + 900
    y1      = y0 + block_h

    draw.rounded_rectangle([x0, y0, x1, y1], radius=8, fill=BG_CARD, outline=DIVIDER)
    draw.rectangle([x0, y0, x0 + 4, y1], fill=ACCENT_CYAN)

    font_hdr  = _load_font(22, mono=True)
    font_code = _load_font(26, mono=True)

    draw.text((x1 - 60, y0 + 4), "Java", font=font_hdr, fill=TEXT_SECONDARY)

    code_y = y0 + header_h + pad
    for line in lines:
        if code_y + line_h > y1 - pad:
            break
        draw.text((x0 + 24, code_y), line, font=font_code, fill=TEXT_CODE)
        code_y += line_h

    return y1 + 16


def paste_diagram(img: Image.Image, diagram_path: Path) -> None:
    """Paste diagram PNG at DIAGRAM_X/DIAGRAM_Y, scaled to fit, preserving aspect ratio."""
    try:
        diag = Image.open(diagram_path).convert("RGB")
    except (OSError, IOError):
        return

    dw, dh = diag.size
    scale   = min(DIAGRAM_W / dw, DIAGRAM_H / dh, 1.0)
    new_w   = int(dw * scale)
    new_h   = int(dh * scale)

    diag = diag.resize((new_w, new_h), Image.LANCZOS)

    offset_x = DIAGRAM_X + (DIAGRAM_W - new_w) // 2
    offset_y = DIAGRAM_Y + (DIAGRAM_H - new_h) // 2

    img.paste(diag, (offset_x, offset_y))


def draw_logo(draw: ImageDraw.ImageDraw) -> None:
    """Draw 'LX' rounded rectangle at top-right corner."""
    x0, y0 = CANVAS_W - 80, 16
    x1, y1 = CANVAS_W - 16, 58
    draw.rounded_rectangle([x0, y0, x1, y1], radius=6, fill=ACCENT_CYAN)
    font = _load_font(22, bold=True)
    draw.text((x0 + 8, y0 + 5), "LX", font=font, fill=BG_DEEP)
