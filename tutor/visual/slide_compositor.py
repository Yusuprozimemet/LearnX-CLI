"""
Public API for composing slides into 1920×1080 PNGs.
Delegates all drawing to slide_draw; reads constants from slide_theme.
"""
import logging
from pathlib import Path

from PIL import Image, ImageDraw

from tutor.models import VisualSpec
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
    BG_CARD,
    BODY_Y,
    BULLET_AREA_W,
    BULLET_AREA_W_FULL,
    CANVAS_H,
    CANVAS_W,
    CONTENT_LEFT,
    CONTENT_RIGHT,
    CONTENT_WIDTH,
    DIVIDER_Y,
    FOOTER_BAR_Y,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TITLE_Y,
    _load_font,
    wrap_text,
)

log = logging.getLogger(__name__)


def compose_all(
    visuals: list[VisualSpec],
    diagram_pngs: dict[int, Path],
    output_dir: Path,
    session_label: str,
) -> list[Path]:
    """
    Compose all slides. Returns ordered list of PNG paths.
    Order: title, [hook, concept, memory] × N units, outro.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    unit_specs = [v for v in visuals if v.slide_type == "unit"]
    total = len(unit_specs)

    paths: list[Path] = []

    title_spec = next((v for v in visuals if v.slide_type == "title_card"), None)
    if title_spec:
        p = compose_title_card(title_spec, output_dir / "00_title.png")
        paths.append(p)

    for spec in unit_specs:
        i = spec.unit_index
        diag_png = diagram_pngs.get(i)

        p = compose_hook_slide(spec, output_dir / f"{i:02d}_hook.png", total)
        paths.append(p)

        p = compose_concept_slide(
            spec, diag_png, output_dir / f"{i:02d}_concept.png", total
        )
        paths.append(p)

        p = compose_memory_slide(spec, output_dir / f"{i:02d}_memory.png", total)
        paths.append(p)

    outro_spec = next((v for v in visuals if v.slide_type == "outro"), None)
    if outro_spec:
        p = compose_outro_card(outro_spec, output_dir / "99_outro.png", session_label)
        paths.append(p)

    log.info("Composed %d slides into %s", len(paths), output_dir)
    return paths


def compose_title_card(spec: VisualSpec, output_path: Path) -> Path:
    img  = Image.new("RGB", (CANVAS_W, CANVAS_H), "#0d1117")
    draw = ImageDraw.Draw(img)

    draw_background(img)
    draw_accent_strip(draw)

    cx = CANVAS_W // 2
    cy = CANVAS_H // 2

    # Logo block centred above title
    lx0, ly0 = cx - 60, cy - 190
    lx1, ly1 = cx + 60, cy - 70
    draw.rounded_rectangle([lx0, ly0, lx1, ly1], radius=12, fill=ACCENT_CYAN)
    font_lx = _load_font(52, bold=True)
    draw.text((lx0 + 14, ly0 + 8), "LX", font=font_lx, fill="#0d1117")

    # Document title
    font_title = _load_font(80, bold=True)
    title_lines = wrap_text(draw, spec.title, font_title, CONTENT_WIDTH)
    y = cy - 30
    for line in title_lines[:2]:
        bbox = draw.textbbox((0, 0), line, font=font_title)
        x = cx - (bbox[2] - bbox[0]) // 2
        draw.text((x, y), line, font=font_title, fill=TEXT_PRIMARY)
        y += 90

    # Thin divider
    draw.line([(cx - 300, cy + 30), (cx + 300, cy + 30)], fill=ACCENT_CYAN, width=2)

    # Subtitle
    font_sub = _load_font(32)
    bbox = draw.textbbox((0, 0), spec.subtitle, font=font_sub)
    x = cx - (bbox[2] - bbox[0]) // 2
    draw.text((x, cy + 60), spec.subtitle, font=font_sub, fill=TEXT_SECONDARY)

    # Bottom labels
    font_footer = _load_font(22)
    draw.text((CONTENT_LEFT, FOOTER_BAR_Y + 28), spec.doc_source, font=font_footer, fill=TEXT_SECONDARY)
    lx_w = draw.textbbox((0, 0), "LearnX v2", font=font_footer)[2]
    draw.text((CONTENT_RIGHT - lx_w, FOOTER_BAR_Y + 28), "LearnX v2", font=font_footer, fill=TEXT_SECONDARY)

    img.save(output_path, "PNG")
    return output_path


def compose_hook_slide(
    spec: VisualSpec, output_path: Path, total: int
) -> Path:
    img  = Image.new("RGB", (CANVAS_W, CANVAS_H))
    draw = ImageDraw.Draw(img)

    draw_background(img)
    draw_accent_strip(draw)
    draw_top_bar(draw, spec.unit_index, total)
    draw_logo(draw)
    draw_concept_title(draw, spec.concept)
    draw_divider(draw)

    # Decorative "?" glyph
    font_deco = _load_font(200, bold=True)
    draw.text((1700, 150), "?", font=font_deco, fill=ACCENT_AMBER)

    # Hook question with open-quote prefix
    font_quote = _load_font(56, bold=True)
    font_hook  = _load_font(44)
    draw.text((CONTENT_LEFT - 10, BODY_Y - 10), "“", font=font_quote, fill=ACCENT_CYAN)
    lines = wrap_text(draw, spec.hook_question, font_hook, CONTENT_WIDTH - 60)
    q_y = BODY_Y + 50
    for line in lines[:4]:
        draw.text((CONTENT_LEFT + 60, q_y), line, font=font_hook, fill=ACCENT_AMBER)
        q_y += 56

    draw_footer_bar(draw, spec.memory_hook)

    img.save(output_path, "PNG")
    return output_path


def compose_concept_slide(
    spec: VisualSpec,
    diagram_png: Path | None,
    output_path: Path,
    total: int,
) -> Path:
    img  = Image.new("RGB", (CANVAS_W, CANVAS_H))
    draw = ImageDraw.Draw(img)

    draw_background(img)
    draw_accent_strip(draw)
    draw_top_bar(draw, spec.unit_index, total)
    draw_logo(draw)
    draw_concept_title(draw, spec.concept)
    draw_divider(draw)

    has_diagram = diagram_png is not None and diagram_png.exists()
    bullet_w    = BULLET_AREA_W if has_diagram else BULLET_AREA_W_FULL

    after_bullets = draw_bullets(
        draw, spec.key_points, CONTENT_LEFT, BODY_Y, bullet_w
    )

    if spec.code_snippet:
        draw_code_block(img, draw, spec.code_snippet, after_bullets + 16)

    if has_diagram:
        paste_diagram(img, diagram_png)

    draw_footer_bar(draw, spec.memory_hook)

    img.save(output_path, "PNG")
    return output_path


def compose_memory_slide(
    spec: VisualSpec, output_path: Path, total: int
) -> Path:
    img  = Image.new("RGB", (CANVAS_W, CANVAS_H))
    draw = ImageDraw.Draw(img)

    draw_background(img)
    draw_accent_strip(draw, colour=ACCENT_AMBER)
    draw_logo(draw)

    # Top bar
    font_bar = _load_font(26)
    label = f"UNIT {spec.unit_index} / {total} — REMEMBER THIS"
    draw.text((CONTENT_LEFT, 20), label, font=font_bar, fill=TEXT_SECONDARY)

    # Decorative checkmark
    font_deco = _load_font(160, bold=True)
    draw.text((1700, 100), "✓", font=font_deco, fill=ACCENT_GREEN)

    draw_concept_title(draw, spec.concept)
    draw_divider(draw, colour=ACCENT_AMBER)

    # Memory hook text centred vertically
    font_hook  = _load_font(52, bold=True)
    font_quote = _load_font(64, bold=True)
    hook_y     = (DIVIDER_Y + FOOTER_BAR_Y) // 2 - 50

    draw.text((CONTENT_LEFT - 10, hook_y - 20), "“", font=font_quote, fill=ACCENT_CYAN)
    lines = wrap_text(draw, spec.memory_hook, font_hook, CONTENT_WIDTH - 60)
    for line in lines[:2]:
        bbox = draw.textbbox((0, 0), line, font=font_hook)
        cx = (CONTENT_LEFT + CONTENT_RIGHT) // 2
        x  = cx - (bbox[2] - bbox[0]) // 2
        draw.text((x, hook_y), line, font=font_hook, fill=ACCENT_AMBER)
        hook_y += 70

    # Summary bullets
    if spec.key_points:
        font_sum = _load_font(30)
        sum_y = hook_y + 30
        for point in spec.key_points[:3]:
            if sum_y + 40 >= FOOTER_BAR_Y - 20:
                break
            draw.text((CONTENT_LEFT, sum_y), f"• {point}", font=font_sum, fill=TEXT_SECONDARY)
            sum_y += 40

    # Footer bar with analogy
    draw.rectangle([0, FOOTER_BAR_Y, CANVAS_W, CANVAS_H], fill=BG_CARD)
    draw.rectangle([0, FOOTER_BAR_Y, 4, CANVAS_H], fill=ACCENT_GREEN)
    font_pin   = _load_font(22)
    font_anal  = _load_font(26)
    draw.text((CONTENT_LEFT, FOOTER_BAR_Y + 28), "\U0001f4cc Pin this", font=font_pin, fill=ACCENT_GREEN)
    if spec.analogy:
        analogy_lines = wrap_text(draw, spec.analogy, font_anal, 700)
        draw.text((CONTENT_RIGHT - 720, FOOTER_BAR_Y + 28), analogy_lines[0] if analogy_lines else "", font=font_anal, fill=TEXT_SECONDARY)

    img.save(output_path, "PNG")
    return output_path


def compose_outro_card(
    spec: VisualSpec, output_path: Path, session_label: str
) -> Path:
    img  = Image.new("RGB", (CANVAS_W, CANVAS_H))
    draw = ImageDraw.Draw(img)

    draw_background(img)
    draw_accent_strip(draw)

    cx = CANVAS_W // 2

    # "Session Complete"
    font_title = _load_font(72, bold=True)
    bbox = draw.textbbox((0, 0), "Session Complete", font=font_title)
    draw.text((cx - (bbox[2] - bbox[0]) // 2, 220), "Session Complete", font=font_title, fill=TEXT_PRIMARY)

    draw.line([(cx - 200, 316), (cx + 200, 316)], fill=ACCENT_CYAN, width=2)

    font_stats = _load_font(30)
    bbox = draw.textbbox((0, 0), spec.session_stats, font=font_stats)
    draw.text((cx - (bbox[2] - bbox[0]) // 2, 340), spec.session_stats, font=font_stats, fill=TEXT_SECONDARY)

    # Memory hooks
    font_hdr  = _load_font(28, bold=True)
    font_hook = _load_font(34)
    hdr = "What to remember:"
    bbox = draw.textbbox((0, 0), hdr, font=font_hdr)
    draw.text((cx - (bbox[2] - bbox[0]) // 2, 420), hdr, font=font_hdr, fill=ACCENT_GREEN)

    hook_y = 480
    for hook in spec.memory_hooks[:5]:
        if hook_y + 56 > 900:
            break
        text = f"— {hook}"
        bbox = draw.textbbox((0, 0), text, font=font_hook)
        draw.text((cx - (bbox[2] - bbox[0]) // 2, hook_y), text, font=font_hook, fill=ACCENT_AMBER)
        hook_y += 56

    # Bottom wordmark
    font_wm  = _load_font(28)
    font_pth = _load_font(20)
    lx_text  = "LearnX"
    bbox = draw.textbbox((0, 0), lx_text, font=font_wm)
    draw.text((cx - (bbox[2] - bbox[0]) // 2, 930), lx_text, font=font_wm, fill=TEXT_SECONDARY)

    path_text = f"video/{session_label}/"
    bbox = draw.textbbox((0, 0), path_text, font=font_pth)
    draw.text((cx - (bbox[2] - bbox[0]) // 2, 960), path_text, font=font_pth, fill=TEXT_SECONDARY)

    img.save(output_path, "PNG")
    return output_path
