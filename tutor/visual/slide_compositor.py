"""
Public API for composing slides into 1920x1080 PNGs.
Delegates all drawing to slide_draw; reads constants from slide_theme.
"""

import logging
from pathlib import Path

from PIL import Image, ImageDraw

from tutor.models import VisualSpec
from tutor.visual.slide_draw import (
    draw_accent_strip,
    draw_bullets,
    draw_code_block,
    draw_concept_title,
    draw_divider,
    draw_footer_bar,
    draw_logo,
    draw_subtle_grid,
    draw_tag,
    draw_top_bar,
    paste_diagram,
)
from tutor.visual.slide_theme import (
    ACCENT_AMBER,
    ACCENT_CYAN,
    ACCENT_GREEN,
    BG_CARD,
    BG_DEEP,
    BG_PANEL,
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
    """Compose all slides. Returns ordered list of PNG paths."""
    output_dir.mkdir(parents=True, exist_ok=True)

    unit_specs = [v for v in visuals if v.slide_type == "unit"]
    total = len(unit_specs)
    paths: list[Path] = []

    title_spec = next((v for v in visuals if v.slide_type == "title_card"), None)
    if title_spec:
        paths.append(compose_title_card(title_spec, output_dir / "00_title.png"))

    for spec in unit_specs:
        i = spec.unit_index
        diag_png = diagram_pngs.get(i)
        paths.append(compose_hook_slide(spec, output_dir / f"{i:02d}_hook.png", total))
        paths.append(
            compose_concept_slide(spec, diag_png, output_dir / f"{i:02d}_concept.png", total)
        )
        paths.append(compose_memory_slide(spec, output_dir / f"{i:02d}_memory.png", total))

    outro_spec = next((v for v in visuals if v.slide_type == "outro"), None)
    if outro_spec:
        paths.append(compose_outro_card(outro_spec, output_dir / "99_outro.png", session_label))

    log.info("Composed %d slides into %s", len(paths), output_dir)
    return paths


def compose_title_card(spec: VisualSpec, output_path: Path) -> Path:
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), BG_DEEP)
    draw = ImageDraw.Draw(img)

    draw_subtle_grid(draw)
    draw_accent_strip(draw)

    cx = CANVAS_W // 2
    cy = CANVAS_H // 2

    # Large background glow circle for visual interest
    for r, alpha in [(340, "#0d2030"), (260, "#0e2535"), (180, "#0f2a3a")]:
        draw.ellipse([cx - r, cy - r - 60, cx + r, cy + r - 60], fill=alpha)

    # LX logo block
    lx_size = 130
    lx_x0 = cx - lx_size // 2
    lx_y0 = cy - 220
    draw.rounded_rectangle(
        [lx_x0, lx_y0, lx_x0 + lx_size, lx_y0 + lx_size], radius=20, fill=ACCENT_CYAN
    )
    font_lx = _load_font(60, bold=True)
    draw.text((lx_x0 + 22, lx_y0 + 22), "LX", font=font_lx, fill=BG_DEEP)

    # Document title
    font_title = _load_font(76, bold=True)
    title_text = spec.title or "LearnX Tutorial"
    title_lines = wrap_text(draw, title_text, font_title, 1400)
    y = cy - 60
    for line in title_lines[:2]:
        bbox = draw.textbbox((0, 0), line, font=font_title)
        x = cx - (bbox[2] - bbox[0]) // 2
        draw.text((x, y), line, font=font_title, fill=TEXT_PRIMARY)
        y += 88

    # Divider
    div_y = cy + 60
    draw.line([(cx - 320, div_y), (cx + 320, div_y)], fill=ACCENT_CYAN, width=3)

    # Subtitle badge
    font_sub = _load_font(30)
    bbox = draw.textbbox((0, 0), spec.subtitle, font=font_sub)
    x = cx - (bbox[2] - bbox[0]) // 2
    draw.text((x, div_y + 20), spec.subtitle, font=font_sub, fill=TEXT_SECONDARY)

    # Bottom metadata
    font_meta = _load_font(22)
    draw.text(
        (CONTENT_LEFT, FOOTER_BAR_Y + 28),
        spec.doc_source or "",
        font=font_meta,
        fill=TEXT_SECONDARY,
    )
    lx_label = "LearnX v2"
    bbox = draw.textbbox((0, 0), lx_label, font=font_meta)
    draw.text(
        (CONTENT_RIGHT - (bbox[2] - bbox[0]), FOOTER_BAR_Y + 28),
        lx_label,
        font=font_meta,
        fill=TEXT_SECONDARY,
    )

    img.save(output_path, "PNG")
    return output_path


def compose_hook_slide(spec: VisualSpec, output_path: Path, total: int) -> Path:
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), BG_DEEP)
    draw = ImageDraw.Draw(img)

    draw_subtle_grid(draw)
    draw_accent_strip(draw)
    draw_top_bar(draw, spec.unit_index, total)
    draw_logo(draw)

    # Large decorative "?" in background
    font_deco = _load_font(280, bold=True)
    draw.text((1580, 60), "?", font=font_deco, fill="#152030")

    draw_concept_title(draw, spec.concept)
    draw_divider(draw)

    # Hook question panel
    panel_y0 = BODY_Y + 10
    panel_x1 = CONTENT_RIGHT - 80
    draw.rounded_rectangle(
        [CONTENT_LEFT - 16, panel_y0 - 20, panel_x1, panel_y0 + 280], radius=12, fill=BG_PANEL
    )
    draw.rectangle(
        [CONTENT_LEFT - 16, panel_y0 - 20, CONTENT_LEFT - 6, panel_y0 + 280], fill=ACCENT_AMBER
    )

    # Open-quote decoration (two vertical bars — reliable in all system fonts)
    font_q = _load_font(80, bold=True)
    font_hook = _load_font(46)
    draw.text((CONTENT_LEFT + 8, panel_y0 - 16), "//", font=font_q, fill=ACCENT_CYAN)

    lines = wrap_text(draw, spec.hook_question, font_hook, CONTENT_WIDTH - 120)
    q_y = panel_y0 + 50
    for line in lines[:3]:
        draw.text((CONTENT_LEFT + 80, q_y), line, font=font_hook, fill=ACCENT_AMBER)
        q_y += 60

    # "What you'll learn" preview below hook panel
    if spec.key_points:
        learn_y = panel_y0 + 310
        font_lbl = _load_font(22, bold=True)
        font_pt = _load_font(30)
        draw.text((CONTENT_LEFT, learn_y), "WHAT YOU'LL LEARN", font=font_lbl, fill=TEXT_SECONDARY)
        learn_y += 34
        for pt in spec.key_points[:3]:
            pt_lines = wrap_text(draw, pt, font_pt, CONTENT_WIDTH - 80)
            draw.text(
                (CONTENT_LEFT + 4, learn_y), f"+ {pt_lines[0]}", font=font_pt, fill=TEXT_PRIMARY
            )
            learn_y += 42
            if learn_y > FOOTER_BAR_Y - 60:
                break

    # UNIT tag
    draw_tag(draw, f"Unit {spec.unit_index}", CONTENT_LEFT, FOOTER_BAR_Y - 46, ACCENT_CYAN)

    draw_footer_bar(draw, spec.memory_hook)
    img.save(output_path, "PNG")
    return output_path


def compose_concept_slide(
    spec: VisualSpec,
    diagram_png: Path | None,
    output_path: Path,
    total: int,
) -> Path:
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), BG_DEEP)
    draw = ImageDraw.Draw(img)

    draw_subtle_grid(draw)
    draw_accent_strip(draw)
    draw_top_bar(draw, spec.unit_index, total)
    draw_logo(draw)
    draw_concept_title(draw, spec.concept)
    draw_divider(draw)

    has_diagram = diagram_png is not None and diagram_png.exists()
    bullet_w = BULLET_AREA_W if has_diagram else BULLET_AREA_W_FULL

    after_bullets = draw_bullets(draw, spec.key_points, CONTENT_LEFT, BODY_Y, bullet_w)

    if spec.code_snippet:
        draw_code_block(img, draw, spec.code_snippet, after_bullets + 20)

    if has_diagram:
        paste_diagram(img, diagram_png)

    draw_footer_bar(draw, spec.memory_hook)
    img.save(output_path, "PNG")
    return output_path


def compose_memory_slide(spec: VisualSpec, output_path: Path, total: int) -> Path:
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), BG_DEEP)
    draw = ImageDraw.Draw(img)

    draw_subtle_grid(draw)
    draw_accent_strip(draw, colour=ACCENT_AMBER)
    draw_logo(draw)

    # Top bar
    font_bar = _load_font(24)
    draw.text(
        (CONTENT_LEFT, 22),
        f"UNIT {spec.unit_index} / {total}  -  REMEMBER THIS",
        font=font_bar,
        fill=TEXT_SECONDARY,
    )

    # Decorative checkmark background
    font_deco = _load_font(260, bold=True)
    draw.text((1560, 60), "V", font=font_deco, fill="#14200f")

    draw_concept_title(draw, spec.concept)
    draw_divider(draw, colour=ACCENT_AMBER)

    # Memory hook card
    hook_card_y = DIVIDER_Y + 40
    hook_card_h = 200
    cx = CANVAS_W // 2
    draw.rounded_rectangle(
        [CONTENT_LEFT - 16, hook_card_y, CONTENT_RIGHT + 16, hook_card_y + hook_card_h],
        radius=12,
        fill=BG_PANEL,
    )
    draw.rectangle(
        [CONTENT_LEFT - 16, hook_card_y, CONTENT_LEFT - 4, hook_card_y + hook_card_h],
        fill=ACCENT_AMBER,
    )

    font_hook = _load_font(50, bold=True)
    lines = wrap_text(draw, spec.memory_hook, font_hook, CONTENT_WIDTH - 60)
    mem_y = hook_card_y + (hook_card_h - len(lines[:2]) * 62) // 2
    for line in lines[:2]:
        bbox = draw.textbbox((0, 0), line, font=font_hook)
        x = cx - (bbox[2] - bbox[0]) // 2
        draw.text((x, mem_y), line, font=font_hook, fill=ACCENT_AMBER)
        mem_y += 62

    # Summary bullets below hook card
    if spec.key_points:
        font_sum = _load_font(30)
        sum_y = hook_card_y + hook_card_h + 30
        for point in spec.key_points[:3]:
            if sum_y + 40 >= FOOTER_BAR_Y - 20:
                break
            bbox = draw.textbbox((0, 0), f"  {point}", font=font_sum)
            x = cx - (bbox[2] - bbox[0]) // 2
            draw.text((x, sum_y), f"- {point}", font=font_sum, fill=TEXT_SECONDARY)
            sum_y += 44

    # Footer
    draw.rectangle([0, FOOTER_BAR_Y, CANVAS_W, CANVAS_H], fill=BG_CARD)
    draw.rectangle([0, FOOTER_BAR_Y, 10 + 2, CANVAS_H], fill=ACCENT_AMBER)
    font_pin = _load_font(22, bold=True)
    font_anal = _load_font(26)
    text_y = FOOTER_BAR_Y + 26
    draw.text((CONTENT_LEFT, text_y), "[ PIN THIS ]", font=font_pin, fill=ACCENT_GREEN)
    if spec.analogy:
        analogy_lines = wrap_text(draw, spec.analogy, font_anal, 780)
        draw.text(
            (CONTENT_RIGHT - 800, text_y),
            analogy_lines[0] if analogy_lines else "",
            font=font_anal,
            fill=TEXT_SECONDARY,
        )

    img.save(output_path, "PNG")
    return output_path


def compose_outro_card(spec: VisualSpec, output_path: Path, session_label: str) -> Path:
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), BG_DEEP)
    draw = ImageDraw.Draw(img)

    draw_subtle_grid(draw)
    draw_accent_strip(draw)

    cx = CANVAS_W // 2

    # Background glow
    for r, col in [(300, "#0d2030"), (200, "#0e2535")]:
        draw.ellipse([cx - r, 300 - r, cx + r, 300 + r], fill=col)

    # "Session Complete"
    font_title = _load_font(72, bold=True)
    title_text = "Session Complete"
    bbox = draw.textbbox((0, 0), title_text, font=font_title)
    draw.text((cx - (bbox[2] - bbox[0]) // 2, 180), title_text, font=font_title, fill=TEXT_PRIMARY)

    # Divider
    draw.line([(cx - 240, 278), (cx + 240, 278)], fill=ACCENT_CYAN, width=3)

    # Stats
    font_stats = _load_font(30)
    bbox = draw.textbbox((0, 0), spec.session_stats, font=font_stats)
    draw.text(
        (cx - (bbox[2] - bbox[0]) // 2, 298),
        spec.session_stats,
        font=font_stats,
        fill=TEXT_SECONDARY,
    )

    # "What to remember" header
    font_hdr = _load_font(28, bold=True)
    hdr_text = "What to remember:"
    bbox = draw.textbbox((0, 0), hdr_text, font=font_hdr)
    draw.text((cx - (bbox[2] - bbox[0]) // 2, 360), hdr_text, font=font_hdr, fill=ACCENT_GREEN)

    # Memory hooks
    font_hook = _load_font(32)
    hook_y = 410
    for hook in spec.memory_hooks[:5]:
        if hook_y + 50 > 880:
            break
        text = f"- {hook}"
        bbox = draw.textbbox((0, 0), text, font=font_hook)
        draw.text((cx - (bbox[2] - bbox[0]) // 2, hook_y), text, font=font_hook, fill=ACCENT_AMBER)
        hook_y += 54

    # Bottom wordmark
    font_wm = _load_font(30, bold=True)
    font_pth = _load_font(20)
    lx_text = "LearnX"
    bbox = draw.textbbox((0, 0), lx_text, font=font_wm)
    draw.text((cx - (bbox[2] - bbox[0]) // 2, 920), lx_text, font=font_wm, fill=ACCENT_CYAN)

    path_text = f"video/{session_label}/"
    bbox = draw.textbbox((0, 0), path_text, font=font_pth)
    draw.text((cx - (bbox[2] - bbox[0]) // 2, 960), path_text, font=font_pth, fill=TEXT_SECONDARY)

    img.save(output_path, "PNG")
    return output_path
