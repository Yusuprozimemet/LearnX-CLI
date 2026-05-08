"""
Colour palette, spacing constants, and font loading for the slide compositor.
No Pillow Image/Draw objects are created here.
"""
from pathlib import Path

from PIL import ImageDraw, ImageFont

# ── Colour palette ─────────────────────────────────────────────────────────
BG_DEEP         = "#0d1117"
BG_CARD         = "#161b22"
BG_ACCENT_STRIP = "#00b4d8"
TEXT_PRIMARY    = "#e6edf3"
TEXT_SECONDARY  = "#8b949e"
TEXT_CODE       = "#79c0ff"
ACCENT_CYAN     = "#00b4d8"
ACCENT_GREEN    = "#3fb950"
ACCENT_AMBER    = "#e3b341"
ACCENT_RED      = "#f85149"
DIVIDER         = "#30363d"

# ── Spacing grid ───────────────────────────────────────────────────────────
CANVAS_W        = 1920
CANVAS_H        = 1080
MARGIN          = 80
ACCENT_STRIP_W  = 8
CONTENT_LEFT    = 108    # MARGIN + ACCENT_STRIP_W + 20
CONTENT_RIGHT   = 1840   # CANVAS_W - MARGIN
CONTENT_WIDTH   = 1732   # CONTENT_RIGHT - CONTENT_LEFT
TITLE_Y         = 80
DIVIDER_Y       = 180
BODY_Y          = 210
FOOTER_BAR_H    = 80
FOOTER_BAR_Y    = 1000   # CANVAS_H - FOOTER_BAR_H
BULLET_LEAD     = 52
LINE_HEIGHT_BODY = 48
DIAGRAM_X       = 1060
DIAGRAM_Y       = 210
DIAGRAM_W       = 780
DIAGRAM_H       = 680
BULLET_AREA_W      = 900
BULLET_AREA_W_FULL = 1732

# ── Font assets ─────────────────────────────────────────────────────────────
_FONTS_DIR = Path(__file__).parent.parent / "assets" / "fonts"

_SANS_REGULAR = _FONTS_DIR / "Inter-Regular.ttf"
_SANS_BOLD    = _FONTS_DIR / "Inter-Bold.ttf"
_MONO_REGULAR = _FONTS_DIR / "JetBrainsMono-Regular.ttf"
_MONO_BOLD    = _FONTS_DIR / "JetBrainsMono-Bold.ttf"

FONT_SANS_FALLBACK = ["Segoe UI", "Arial", "DejaVu Sans"]
FONT_MONO_FALLBACK = ["Consolas", "Courier New", "DejaVu Sans Mono"]


def _load_font(size: int, bold: bool = False, mono: bool = False) -> ImageFont.ImageFont:
    """
    Try the bundled TTF first, then system fallbacks.
    Never raises — returns Pillow's bitmap font as last resort.
    """
    if mono:
        primary = _MONO_BOLD if bold else _MONO_REGULAR
        fallbacks = FONT_MONO_FALLBACK
    else:
        primary = _SANS_BOLD if bold else _SANS_REGULAR
        fallbacks = FONT_SANS_FALLBACK

    if primary.exists():
        try:
            return ImageFont.truetype(str(primary), size)
        except (OSError, IOError):
            pass

    for name in fallbacks:
        try:
            return ImageFont.truetype(name, size)
        except (OSError, IOError):
            pass

    return ImageFont.load_default()


def wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    """Split text into lines that each fit within max_width pixels."""
    words = text.split()
    lines: list[str] = []
    current: list[str] = []

    for word in words:
        candidate = " ".join(current + [word])
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]

    if current:
        lines.append(" ".join(current))

    return lines or [""]
