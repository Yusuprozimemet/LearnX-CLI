import os
import tempfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

from tutor.models import SlideSegment, VisualSpec

TEMPLATE_DIR = Path(__file__).parent / "templates"
ASSET_DIR = Path(__file__).parent.parent / "assets" / "html"
_ENV = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)


def render_all_slides(
    title_spec: VisualSpec,
    outro_spec: VisualSpec,
    segments_by_unit: dict[int, list[SlideSegment]],
    output_dir: Path,
    session_label: str,
) -> list[Path]:
    """
    Render all slides in video order:
      title_card, unit_1_segs..., unit_N_segs..., outro

    Populates seg.png_path on every SlideSegment in segments_by_unit.
    Returns ordered list of PNG paths for the beat timer.
    One Playwright browser context is opened and reused for all slides.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.set_viewport_size({"width": 1920, "height": 1080})

        title_path = output_dir / "00_title.png"
        _screenshot(
            page,
            _render_html("title_card", spec=title_spec),
            title_path,
            wait_mermaid=False,
            wait_hljs=False,
        )
        paths.append(title_path)

        for unit_num in sorted(segments_by_unit.keys()):
            segs = segments_by_unit[unit_num]
            total = len(segs)
            for seg in segs:
                filename = f"{unit_num:02d}_{seg.segment_index:02d}_{seg.visual_type}.png"
                out = output_dir / filename
                html = _render_html(
                    seg.visual_type,
                    seg=seg,
                    current_dot=seg.segment_index + 1,
                    total_dots=total,
                    asset_dir=ASSET_DIR.as_uri(),
                )
                _screenshot(
                    page,
                    html,
                    out,
                    wait_mermaid=(seg.visual_type == "diagram"),
                    wait_hljs=(seg.code is not None),
                )
                seg.png_path = str(out)
                paths.append(out)

        outro_path = output_dir / "99_outro.png"
        _screenshot(
            page,
            _render_html("outro", spec=outro_spec),
            outro_path,
            wait_mermaid=False,
            wait_hljs=False,
        )
        paths.append(outro_path)

        browser.close()

    return paths


def _render_html(template_name: str, **context: object) -> str:
    context["asset_dir"] = ASSET_DIR.as_uri()
    return _ENV.get_template(f"{template_name}.html.j2").render(**context)


def _screenshot(
    page: object,
    html: str,
    output: Path,
    wait_mermaid: bool,
    wait_hljs: bool,
) -> None:
    # Write to a temp file so the page gets a file:// origin and can load
    # CSS/JS/font assets via file:// URLs (set_content() gives null origin,
    # which Chromium blocks).
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html)
        tmp_path = f.name
    try:
        url = "file:///" + tmp_path.replace(os.sep, "/")
        page.goto(url, wait_until="domcontentloaded")  # type: ignore[union-attr]
        if wait_mermaid:
            try:
                page.wait_for_function(  # type: ignore[union-attr]
                    "() => document.querySelector('.mermaid svg') !== null",
                    timeout=10_000,
                )
            except Exception:
                pass
        if wait_hljs:
            try:
                page.wait_for_function(  # type: ignore[union-attr]
                    "() => document.querySelector('pre code.hljs') !== null",
                    timeout=5_000,
                )
            except Exception:
                pass
        page.screenshot(path=str(output), full_page=False)  # type: ignore[union-attr]
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
