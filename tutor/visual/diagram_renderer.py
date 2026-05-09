import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from subprocess import DEVNULL
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from tutor.exceptions import ConfigError
from tutor.models import VisualSpec

log = logging.getLogger(__name__)

# ── Output dimensions ──────────────────────────────────────────────────────
DIAGRAM_W = 800
DIAGRAM_H = 500
CODE_COMP_H = 400
ANALOGY_H = 260

# ── Dark palette ───────────────────────────────────────────────────────────
BG_CARD = "#161b22"
BG_WRONG = "#2a0d0d"
BG_RIGHT = "#0d2a1a"
TEXT_PRI = "#e6edf3"
TEXT_SEC = "#8b949e"
COL_WRONG = "#f85149"
COL_RIGHT = "#3fb950"
COL_DIVIDER = "#30363d"
COL_CYAN = "#00b4d8"

_graphviz_ready: bool | None = None  # None = unchecked


# ── Public API ─────────────────────────────────────────────────────────────


def render_diagram(spec: VisualSpec, output_dir: Path) -> Path | None:
    """
    Dispatch to the correct renderer. Returns PNG path or None on catastrophic failure.
    ConfigError (graphviz not installed) is re-raised so the pipeline can surface it.
    """
    output_path = output_dir / f"unit_{spec.unit_index:02d}_diagram.png"

    if spec.diagram_type == "code_comparison":
        if isinstance(spec.diagram_spec, dict):
            return _render_code_comparison(spec.diagram_spec, output_path)
        log.warning(
            "unit %d code_comparison spec is not a dict — using analogy fallback", spec.unit_index
        )
        return _render_analogy_fallback(spec.analogy or spec.memory_hook, output_path)

    if spec.diagram_type in ("class_diagram", "flowchart", "concept_map"):
        engine = "neato" if spec.diagram_type == "concept_map" else "dot"
        try:
            return _render_graphviz(str(spec.diagram_spec or ""), output_path, engine)
        except ConfigError:
            raise  # missing graphviz is fatal — propagate to caller
        except Exception as exc:
            log.warning(
                "graphviz failed for unit %d (%s): %s — using analogy fallback",
                spec.unit_index,
                spec.diagram_type,
                exc,
            )
            return _render_analogy_fallback(spec.analogy or spec.memory_hook, output_path)

    # diagram_type == "none" or unknown → render analogy as visual anchor
    return _render_analogy_fallback(spec.analogy or spec.memory_hook, output_path)


# ── Graphviz renderer ──────────────────────────────────────────────────────


def _render_graphviz(dot_source: str, output_path: Path, engine: str = "dot") -> Path:
    _check_graphviz()
    themed = _apply_dark_theme(dot_source)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".dot", delete=False, encoding="utf-8") as f:
        f.write(themed)
        dot_path = Path(f.name)

    # Always call the `dot` binary; use -K<engine> to select layout algorithm.
    cmd = ["dot", "-Tpng", f"-o{output_path}", str(dot_path)]
    if engine != "dot":
        cmd.insert(1, f"-K{engine}")

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=15)
        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="replace")[:300]
            raise ValueError(f"graphviz ({engine}) exit {result.returncode}: {err}")
    finally:
        dot_path.unlink(missing_ok=True)

    return output_path


def _apply_dark_theme(dot_source: str) -> str:
    """Inject dark-theme graph/node/edge defaults after the opening brace if absent."""
    if "bgcolor=" in dot_source:
        return dot_source

    brace = dot_source.find("{")
    if brace == -1:
        return dot_source

    injection = (
        '\n  graph [bgcolor="#0d1117" fontcolor="#e6edf3" fontname="Consolas,monospace"]\n'
        '  node  [style=filled fillcolor="#161b22" color="#30363d" '
        'fontcolor="#e6edf3" fontname="Consolas,monospace" fontsize=14]\n'
        '  edge  [color="#8b949e" fontcolor="#8b949e" fontname="Consolas,monospace" fontsize=11]\n'
    )
    return dot_source[: brace + 1] + injection + dot_source[brace + 1 :]


def _check_graphviz() -> None:
    global _graphviz_ready
    if _graphviz_ready:
        return

    try:
        subprocess.run(["dot", "-V"], stdout=DEVNULL, stderr=DEVNULL, check=True)
        _graphviz_ready = True
        return
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    if sys.platform == "win32":
        search_roots = [
            Path("C:/Program Files/Graphviz"),
            Path("C:/Graphviz"),
            Path("C:/graphviz"),  # portable zip extracted here
        ]
        for root in search_roots:
            if not root.exists():
                continue
            for candidate in [root / "bin" / "dot.exe", *root.glob("*/bin/dot.exe")]:
                if candidate.exists():
                    os.environ["PATH"] = str(candidate.parent) + os.pathsep + os.environ["PATH"]
                    _graphviz_ready = True
                    return

    raise ConfigError(
        "Graphviz not found.\n"
        "  Windows: download from https://graphviz.org/download/ and run the installer\n"
        "  Then restart your terminal and re-run."
    )


# ── Pillow renderers ───────────────────────────────────────────────────────


def _render_code_comparison(spec_dict: dict[str, Any], output_path: Path) -> Path:
    img = Image.new("RGB", (DIAGRAM_W, CODE_COMP_H), BG_CARD)
    draw = ImageDraw.Draw(img)

    font_hdr = _load_font(18, bold=True)
    font_code = _load_font(15, mono=True)
    font_label = _load_font(13, mono=True)

    col_w = DIAGRAM_W // 2

    draw.line([(col_w, 0), (col_w, CODE_COMP_H)], fill=COL_DIVIDER, width=1)

    # Left column — wrong
    draw.rectangle((0, 0, col_w - 1, 32), fill=BG_WRONG)
    draw.text((12, 7), "WRONG", font=font_hdr, fill=COL_WRONG)
    _draw_code_block(draw, spec_dict.get("wrong", ""), font_code, x=12, y=44)
    if lbl := spec_dict.get("label_wrong", ""):
        draw.text((12, CODE_COMP_H - 26), lbl, font=font_label, fill=TEXT_SEC)

    # Right column — correct
    draw.rectangle((col_w, 0, DIAGRAM_W - 1, 32), fill=BG_RIGHT)
    draw.text((col_w + 12, 7), "CORRECT", font=font_hdr, fill=COL_RIGHT)
    _draw_code_block(draw, spec_dict.get("right", ""), font_code, x=col_w + 12, y=44)
    if lbl := spec_dict.get("label_right", ""):
        draw.text((col_w + 12, CODE_COMP_H - 26), lbl, font=font_label, fill=TEXT_SEC)

    img.save(output_path, "PNG")
    return output_path


def _render_analogy_fallback(analogy: str, output_path: Path) -> Path:
    img = Image.new("RGB", (DIAGRAM_W, ANALOGY_H), BG_CARD)
    draw = ImageDraw.Draw(img)

    draw.rectangle((0, 0, 7, ANALOGY_H), fill=COL_CYAN)  # left accent stripe

    font_quote = _load_font(72, bold=True)
    font_body = _load_font(26)
    font_attr = _load_font(17)

    draw.text((20, 8), "“", font=font_quote, fill=COL_CYAN)

    text = analogy or "No analogy available."
    lines = _wrap(text, max_chars=56)
    y = 70
    for line in lines[:3]:
        draw.text((28, y), line, font=font_body, fill=TEXT_PRI)
        y += 38

    draw.text((DIAGRAM_W - 130, ANALOGY_H - 26), "— analogy", font=font_attr, fill=TEXT_SEC)

    img.save(output_path, "PNG")
    return output_path


# ── Helpers ────────────────────────────────────────────────────────────────


def _draw_code_block(draw: ImageDraw.ImageDraw, code: str, font: ImageFont.ImageFont | ImageFont.FreeTypeFont, x: int, y: int) -> None:
    for line in code.split("\n")[:8]:
        draw.text((x, y), line, font=font, fill=TEXT_PRI)
        y += 22


def _load_font(size: int, bold: bool = False, mono: bool = False) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    if mono:
        names = ["Consolas", "Courier New", "DejaVu Sans Mono"]
    elif bold:
        names = ["Segoe UI Bold", "Arial Bold", "DejaVu Sans Bold", "DejaVu Sans", "Arial"]
    else:
        names = ["Segoe UI", "Arial", "DejaVu Sans"]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _wrap(text: str, max_chars: int = 56) -> list[str]:
    words: list[str] = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        if len(" ".join(current + [word])) <= max_chars:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines
