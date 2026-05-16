import logging
import os
import tempfile
import time as _time
from dataclasses import replace
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from tutor.models import SlideSegment, VisualSpec

log = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "templates"
ASSET_DIR = Path(__file__).parent.parent / "assets" / "html"
_ENV = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)

_FALLBACK_VISUAL_TYPE = "key_insight"
_MIN_PNG_BYTES = 5_120  # 5 KB — any PNG smaller than this is a failed render


def _fallback_segment(seg: SlideSegment) -> SlideSegment:
    """Return a copy of seg reclassified as key_insight for render fallback."""
    return replace(
        seg,
        visual_type=_FALLBACK_VISUAL_TYPE,
        body=seg.body or f"[diagram: {seg.title}]",
        mermaid=None,
    )


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
    _prime_msvcp()  # ensure MSVCP140.dll is on the DLL search path before playwright loads
    from playwright.sync_api import sync_playwright  # lazy: avoid DLL load at import time

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
                try:
                    _screenshot(
                        page,
                        html,
                        out,
                        wait_mermaid=(seg.visual_type == "diagram"),
                        wait_hljs=(seg.code is not None),
                    )
                except Exception as exc:
                    log.warning(
                        "Slide render failed for %s (%s): %s — retrying as %s",
                        out.name,
                        seg.visual_type,
                        exc,
                        _FALLBACK_VISUAL_TYPE,
                    )
                    fallback_seg = _fallback_segment(seg)
                    fallback_html = _render_html(
                        fallback_seg.visual_type,
                        seg=fallback_seg,
                        current_dot=seg.segment_index + 1,
                        total_dots=total,
                        asset_dir=ASSET_DIR.as_uri(),
                    )
                    _screenshot(
                        page,
                        fallback_html,
                        out,
                        wait_mermaid=False,
                        wait_hljs=False,
                    )
                    seg.visual_type = _FALLBACK_VISUAL_TYPE

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

        # Navigate with one retry for transient file:// timing issues.
        for attempt in range(2):
            try:
                page.goto(url, wait_until="domcontentloaded")  # type: ignore[union-attr]
                break
            except Exception:
                if attempt == 0:
                    _time.sleep(0.2)
                else:
                    raise

        if wait_mermaid:
            try:
                page.wait_for_function(  # type: ignore[union-attr]
                    "() => document.querySelector('.mermaid svg') !== null",
                    timeout=10_000,
                )
            except Exception:
                log.warning(
                    "Mermaid diagram did not render within 10 s for %s — slide will use fallback",
                    output.name,
                )
                raise  # re-raise so render_all_slides can apply fallback

        if wait_hljs:
            try:
                page.wait_for_function(  # type: ignore[union-attr]
                    "() => document.querySelector('pre code.hljs') !== null",
                    timeout=5_000,
                )
            except Exception:
                log.warning(
                    "highlight.js did not render within 5 s for %s — "
                    "screenshot may show un-highlighted code",
                    output.name,
                )
                # Do not re-raise for hljs; un-highlighted code is acceptable.

        page.screenshot(path=str(output), full_page=False)  # type: ignore[union-attr]

        # Validate the output is a real PNG.
        if not output.exists() or output.stat().st_size < _MIN_PNG_BYTES:
            raise RuntimeError(
                f"Screenshot for {output.name} is missing or too small "
                f"({output.stat().st_size if output.exists() else 0} bytes); "
                f"expected ≥ {_MIN_PNG_BYTES} bytes"
            )

    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _prime_msvcp() -> None:
    """Add a directory containing MSVCP140.dll to the DLL search path on Windows.

    Python ships vcruntime140.dll but not msvcp140.dll; greenlet (used by
    playwright's sync API) links against it. The DLL exists on the system
    in non-standard locations so we find it dynamically.
    """
    import sys

    if sys.platform != "win32":
        return
    import glob

    candidates = [
        r"C:\Windows\System32\HealthAttestationClient",
        r"C:\Windows\System32\Microsoft-Edge-WebView",
        *glob.glob(r"C:\Windows\WinSxS\amd64_microsoft-edge-webview_*"),
    ]
    for directory in candidates:
        msvcp = os.path.join(directory, "MSVCP140.dll")
        if os.path.exists(msvcp):
            try:
                os.add_dll_directory(directory)
                log.debug("Added DLL directory for MSVCP140: %s", directory)
                return
            except OSError:
                continue
    log.debug("MSVCP140.dll not found in known locations — playwright may fail")
