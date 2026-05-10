# Day 15 — Segment Slide Renderers

## Goal

Implement Pillow-based renderers for all 9 v3 visual types. Each renderer
produces a 1920×1080 PNG whose content directly reflects the dialogue segment
being spoken at that moment. A progress-dot row in the footer shows the viewer
their position within the unit.

**This day is split across three files** to respect the 400-line limit and enforce
separation of concerns:

| File | Responsibility | ~Lines |
|---|---|---|
| `tutor/visual/slide_draw.py` | 5 new drawing primitives | ~280 total |
| `tutor/visual/slide_compositor_v3.py` | 7 new `compose_*` functions (new file) | ~260 |
| `tutor/visual/slide_compositor.py` | `compose_segment()` dispatcher + `compose_all_v3()` | ~280 |

---

## Done (merge gate)

```powershell
py -m pytest tutor/tests/visual/test_slide_compositor_v3.py -v   # scoped — all green
py -m pytest                                                      # full suite — 0 failures
py -m ruff check tutor/                                           # 0 errors
py -m ruff format --check tutor/                                  # 0 formatting issues
```

Report: list each acceptance criterion below with pass/fail. Paste gate output.
Stop: do not merge to main — wait for human review.

---

## Data boundary

```
Reads:   SlideSegment (in memory, passed from segment_planner)
         VisualSpec   (title card + outro, from plan_visuals)
Writes:  video/<session>/slides/<unit>_<segment>_<type>.png
```

No LLM calls, no audio files, no ffmpeg in any of these three files.

---

## New drawing primitives — `tutor/visual/slide_draw.py`

Add 5 functions to the existing file (currently ~220 lines → ~280 total).
All functions receive a `draw` or `img` object and modify it in place.
No `SlideSegment` logic, no VisualSpec logic here — only pixels.

```python
def draw_progress_dots(
    draw: ImageDraw.ImageDraw,
    current: int,   # 0-based index of the current segment within the unit
    total: int,     # total segments in this unit
) -> None:
    """
    Render a row of dots in the footer bar, left-aligned from CONTENT_LEFT.
    Filled dot (ACCENT_CYAN, radius 6px) = current position.
    Hollow dot (DIVIDER border, BG_CARD fill) = other positions.
    Dot centre-to-centre spacing: 20px. Y centre: FOOTER_BAR_Y + 30.
    If total > 15: render a proportional progress bar (width 200px, height 8px)
    instead of individual dots to avoid overflow.
    """

def draw_two_panel(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    left_label: str,
    right_label: str,
    left_body: str,
    right_body: str,
) -> None:
    """
    Render two equal-width panels separated by a centred ≈ symbol.
    Each panel: rounded rect (BG_CARD fill, DIVIDER border, radius 12px).
    Panel width: (CONTENT_WIDTH - 120) // 2.  Y start: BODY_Y.
    Label: TEXT_PRIMARY 32px bold, top of panel.
    Body: TEXT_SECONDARY 28px, below label, wrapped within panel width.
    ≈ symbol: ACCENT_CYAN 56px, vertically centred between panels.
    Used only by compose_analogy().
    """

def draw_comparison_table(
    draw: ImageDraw.ImageDraw,
    left_label: str,
    right_label: str,
    rows: list[list[str]],
) -> None:
    """
    Render a two-column table starting at BODY_Y.
    Header row: left_label (ACCENT_CYAN, 32px bold) | right_label (ACCENT_AMBER, 32px bold).
    Divider below headers: 1px DIVIDER.
    Data rows: alternating BG_CARD / BG_DEEP background bands.
    Cell text: TEXT_PRIMARY 28px, X padding 20px.
    Row height: 52px. Max 6 data rows; row 7+ replaced by single "…" row.
    Column split at x = CONTENT_LEFT + CONTENT_WIDTH // 2.
    Vertical column divider: 1px DIVIDER.
    """

def draw_speaker_tag(
    draw: ImageDraw.ImageDraw,
    speaker: str,   # "MAYA" | "SAM"
) -> None:
    """
    Render a coloured pill tag near the top-right of the content area.
    MAYA → ACCENT_GREEN background, TEXT_PRIMARY text.
    SAM  → ACCENT_AMBER background, TEXT_PRIMARY text.
    Pill: rounded rect (radius 8px), 26px text, right-aligned at CONTENT_RIGHT - 20,
    Y = TITLE_Y.
    """

def draw_large_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    colour: str,
    font_size: int,
) -> None:
    """
    Render multi-line text centred horizontally and vertically in the content area.
    Content area: y range [BODY_Y, FOOTER_BAR_Y - 20].
    Wraps at CONTENT_WIDTH. Line height: font_size * 1.4.
    """
```

---

## New compositor — `tutor/visual/slide_compositor_v3.py`

New file. Single responsibility: one `compose_*` function per new visual type.
Imports drawing primitives from `slide_draw`; imports constants from `slide_theme`.
No raw Pillow constants defined here.

All 7 functions follow the same skeleton:

```python
def compose_X(seg: SlideSegment, output_path: Path, total: int) -> Path:
    img  = Image.new("RGB", (1920, 1080))
    draw = ImageDraw.Draw(img)
    draw_background(img)
    draw_accent_strip(draw)
    draw_top_bar(draw, seg.unit_index, ...)
    draw_concept_title(draw, seg.title)
    draw_divider(draw)
    # — type-specific content —
    draw_progress_dots(draw, seg.segment_index, total)
    draw_logo(draw)
    img.save(output_path, "PNG")
    return output_path
```

### `compose_definition(seg, output_path, total)`

```
Term name: ACCENT_CYAN, 56px bold, Y = TITLE_Y
Divider:   ACCENT_CYAN, Y = DIVIDER_Y

Definition text: TEXT_PRIMARY 36px, X = CONTENT_LEFT, Y = BODY_Y,
  max width CONTENT_WIDTH, wrapped.

Code block (if seg.code present):
  draw_code_block() at Y = BODY_Y + definition_height + 30
```

### `compose_analogy(seg, output_path, total)`

```
Title: TEXT_SECONDARY 26px, Y = TITLE_Y ("Think of it this way")
draw_two_panel(
    left_label  = seg.left,
    right_label = seg.right,
    left_body   = seg.rows[0][0],   # first entry, left cell
    right_body  = seg.rows[0][1],   # first entry, right cell
)
```

### `compose_comparison(seg, output_path, total)`

```
draw_comparison_table(
    left_label  = seg.left,
    right_label = seg.right,
    rows        = seg.rows,
)
```

### `compose_code_example(seg, output_path, total)`

```
Optional description: TEXT_SECONDARY 28px at BODY_Y if seg.body present.
draw_code_block() at BODY_Y (or BODY_Y + desc_height + 20 if body present).
Full-width code block: width = CONTENT_WIDTH.
Code text colour: TEXT_CODE (#79c0ff).
```

### `compose_question_prompt(seg, output_path, total)`

```
Background: slightly lighter variant — BG_CARD (#161b22) for the full canvas
  (signals MAYA/SAM speaking, not ALEX).
draw_speaker_tag(draw, speaker=_speaker_from_body(seg))
Question text: centred via draw_large_centered_text()
  colour = TEXT_PRIMARY, font_size = 44px, italic weight.
Optional opening quote " in ACCENT_CYAN 80px, X = CONTENT_LEFT, Y = BODY_Y - 60.
```

`_speaker_from_body(seg)` — infer speaker from `seg.title` ("MAYA asks" → "MAYA").

### `compose_decision_guide(seg, output_path, total)`

```
draw_comparison_table(
    left_label  = seg.left,    # e.g. "USE INTERFACE when…"
    right_label = seg.right,   # e.g. "USE ABSTRACT when…"
    rows        = seg.rows,
)
Left header colour override: ACCENT_CYAN (same as comparison default).
Right header colour override: ACCENT_AMBER.
```

### `compose_key_insight(seg, output_path, total)`

```
Body text: draw_large_centered_text()
  colour = ACCENT_AMBER, font_size = 48px bold.
Thin rule below text: 400px wide, ACCENT_CYAN, 2px.
```

---

## Updated compositor — `tutor/visual/slide_compositor.py`

Add `compose_segment()` dispatcher and `compose_all_v3()`.
The 5 existing `compose_*` functions gain an optional `total: int = 0` parameter
for progress dots — callers that omit it get empty dots (backward compatible).

### Dispatcher

```python
from tutor.visual.slide_compositor_v3 import (
    compose_definition, compose_analogy, compose_comparison,
    compose_code_example, compose_question_prompt,
    compose_decision_guide, compose_key_insight,
)

_COMPOSERS: dict[str, Callable] = {
    "hook_question":   compose_hook_slide,
    "definition":      compose_definition,
    "analogy":         compose_analogy,
    "comparison":      compose_comparison,
    "code_example":    compose_code_example,
    "question_prompt": compose_question_prompt,
    "decision_guide":  compose_decision_guide,
    "key_insight":     compose_key_insight,
    "memory_hook":     compose_memory_slide,
}

def compose_segment(seg: SlideSegment, output_path: Path, total: int) -> Path:
    """
    Dispatch to the correct composer. Falls back to compose_key_insight()
    for any unknown visual_type — never raises.
    """
    fn = _COMPOSERS.get(seg.visual_type, compose_key_insight)
    return fn(seg, output_path, total)
```

### `compose_all_v3()`

```python
def compose_all_v3(
    title_spec:       VisualSpec,
    outro_spec:       VisualSpec,
    segments_by_unit: dict[int, list[SlideSegment]],
    output_dir:       Path,
    session_label:    str,
) -> list[Path]:
    """
    Compose all slides for a v3 session in video order:
      [title_card, unit_1_segs…, unit_2_segs…, …, outro]

    For each unit's segments, calls compose_segment() with total = len(unit_segs).
    Populates seg.png_path for every SlideSegment in segments_by_unit.
    Returns the ordered list of PNG paths for the video assembler.
    """
```

---

## Output filenames — v3

```
video/<session>/slides/
  00_title.png
  01_00_hook_question.png     ← unit 01, segment 00
  01_01_definition.png
  01_02_analogy.png
  ...
  01_10_memory_hook.png
  02_00_hook_question.png
  ...
  99_outro.png
```

Pattern: `{unit:02d}_{segment:02d}_{visual_type}.png`

`compose_all_v3()` returns paths in this order — the order that defines the video
timeline for the assembler and beat timer.

---

## Progress dots design

| Property | Value |
|---|---|
| Dot radius | 6 px |
| Dot spacing (centre to centre) | 20 px |
| Y centre | `FOOTER_BAR_Y + 30` |
| X start | `CONTENT_LEFT` |
| Filled (current) colour | `ACCENT_CYAN` |
| Hollow (other) fill | `BG_CARD` |
| Hollow (other) border | `DIVIDER` |
| Fallback if `total > 15` | proportional bar: 200 × 8 px, filled portion in `ACCENT_CYAN` |

Progress dots replace the static memory-hook text that was in the v2 footer.
Memory-hook text now appears only on the `memory_hook` slide type itself.

---

## Acceptance criteria

- [ ] All 9 visual types (including hook_question and memory_hook) produce valid 1920×1080 PNGs
- [ ] `compose_segment()` handles unknown visual_type without raising
- [ ] Progress dots correct: filled dot at `seg.segment_index`, hollow elsewhere
- [ ] `compose_comparison()` truncates rows beyond 6 with a "…" row
- [ ] `compose_code_example()` renders code in `TEXT_CODE` colour, monospace font
- [ ] `compose_question_prompt()` renders speaker tag (MAYA/SAM) with correct colour
- [ ] `compose_all_v3()` populates `seg.png_path` on every input segment
- [ ] `compose_all_v3()` returns title + all segment PNGs + outro in correct order
- [ ] Output files written to `video/<session>/slides/`, not `audio/<session>/slides/`
- [ ] `slide_compositor.py` stays under 400 lines
- [ ] `slide_compositor_v3.py` stays under 400 lines
- [ ] `slide_draw.py` stays under 400 lines
- [ ] No file defines raw Pillow constants — all colours and sizes via `slide_theme`
- [ ] Existing `compose_all()` (v2 caller) still works — no regression

## Tests — `tutor/tests/visual/test_slide_compositor_v3.py`

New test file.

- `test_definition_slide_is_1920x1080`
- `test_analogy_slide_renders_without_error`
- `test_comparison_slide_six_rows_max` — 7 rows → 6 + "…" row
- `test_code_example_renders_code_block`
- `test_question_prompt_renders_speaker_tag` — pixel at expected tag position is ACCENT_GREEN
- `test_decision_guide_renders_two_columns`
- `test_key_insight_large_text_centred`
- `test_compose_segment_unknown_type_falls_back_to_key_insight`
- `test_progress_dots_filled_at_current_index` — pixel check at expected dot position
- `test_compose_all_v3_output_count` — 2 units × 10 segments + title + outro = 22 PNGs
- `test_compose_all_v3_populates_png_path` — all segs have non-empty png_path after call
- `test_compose_all_v3_file_order` — first path is title, last is outro
