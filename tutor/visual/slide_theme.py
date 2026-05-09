"""
Colour palette, spacing constants, and font loading for the slide compositor.
No Pillow Image/Draw objects are created here.
"""

import sys
from pathlib import Path

from PIL import ImageDraw, ImageFont

# ── Colour palette ─────────────────────────────────────────────────────────
BG_DEEP = "#0d1117"
BG_CARD = "#161b22"
BG_PANEL = "#1c2128"  # slightly lighter panel for bullet cards
BG_ACCENT_STRIP = "#00b4d8"
TEXT_PRIMARY = "#e6edf3"
TEXT_SECONDARY = "#8b949e"
TEXT_CODE = "#79c0ff"
ACCENT_CYAN = "#00b4d8"
ACCENT_GREEN = "#3fb950"
ACCENT_AMBER = "#e3b341"
ACCENT_RED = "#f85149"
DIVIDER = "#30363d"

# ── Spacing grid ───────────────────────────────────────────────────────────
CANVAS_W = 1920
CANVAS_H = 1080
MARGIN = 72
ACCENT_STRIP_W = 10
CONTENT_LEFT = 108
CONTENT_RIGHT = 1848
CONTENT_WIDTH = 1740
TITLE_Y = 68
DIVIDER_Y = 168
BODY_Y = 204
FOOTER_BAR_H = 84
FOOTER_BAR_Y = 996
BULLET_LEAD = 58
LINE_HEIGHT_BODY = 50
DIAGRAM_X = 1020
DIAGRAM_Y = 200
DIAGRAM_W = 820
DIAGRAM_H = 720
BULLET_AREA_W = 870
BULLET_AREA_W_FULL = 1740

# ── Font assets ─────────────────────────────────────────────────────────────
_FONTS_DIR = Path(__file__).parent.parent / "assets" / "fonts"

_SANS_REGULAR = _FONTS_DIR / "Inter-Regular.ttf"
_SANS_BOLD = _FONTS_DIR / "Inter-Bold.ttf"
_MONO_REGULAR = _FONTS_DIR / "JetBrainsMono-Regular.ttf"
_MONO_BOLD = _FONTS_DIR / "JetBrainsMono-Bold.ttf"

# Windows system font paths (full path — works reliably with Pillow on Windows)
_WIN_FONTS = Path("C:/Windows/Fonts")
_WIN_SANS = {
    (False, False): _WIN_FONTS / "segoeui.ttf",
    (True, False): _WIN_FONTS / "segoeuib.ttf",
    (False, True): _WIN_FONTS / "consola.ttf",
    (True, True): _WIN_FONTS / "consolab.ttf",
}
_WIN_SANS_FALLBACK = {
    (False, False): _WIN_FONTS / "verdana.ttf",
    (True, False): _WIN_FONTS / "verdanab.ttf",
    (False, True): _WIN_FONTS / "cour.ttf",
    (True, True): _WIN_FONTS / "courbd.ttf",
}

FONT_SANS_FALLBACK = ["Segoe UI", "Arial", "DejaVu Sans"]
FONT_MONO_FALLBACK = ["Consolas", "Courier New", "DejaVu Sans Mono"]


def _load_font(
    size: int, bold: bool = False, mono: bool = False
) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    """
    Try bundled TTF → Windows system path → name-based → bitmap default.
    Never raises.
    """
    primary = (
        (_MONO_BOLD if bold else _MONO_REGULAR) if mono else (_SANS_BOLD if bold else _SANS_REGULAR)
    )
    fallback_names = FONT_MONO_FALLBACK if mono else FONT_SANS_FALLBACK

    # 1. Bundled font (Inter / JetBrains Mono from assets/fonts/)
    if primary.exists():
        try:
            return ImageFont.truetype(str(primary), size)
        except OSError:
            pass

    # 2. Windows system fonts via full path (most reliable on Windows)
    if sys.platform == "win32":
        key = (bold, mono)
        for path_map in (_WIN_SANS, _WIN_SANS_FALLBACK):
            p = path_map.get(key)
            if p and p.exists():
                try:
                    return ImageFont.truetype(str(p), size)
                except OSError:
                    pass

    # 3. Font by name (works on Linux/Mac, sometimes Windows)
    for name in fallback_names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass

    return ImageFont.load_default()


def wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont | ImageFont.FreeTypeFont,
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
