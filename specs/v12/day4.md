# Day 4 (v12) — Playwright Rendering Hardening

## Goal

Fix the three silent failure modes in `tutor/visual/slide_renderer.py`:

1. **Mermaid timeout is swallowed silently.** `except Exception: pass` after the
   Mermaid wait means a diagram slide can screenshot an empty white box with no
   warning. Replace with a logged warning and a fallback: re-render the slide as a
   `key_insight` type using the diagram title and `seg.body` as the text.

2. **No screenshot validation.** After `page.screenshot()`, the PNG file may be
   missing or nearly empty (0-byte write on navigation error). Add a file-size
   assertion: any PNG smaller than 5 KB is considered a failed render.

3. **No retry on transient navigation failure.** `page.goto()` can transiently fail
   on `file://` URLs due to temporary Chromium timing issues. Add one retry before
   raising, with a 200 ms wait between attempts.

---

## Done (merge gate)

```powershell
py -m pytest tutor/tests/ -v -k "renderer or visual or slide"
py -m ruff check tutor/
py -m ruff format --check tutor/
```

Report: paste gate output. List each acceptance criterion.
Stop: do not merge — wait for human review.

---

## Data boundary

```
Modifies (existing):
  tutor/visual/slide_renderer.py       ← hardening changes
  tutor/tests/test_slide_renderer.py   ← new tests (create if absent)

Does NOT touch:
  tutor/visual/templates/              ← unchanged
  tutor/assets/html/                   ← unchanged
  tutor/generation/segment_planner.py  ← unchanged
  tutor/visual/__init__.py             ← unchanged
  tutor/visual/beat_timer.py           ← unchanged
  tutor/visual/video_assembler.py      ← unchanged
```

---

## Change 1 — Extract `_render_segment_html()` helper

Before writing the hardening logic, extract a small helper that builds the fallback
`key_insight` HTML for a failed diagram. This keeps `_screenshot()` from growing
beyond 40 lines.

Add to `slide_renderer.py`:

```python
_FALLBACK_VISUAL_TYPE = "key_insight"
_MIN_PNG_BYTES = 5_120  # 5 KB — any PNG smaller than this is a failed render


def _fallback_segment(seg: SlideSegment) -> SlideSegment:
    """Return a copy of seg reclassified as key_insight for render fallback."""
    from dataclasses import replace
    return replace(
        seg,
        visual_type=_FALLBACK_VISUAL_TYPE,
        body=seg.body or f"[diagram: {seg.title}]",
        mermaid=None,
    )
```

`dataclasses.replace()` is in the standard library (Python 3.7+). `SlideSegment`
is a `@dataclass`, so `replace()` works without modification.

---

## Change 2 — Harden `_screenshot()`

Replace the existing `_screenshot()` function with the version below.

Key changes vs current implementation:
- `page.goto()` is retried once on any `Exception` (200 ms wait between attempts).
  This handles transient Chromium timing issues on `file://` URLs.
- Mermaid `wait_for_function` failure is caught, logged as a warning (not silently
  swallowed), and sets `mermaid_failed = True`.
- After `page.screenshot()`, the output file size is checked. If it is absent or
  smaller than `_MIN_PNG_BYTES`, a `RuntimeError` is raised with a clear message.
- The caller (`render_all_slides`) catches `RuntimeError` for diagram segments and
  re-renders as `key_insight` fallback.

```python
import time as _time


def _screenshot(
    page: object,
    html: str,
    output: Path,
    wait_mermaid: bool,
    wait_hljs: bool,
) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False, encoding="utf-8"
    ) as f:
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
                    "Mermaid diagram did not render within 10 s for %s — "
                    "slide will use fallback",
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
```

---

## Change 3 — Add fallback handling in `render_all_slides()`

In the per-unit segment loop inside `render_all_slides()`, wrap `_screenshot()` in
a try/except and re-render as `_FALLBACK_VISUAL_TYPE` when it raises.

Replace the current inner loop body:

```python
# Current (no error handling):
_screenshot(
    page,
    html,
    out,
    wait_mermaid=(seg.visual_type == "diagram"),
    wait_hljs=(seg.code is not None),
)
seg.png_path = str(out)
paths.append(out)
```

With:

```python
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
        out.name, seg.visual_type, exc, _FALLBACK_VISUAL_TYPE,
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
```

If the fallback render also fails, the exception propagates up and the pipeline
exits with a clear error message. This is intentional: two consecutive failures
indicate a Playwright configuration problem, not a content problem.

---

## New tests — add to `tutor/tests/test_slide_renderer.py`

```python
import os
import pathlib
import tempfile
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from tutor.visual.slide_renderer import _fallback_segment, _MIN_PNG_BYTES
from tutor.models import SlideSegment


def _make_seg(**kwargs) -> SlideSegment:
    defaults = dict(
        unit_index=1,
        segment_index=0,
        lines_start=0,
        lines_end=2,
        visual_type="diagram",
        title="Class hierarchy",
        body="Shows the relationship between Animal and Dog",
        code=None,
        language=None,
        mermaid="classDiagram\n  Animal <|-- Dog",
        left=None,
        right=None,
        rows=None,
        png_path="",
    )
    defaults.update(kwargs)
    return SlideSegment(**defaults)


def test_fallback_segment_reclassifies_to_key_insight():
    seg = _make_seg(visual_type="diagram", mermaid="classDiagram\n  A <|-- B")
    result = _fallback_segment(seg)
    assert result.visual_type == "key_insight"
    assert result.mermaid is None
    assert result.body is not None


def test_fallback_segment_preserves_body_when_present():
    seg = _make_seg(body="Animal is a base class")
    result = _fallback_segment(seg)
    assert result.body == "Animal is a base class"


def test_fallback_segment_uses_title_when_body_is_none():
    seg = _make_seg(body=None)
    result = _fallback_segment(seg)
    assert "Class hierarchy" in result.body


def test_min_png_bytes_constant():
    assert _MIN_PNG_BYTES == 5_120


def test_screenshot_raises_on_small_file(tmp_path):
    """_screenshot raises RuntimeError when the output PNG is below the size threshold."""
    from tutor.visual.slide_renderer import _screenshot

    html = "<html><body>test</body></html>"
    output = tmp_path / "test.png"

    # Write a tiny fake PNG (1 byte) to simulate a failed render
    output.write_bytes(b"X")

    # Mock page that does nothing on goto/screenshot
    mock_page = MagicMock()

    with pytest.raises(RuntimeError, match="too small"):
        _screenshot(mock_page, html, output, wait_mermaid=False, wait_hljs=False)


def test_screenshot_goto_retries_once_on_failure(tmp_path):
    """page.goto() is retried once before raising on persistent failure."""
    from tutor.visual.slide_renderer import _screenshot

    html = "<html><body>test</body></html>"
    output = tmp_path / "out.png"

    mock_page = MagicMock()
    mock_page.goto.side_effect = [RuntimeError("connection reset"), None]

    # Make screenshot produce a valid-size file
    def fake_screenshot(**kwargs):
        output.write_bytes(b"PNG" + b"\x00" * 6000)

    mock_page.screenshot.side_effect = fake_screenshot

    _screenshot(mock_page, html, output, wait_mermaid=False, wait_hljs=False)
    assert mock_page.goto.call_count == 2
```

---

## Acceptance criteria

- [ ] `_MIN_PNG_BYTES = 5_120` constant defined in `slide_renderer.py`
- [ ] `_fallback_segment()` function defined — returns a copy with `visual_type="key_insight"`, `mermaid=None`
- [ ] `_screenshot()` retries `page.goto()` once before raising on navigation error
- [ ] `_screenshot()` logs a `WARNING` when Mermaid `wait_for_function` times out
- [ ] After the Mermaid timeout warning, `_screenshot()` re-raises so the caller can apply fallback
- [ ] `_screenshot()` logs a `WARNING` for highlight.js timeout but does NOT re-raise
- [ ] After `page.screenshot()`, file size is checked; raises `RuntimeError` if < `_MIN_PNG_BYTES`
- [ ] `render_all_slides()` catches `Exception` on `_screenshot()` for content segments
- [ ] On catch, `render_all_slides()` calls `_fallback_segment()` and re-renders as `key_insight`
- [ ] If fallback render also fails, the exception propagates up (not caught a second time)
- [ ] `seg.visual_type` is updated to `_FALLBACK_VISUAL_TYPE` after a successful fallback render
- [ ] `test_fallback_segment_reclassifies_to_key_insight` passes
- [ ] `test_fallback_segment_preserves_body_when_present` passes
- [ ] `test_fallback_segment_uses_title_when_body_is_none` passes
- [ ] `test_min_png_bytes_constant` passes
- [ ] `test_screenshot_raises_on_small_file` passes
- [ ] `test_screenshot_goto_retries_once_on_failure` passes
- [ ] All pre-existing tests still pass
- [ ] ruff clean
