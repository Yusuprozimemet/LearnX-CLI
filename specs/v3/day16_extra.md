# Day 17 — Slide Renderer Overhaul: CSS Loading, Fonts, Templates, Timing

## Goal

Fix four bugs that cause slides to render as unstyled white pages with broken layout:

1. **CSS/JS blocked** — `page.set_content(html)` gives Playwright a null origin; Chromium
   blocks all `file://` resource loads. Fix: write HTML to a temp file and use
   `page.goto("file:///...")`.

2. **Invalid font stubs** — The four WOFF2 files are 48-byte stubs (`wOF2` + zeros), not
   real fonts. Fix: replace with a system-safe CSS font stack and remove the stub files.

3. **Template `None` rendering** — Jinja2 autoescape renders Python `None` as the literal
   string `"None"`. Fix: add `| default('')` guards to every field that may be `None`.

4. **Inter-segment timing gap** — `_exact_duration()` in `beat_timer.py` computes
   `end_ms[last_line] - start_ms[first_line]`, ignoring the `SILENCE_TURN_MS` pause
   that is baked into the concatenated MP3 *between* the last line of one segment and
   the first line of the next. This causes total slide duration < MP3 duration, so
   audio is cut at the end. Fix: add the turn silence to every segment's duration when
   timing is exact.

---

## Data Boundary (files to touch)

```
tutor/visual/slide_renderer.py          ← bug 1 (set_content → goto)
tutor/assets/html/slide_base.css        ← bug 2 (add system font stack, drop @font-face)
tutor/assets/html/fonts/               ← bug 2 (delete all four stub files)
tutor/visual/templates/                 ← bug 3 (| default('') everywhere)
tutor/visual/beat_timer.py              ← bug 4 (_exact_duration fix)
tutor/tests/visual/test_slide_renderer.py   ← update / add tests for goto path
tutor/tests/visual/test_beat_timer.py       ← add gap-accounting test
```

Do **not** touch any other file.

---

## Bug 1 — CSS/JS Loading (`slide_renderer.py`)

### Root Cause

```python
# BROKEN — null origin blocks file://
page.set_content(html, wait_until="domcontentloaded")
```

Chromium assigns a null/opaque origin to pages loaded with `set_content()`. The Content
Security Policy then blocks loading CSS, JS, or fonts via `file://` URLs, even though the
stylesheet href and script src point to valid on-disk files. The resulting screenshot has
the browser default white background and 16 px serif font.

### Fix

Replace `_screenshot()` to write the HTML to a temporary file and navigate to it:

```python
import tempfile, os

def _screenshot(page: Page, html: str, output: Path, wait_mermaid: bool, wait_hljs: bool) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False, encoding="utf-8"
    ) as f:
        f.write(html)
        tmp_path = f.name
    try:
        page.goto(f"file:///{tmp_path.replace(os.sep, '/')}", wait_until="domcontentloaded")
        if wait_hljs:
            page.wait_for_function("typeof hljs !== 'undefined'", timeout=3000)
        if wait_mermaid:
            page.wait_for_function(
                "document.querySelector('.mermaid svg') !== null", timeout=5000
            )
        page.screenshot(path=str(output), full_page=False)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
```

The `file:///` URL gives the page a `file://` origin, so the browser can load all
`file://` sibling resources (CSS, JS, fonts).

### Windows path note

`page.goto()` requires forward slashes. `tmp_path.replace(os.sep, '/')` handles the
Windows backslash-to-slash conversion. The leading triple slash (`file:///`) is correct
for absolute paths on Windows too (`file:///C:/Users/...`).

---

## Bug 2 — Invalid Font Stubs

### Root Cause

`tutor/assets/html/fonts/*.woff2` are placeholder files: `b'wOF2' + b'\x00' * 44`.
Chromium silently rejects them and falls back to the browser default serif font.
`@font-face` declarations referencing these stubs are wasted bytes.

### Fix — System font stack

Replace the four `@font-face` declarations in `slide_base.css` with a pure system font
stack. No binary font assets are needed.

```css
/* Replace entire @font-face block with: */
:root {
  --font-sans: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  --font-mono: "Cascadia Code", "Consolas", "Courier New", monospace;
}

body {
  font-family: var(--font-sans);
}

code, pre, .code-block {
  font-family: var(--font-mono);
}
```

`Segoe UI` is the Windows system UI font (present on all Windows 10+ machines).
`Cascadia Code` is bundled with Windows Terminal; `Consolas` is the fallback on older
Windows builds.

Delete the four stub files:

```
tutor/assets/html/fonts/Inter-Regular.woff2
tutor/assets/html/fonts/Inter-SemiBold.woff2
tutor/assets/html/fonts/Inter-Bold.woff2
tutor/assets/html/fonts/JetBrainsMono-Regular.woff2
```

Also remove their `@font-face` declarations from `slide_base.css`. If the `fonts/`
directory becomes empty, delete it too (Playwright does not serve directory listings).

---

## Bug 3 — Template `None` Rendering

### Root Cause

Jinja2 `autoescape=True` converts `None` → `"None"` (the string). Any template field
that is conditionally populated (e.g., `seg.body`, `seg.left`, `seg.right`, `seg.rows`,
`seg.mermaid`, `seg.code`) renders as the literal word "None" when not provided.

Observed example: `analogy.html.j2` produced `"None ≈ None"` for a segment with
`left=None, right=None`.

### Fix — add `| default('')` and conditional guards to every template

Apply the following rules consistently across all templates:

**Rule A** — simple optional string fields:
```jinja2
{# Before #}
{{ seg.body }}
{# After #}
{{ seg.body | default('') }}
```

**Rule B** — block-level optional sections (hide the entire element if empty):
```jinja2
{% if seg.body %}
<p class="body-text">{{ seg.body }}</p>
{% endif %}
```

**Rule C** — analogy / comparison (left + right):
```jinja2
{% if seg.left and seg.right %}
<div class="analogy-pair">
  <div class="analogy-side">{{ seg.left }}</div>
  <span class="analogy-sep">≈</span>
  <div class="analogy-side">{{ seg.right }}</div>
</div>
{% endif %}
```

**Rule D** — rows (table):
```jinja2
{% if seg.rows %}
<table class="data-table">
  {% for row in seg.rows %}
  <tr>{% for cell in row %}<td>{{ cell | default('') }}</td>{% endfor %}</tr>
  {% endfor %}
</table>
{% endif %}
```

**Rule E** — mermaid diagrams:
```jinja2
{% if seg.mermaid %}
<div class="mermaid">{{ seg.mermaid }}</div>
{% endif %}
```

**Rule F** — code blocks:
```jinja2
{% if seg.code %}
<pre><code class="{{ seg.language | default('plaintext') }}">{{ seg.code }}</code></pre>
{% endif %}
```

Apply these rules to every template in `tutor/visual/templates/` that references
`seg` fields.

---

## Bug 4 — Inter-Segment Timing Gap (`beat_timer.py`)

### Root Cause

`_exact_duration(seg, unit_timing)` computes:

```python
start_ms = unit_timing[seg.lines_start]["start_ms"]
end_ms   = unit_timing[seg.lines_end]["end_ms"]
return max((end_ms - start_ms) / 1000.0, MIN_SLIDE_DURATION)
```

The audio builder inserts `SILENCE_TURN_MS` of silence **after** each line's audio,
so the gap between `end_ms` of line N and `start_ms` of line N+1 is approximately
`SILENCE_TURN_MS`. That gap belongs to neither segment; it falls between them.

Result: for each segment boundary, `SILENCE_TURN_MS / 1000` seconds of audio plays
over the *next* slide's timing window. With many segments, the cumulative drift causes
the last few seconds of the unit audio to play over the outro card (or be cut).

### Fix

Add the turn silence to each segment's computed duration:

```python
from tutor.constants import SILENCE_TURN_MS

def _exact_duration(seg: SlideSegment, unit_timing: list[dict]) -> float:
    start_ms = unit_timing[seg.lines_start]["start_ms"]
    end_ms   = unit_timing[seg.lines_end]["end_ms"]
    raw_ms   = end_ms - start_ms
    # Each line in the segment has a trailing SILENCE_TURN_MS baked into the MP3.
    # Add it back so slide duration matches the actual audio window.
    n_lines = seg.lines_end - seg.lines_start + 1
    adjusted_ms = raw_ms + n_lines * SILENCE_TURN_MS
    return max(adjusted_ms / 1000.0, MIN_SLIDE_DURATION)
```

Note: the *last* segment in a unit does not have trailing turn-silence (the inter-unit
silence is `SILENCE_UNIT_MS`, handled separately). This means the last segment gets a
small over-estimate (~`SILENCE_TURN_MS / 1000` seconds). That is acceptable — it pads
the outro slightly rather than cutting audio. If precise alignment is needed for a future
day, track `is_last_segment` and subtract once.

---

## Algorithm — Summary of Changes

### `slide_renderer.py`

1. Import `tempfile`, `os`.
2. Replace `page.set_content(...)` call in `_screenshot()` with:
   - write `html` to a NamedTemporaryFile
   - `page.goto(f"file:///{tmp_path.replace(os.sep, '/')}", wait_until="domcontentloaded")`
   - screenshot
   - `os.unlink(tmp_path)` in a finally block

### `slide_base.css`

1. Delete all four `@font-face` declarations.
2. Add `:root { --font-sans: ...; --font-mono: ...; }` with system stacks.
3. Set `body { font-family: var(--font-sans); }`.
4. Set `code, pre, .code-block { font-family: var(--font-mono); }`.

### Templates (`tutor/visual/templates/*.html.j2`)

Apply Rules A–F above to every template that uses `seg.*` fields. Check each of:
`hook_question`, `key_insight`, `analogy`, `comparison`, `code_example`, `diagram`,
`definition`, `question_prompt`, `memory_hook`, `mini_quiz`, `numbered_list`.

### `beat_timer.py`

In `_exact_duration()`, add `n_lines * SILENCE_TURN_MS` to `raw_ms` before dividing.

---

## Acceptance Criteria

### AC-1 — Screenshots show dark background

Running `py -m pytest tutor/tests/visual/test_slide_renderer.py -v` produces PNGs where
the background color is `#0d1117` (or similar dark value), not `#ffffff`.

Manual check: render one slide and open the PNG — it should be dark-themed, not white.

### AC-2 — No literal "None" text in any rendered slide

Inspect rendered PNGs for units with segments that have `body=None`, `left=None`,
`right=None`, `rows=None`, etc. The word "None" must not appear anywhere in the image.

### AC-3 — System font renders legibly

Text in rendered slides must use a proportional sans-serif font (Segoe UI or Helvetica),
not the browser-default Times New Roman. Code blocks must use a monospace font.
Check visually — no automated pixel test required.

### AC-4 — Slide timing sums match unit MP3 duration (within 5%)

For a unit with `n` segments and a `tutorial.timing.json`:
```
sum(exact_duration(seg) for seg in unit_segments)  ≈  unit_mp3_duration  (±5%)
```

Test: `test_timing_gap_accounted()` — see test names below.

### AC-5 — No regressions

`py -m pytest` — all 215+ existing tests green.
`py -m ruff check tutor/` — zero errors.
`py -m ruff format --check tutor/` — zero diffs.

---

## Test Names

Add to `tutor/tests/visual/test_slide_renderer.py`:

```
test_screenshot_uses_file_url_not_set_content   (mock page, assert page.goto called)
test_tmp_file_cleaned_up_after_screenshot       (assert tempfile deleted after render)
```

Add to `tutor/tests/visual/test_beat_timer.py`:

```
test_timing_gap_accounted_in_exact_duration     (n_lines=3, verify += 3 * SILENCE_TURN_MS)
test_single_line_segment_includes_one_gap       (n_lines=1, verify += 1 * SILENCE_TURN_MS)
```

---

## Branch

Continue on `sandbox/day16` — no new branch needed. This spec is an extension of Day 16.

Merge gate before reporting done:

```powershell
py -m pytest
py -m ruff check tutor/
py -m ruff format --check tutor/
```
