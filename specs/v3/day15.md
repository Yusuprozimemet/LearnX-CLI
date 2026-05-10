# Day 15 — HTML Slide Renderer (Playwright + Jinja2)

## Goal

Replace the Pillow-based slide pipeline with a browser-rendered one. Slides are
produced by rendering Jinja2 HTML templates through a headless Chromium browser
(Playwright) and screenshotting each at 1920×1080. This gives publication-quality
typography, CSS Grid layouts, syntax-highlighted code via highlight.js, and
Mermaid diagrams — none of which are achievable with Pillow without implementing
a layout engine from scratch.

**Four existing files are deleted.** Their tests are deleted with them.
**One new Python file, one template directory, and one asset directory are created.**
The `video_assembler.py` ffmpeg commands do not change — it already accepts
`(png_path, duration_s)` tuples and does not care how the PNGs were produced.

---

## Done (merge gate)

```powershell
playwright install chromium              # one-time; skip if already installed
py -m pytest tutor/tests/visual/test_slide_renderer.py -v   # scoped — all green
py -m pytest                                                 # full suite — 0 failures
py -m ruff check tutor/                                      # 0 errors
py -m ruff format --check tutor/                             # 0 formatting issues
```

Report: list each acceptance criterion below with pass/fail. Paste gate output.
Stop: do not merge to main — wait for human review.

---

## Data boundary

```
Reads (in memory):
  SlideSegment objects    ← from segment_planner (Day 14)
  VisualSpec objects      ← from visual_planner (title card + outro)

Writes:
  video/<session>/slides/<filename>.png   ← one PNG per slide

Deleted files (must be removed as part of this day):
  tutor/visual/slide_compositor.py
  tutor/visual/slide_draw.py
  tutor/visual/slide_theme.py
  tutor/visual/diagram_renderer.py
  tutor/tests/visual/test_slide_compositor.py
  tutor/tests/visual/test_slide_draw.py
  tutor/tests/visual/test_slide_theme.py
  tutor/tests/visual/test_diagram_renderer.py
```

No LLM calls, no audio files, no ffmpeg in any file created this day.

---

## Dependency changes — `pyproject.toml`

### Add to `[project.dependencies]`

```toml
"playwright>=1.44",
"jinja2>=3.1",
```

### Remove from `[project.dependencies]`

Remove the `graphviz` Python package entry if present. (The system `dot` binary is
also no longer needed; update README setup instructions accordingly.)

### One-time Chromium install (developer machine + CI)

```powershell
playwright install chromium
```

Add this step to `.github/workflows/ci.yml` before the pytest step.

---

## Asset bundle — `tutor/assets/html/`

Commit these files to the repository. All are loaded via `file://` URI at render
time — no network calls during slide rendering.

```
tutor/assets/html/
  slide_base.css              ← shared dark theme, top bar, progress dots, footer
  theme-learnx-dark.css       ← highlight.js dark theme matching LearnX palette
  highlight.min.js            ← highlight.js core (MIT)
  highlight-java.min.js       ← Java language pack
  highlight-python.min.js     ← Python language pack
  highlight-javascript.min.js ← JavaScript language pack
  mermaid.min.js              ← Mermaid v10 (MIT, ~2.4 MB)
  fonts/
    Inter-Regular.woff2
    Inter-SemiBold.woff2
    Inter-Bold.woff2
    JetBrainsMono-Regular.woff2
```

**How to obtain:**
- highlight.js: https://highlightjs.org/download — select Java, Python, JavaScript packs
- Mermaid: `npm pack mermaid` or download from the GitHub release page
- Inter font: https://fonts.google.com/specimen/Inter (download and extract .woff2)
- JetBrains Mono: https://www.jetbrains.com/lp/mono/ (download .woff2)

All are MIT or OFL licensed. Commit the files directly; do not add a build step.

---

## Jinja2 templates — `tutor/visual/templates/`

One `.html.j2` file per visual type. All extend `_base.html.j2` via Jinja2
template inheritance.

### `_base.html.j2`

Defines the full page skeleton:

- `<!DOCTYPE html>` + `<meta charset="UTF-8">` + viewport `1920×1080`
- `<link>` loading `slide_base.css`, `theme-learnx-dark.css` from `asset_dir`
- `<script>` loading `highlight.min.js`, language packs, and `mermaid.min.js`
  from `asset_dir`
- `<script>` initialising highlight.js (`hljs.highlightAll()`) and Mermaid
  (`mermaid.initialize({startOnLoad:true, theme:'dark'})`)
- Top bar: `Unit {{ seg.unit_index }} · {{ seg.title }}` (or title card / outro variant)
- Footer bar: progress dots + LearnX logo
- `{% block content %}{% endblock %}` for slide-specific body

### `slide_base.css` — key values

```css
:root {
  --bg-deep:    #0d1117;
  --bg-card:    #161b22;
  --divider:    #30363d;
  --text-pri:   #e6edf3;
  --text-sec:   #8b949e;
  --accent-cyn: #00b4d8;
  --accent-amb: #e3a21a;
  --accent-grn: #3fb950;
  --font-ui:    'Inter', system-ui, sans-serif;
  --font-mono:  'JetBrains Mono', 'Consolas', monospace;
}

/* Canvas */
html, body { width: 1920px; height: 1080px; overflow: hidden; background: var(--bg-deep); }

/* Top bar */
.top-bar { height: 56px; background: var(--bg-card); border-bottom: 1px solid var(--divider); }

/* Footer bar */
.footer-bar { position: absolute; bottom: 0; height: 56px; width: 100%;
              background: var(--bg-card); border-top: 1px solid var(--divider); }

/* Content area */
.content { position: absolute; top: 56px; bottom: 56px; left: 80px; right: 80px; }

/* Progress dots */
.dot { width: 12px; height: 12px; border-radius: 50%; display: inline-block; margin: 0 4px; }
.dot--filled { background: var(--accent-cyn); }
.dot--hollow { background: var(--bg-card); border: 2px solid var(--divider); }
```

### Per-type templates

Each child template uses `{% block content %}` for its body area.

**`hook_question.html.j2`**
```jinja2
{% block content %}
<div class="hook-slide">
  <h1 class="hook-question">{{ seg.title }}</h1>
  {% if seg.body %}
  <ul class="learn-list">
    {% for item in seg.body.split('\n') if item %}
    <li>{{ item }}</li>
    {% endfor %}
  </ul>
  {% endif %}
</div>
{% endblock %}
```

**`definition.html.j2`**
Term name as large heading. Definition text below. Optional code block via
highlight.js (`<pre><code class="language-{{ seg.language or 'java' }}">`).

**`analogy.html.j2`**
CSS Grid two-panel layout. Left panel: `seg.left` label + `seg.rows[0][0]` body.
Right panel: `seg.right` label + `seg.rows[0][1]` body. `≈` symbol centred between.

**`comparison.html.j2`**
Two-column table. Header row: `seg.left` (cyan) | `seg.right` (amber).
Data rows: alternating `--bg-card` / `--bg-deep` bands. Max 6 rows; row 7+ becomes `…`.

**`code_example.html.j2`**
Optional description paragraph. Full-width highlight.js code block with
`language-{{ seg.language or 'java' }}` class. JetBrains Mono font.

**`diagram.html.j2`**
```jinja2
{% block content %}
<div class="diagram-slide">
  <div class="mermaid">{{ seg.mermaid }}</div>
</div>
{% endblock %}
```
Playwright waits for Mermaid to render the SVG before screenshotting (see renderer).

**`question_prompt.html.j2`**
Full canvas background `--bg-card` (signals MAYA/SAM, not ALEX). Speaker badge
top-right (MAYA → `--accent-grn`; SAM → `--accent-amb`). Large centred question text.

**`decision_guide.html.j2`**
Same two-column table as `comparison.html.j2`. Left header colour: `--accent-cyn`;
right header colour: `--accent-amb`.

**`key_insight.html.j2`**
Body text centred horizontally and vertically in content area. `--accent-amb` colour,
56px bold. Thin 400px `--accent-cyn` rule below text.

**`memory_hook.html.j2`**
Large centred single statement. `--text-pri`, 52px.

**`title_card.html.j2`** and **`outro.html.j2`**
For `VisualSpec` title card and outro. `_base.html.j2` variant with no unit index
in top bar, no progress dots in footer.

---

## New file — `tutor/visual/slide_renderer.py`

Single responsibility: open one Playwright browser context, render each slide HTML,
screenshot, close context. No CSS logic, no template logic, no Pillow.

```python
from pathlib import Path
from playwright.sync_api import sync_playwright
from jinja2 import Environment, FileSystemLoader
from tutor.models import SlideSegment, VisualSpec

TEMPLATE_DIR = Path(__file__).parent / "templates"
ASSET_DIR    = Path(__file__).parent.parent / "assets" / "html"
_ENV = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)


def render_all_slides(
    title_spec:       VisualSpec,
    outro_spec:       VisualSpec,
    segments_by_unit: dict[int, list[SlideSegment]],
    output_dir:       Path,
    session_label:    str,
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
        page    = browser.new_page()
        page.set_viewport_size({"width": 1920, "height": 1080})

        # Title card
        title_path = output_dir / "00_title.png"
        _screenshot(page, _render_html("title_card", spec=title_spec), title_path,
                    wait_mermaid=False, wait_hljs=False)
        paths.append(title_path)

        # Unit segments
        for unit_num in sorted(segments_by_unit.keys()):
            segs  = segments_by_unit[unit_num]
            total = len(segs)
            for seg in segs:
                filename = f"{unit_num:02d}_{seg.segment_index:02d}_{seg.visual_type}.png"
                out      = output_dir / filename
                html     = _render_html(seg.visual_type, seg=seg,
                                        current_dot=seg.segment_index + 1,
                                        total_dots=total,
                                        asset_dir=ASSET_DIR.as_uri())
                _screenshot(page, html, out,
                            wait_mermaid=(seg.visual_type == "diagram"),
                            wait_hljs=(seg.code is not None))
                seg.png_path = str(out)
                paths.append(out)

        # Outro
        outro_path = output_dir / "99_outro.png"
        _screenshot(page, _render_html("outro", spec=outro_spec), outro_path,
                    wait_mermaid=False, wait_hljs=False)
        paths.append(outro_path)

        browser.close()

    return paths


def _render_html(template_name: str, **context) -> str:
    context["asset_dir"] = ASSET_DIR.as_uri()
    return _ENV.get_template(f"{template_name}.html.j2").render(**context)


def _screenshot(page, html: str, output: Path,
                wait_mermaid: bool, wait_hljs: bool) -> None:
    page.set_content(html, wait_until="domcontentloaded")
    if wait_mermaid:
        try:
            page.wait_for_function(
                "() => document.querySelector('.mermaid svg') !== null",
                timeout=10_000,
            )
        except Exception:
            # Mermaid render failed — screenshot what's there (error text visible)
            pass
    if wait_hljs:
        try:
            page.wait_for_function(
                "() => document.querySelector('pre code.hljs') !== null",
                timeout=5_000,
            )
        except Exception:
            pass
    page.screenshot(path=str(output), full_page=False)
```

### Output filenames

```
video/<session>/slides/
  00_title.png
  01_00_hook_question.png     ← unit 01, segment index 00
  01_01_definition.png
  01_02_diagram.png
  ...
  01_10_memory_hook.png
  02_00_hook_question.png
  ...
  99_outro.png
```

Pattern: `{unit:02d}_{segment_index:02d}_{visual_type}.png`

---

## File sizes

- `slide_renderer.py` — new file, targeting ~100 lines (Python only; layout is in CSS)
- `templates/` — ~11 template files, ~20–40 lines each
- `assets/html/` — static files; no line limit applies

---

## Acceptance criteria

- [ ] All 10 visual types + title card + outro produce valid 1920×1080 PNGs
- [ ] `render_all_slides()` returns title + all segment PNGs + outro in correct order
- [ ] Output files written to `video/<session>/slides/`, not `audio/<session>/`
- [ ] `seg.png_path` populated on every `SlideSegment` in `segments_by_unit` after call
- [ ] `diagram` slides: Playwright waits for Mermaid SVG before screenshotting
- [ ] Invalid Mermaid does not crash the renderer — screenshot proceeds after timeout
- [ ] `code_example` slides: code rendered in JetBrains Mono via highlight.js
- [ ] `question_prompt` slides: speaker badge visible (MAYA/SAM with correct colour)
- [ ] `comparison` slides: more than 6 rows truncated with a `…` row
- [ ] All assets loaded from `file://` — no network calls during rendering
- [ ] `slide_renderer.py` stays under 200 lines
- [ ] Deleted files are gone: `slide_compositor.py`, `slide_draw.py`, `slide_theme.py`,
  `diagram_renderer.py` and their test files
- [ ] `pyproject.toml` has `playwright>=1.44` and `jinja2>=3.1` in dependencies
- [ ] Full pytest suite passes (tests that imported deleted files are removed)

---

## Tests — `tutor/tests/visual/test_slide_renderer.py`

New test file. Tests that require a live Playwright browser are marked
`@pytest.mark.slow` so they can be skipped in fast CI runs with `-m "not slow"`.

- `test_render_all_slides_returns_correct_count` — 2 units × 3 segments + title + outro = 8 paths `@slow`
- `test_title_is_first_path` — first returned path filename starts with `00_title` `@slow`
- `test_outro_is_last_path` — last returned path filename starts with `99_outro` `@slow`
- `test_png_path_populated_on_segments` — all segs have non-empty `png_path` after call `@slow`
- `test_output_files_exist_on_disk` — every returned path exists as a file `@slow`
- `test_image_dimensions_are_1920x1080` — open PNG with Pillow; assert size `@slow`
- `test_invalid_mermaid_does_not_crash` — `diagram` seg with garbage mermaid string → PNG written `@slow`
- `test_render_html_returns_string` — `_render_html("key_insight", seg=stub_seg, ...)` returns non-empty string (no browser needed)
- `test_template_missing_raises_clearly` — `_render_html("nonexistent_type", ...)` raises `TemplateNotFound`
