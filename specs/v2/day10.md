# Day 10 — Slide Compositor

## Goal

Compose every slide type into a 1920×1080 PNG using Pillow. The result must look
like a professional presentation. Every pixel position, font size, colour, and
spacing is defined in this spec. Output goes to `video/<session>/slides/`.

**This module is split across three files** to stay under the 400-line limit:

| File | Responsibility | ~Lines |
|---|---|---|
| `tutor/visual/slide_theme.py` | Colour palette, spacing grid, font loading | ~120 |
| `tutor/visual/slide_draw.py` | Primitive drawing functions (`_draw_*`) | ~220 |
| `tutor/visual/slide_compositor.py` | Public `compose_*` functions | ~250 |

---

## Data boundary

```
Reads:   VisualSpec (in memory), diagram PNG paths (from Day 9)
Writes:  video/<session>/slides/*.png
```

No audio files, no MP3s, no LLM calls in any of these three files.

---

## Design system

### Canvas

| Property | Value |
|---|---|
| Resolution | 1920 × 1080 px |
| Aspect ratio | 16:9 |
| Colour space | RGB |
| Format | PNG (lossless) |

### Colour palette — `slide_theme.py`

```python
BG_DEEP          = "#0d1117"   # main background
BG_CARD          = "#161b22"   # code blocks, footer bar
BG_ACCENT_STRIP  = "#00b4d8"   # left accent strip (8px, all slides)
TEXT_PRIMARY     = "#e6edf3"   # headings, bullet text
TEXT_SECONDARY   = "#8b949e"   # unit counter, captions
TEXT_CODE        = "#79c0ff"   # code inside code blocks
ACCENT_CYAN      = "#00b4d8"   # dividers, borders
ACCENT_GREEN     = "#3fb950"   # correct / memory hook label
ACCENT_AMBER     = "#e3b341"   # memory hook text, hook question
ACCENT_RED       = "#f85149"   # wrong / error patterns
DIVIDER          = "#30363d"   # horizontal rule
```

### Typography

Fonts loaded from `tutor/assets/fonts/`:

| File | Usage |
|---|---|
| `Inter-Regular.ttf` | Body text, bullets, captions |
| `Inter-Bold.ttf` | Title, concept name, labels |
| `JetBrainsMono-Regular.ttf` | Code snippets |
| `JetBrainsMono-Bold.ttf` | Code block headers |

Both are open-source (SIL OFL). They must be committed to the repo.

**Fallback chain** (if bundled fonts not found):
```python
FONT_SANS_FALLBACK = ["Segoe UI", "Arial", "DejaVu Sans"]
FONT_MONO_FALLBACK = ["Consolas", "Courier New", "DejaVu Sans Mono"]
```

### Font size scale (px)

| Role | Size | Weight |
|---|---|---|
| Document title (title card) | 80 | Bold |
| Unit concept name | 64 | Bold |
| Hook question | 44 | Regular |
| Bullet text | 38 | Regular |
| Code text | 28 | Regular mono |
| Memory hook | 52 | Bold |
| Memory hook label | 24 | Regular |
| Unit counter | 26 | Regular |
| Caption / secondary | 24 | Regular |
| Minimum on-screen | 24 | — |

### Spacing grid — `slide_theme.py`

```python
MARGIN            = 80    # all four edges safe area
ACCENT_STRIP_W    = 8     # left cyan stripe width
CONTENT_LEFT      = 108   # MARGIN + ACCENT_STRIP_W + 20
CONTENT_RIGHT     = 1840  # 1920 - MARGIN
CONTENT_WIDTH     = 1732  # CONTENT_RIGHT - CONTENT_LEFT
TITLE_Y           = 80    # top of concept name
DIVIDER_Y         = 180   # horizontal rule under concept name
BODY_Y            = 210   # first bullet / hook question
FOOTER_BAR_H      = 80    # height of bottom bar
FOOTER_BAR_Y      = 1000  # 1080 - FOOTER_BAR_H
BULLET_LEAD       = 52    # vertical gap between bullets
LINE_HEIGHT_BODY  = 48    # wrapped text line height
DIAGRAM_X         = 1060  # left edge of diagram area
DIAGRAM_Y         = 210   # top of diagram area
DIAGRAM_W         = 780   # max diagram width
DIAGRAM_H         = 680   # max diagram height
BULLET_AREA_W     = 900   # bullet width when diagram present
BULLET_AREA_W_FULL = 1732 # bullet width when no diagram
```

---

## Module A — `tutor/visual/slide_theme.py`

Contains only: colour constants, spacing constants, `_load_font()`, and
`wrap_text()`. No Pillow Image/Draw objects created here.

```python
def _load_font(name: str, size: int, bold: bool = False) -> ImageFont:
    """
    Try bundled TTF first, then walk FONT_SANS_FALLBACK or FONT_MONO_FALLBACK.
    Never raises — falls back to Pillow's built-in bitmap font as last resort.
    """

def wrap_text(draw: ImageDraw, text: str, font: ImageFont, max_width: int) -> list[str]:
    """Split text into lines that each fit within max_width pixels."""
```

---

## Module B — `tutor/visual/slide_draw.py`

Contains only primitive drawing functions. Each function receives a `draw`
(ImageDraw) or `img` (Image) and modifies it in place. No VisualSpec logic here.
Imports from `slide_theme` for constants and font loading.

```python
def draw_background(img: Image.Image, colour: str = BG_DEEP) -> None:
def draw_accent_strip(draw: ImageDraw.ImageDraw, colour: str = ACCENT_CYAN) -> None:
def draw_top_bar(draw: ImageDraw.ImageDraw, unit_idx: int, total: int) -> None:
def draw_footer_bar(draw: ImageDraw.ImageDraw, memory_hook: str) -> None:
def draw_concept_title(draw: ImageDraw.ImageDraw, text: str) -> None:
def draw_divider(draw: ImageDraw.ImageDraw, colour: str = ACCENT_CYAN) -> None:
def draw_bullets(
    draw: ImageDraw.ImageDraw,
    points: list[str],
    x: int,
    y: int,
    max_w: int,
) -> int:
    """Draw bullet points. Returns y position after last bullet."""

def draw_code_block(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    code: str,
    y_start: int,
) -> int:
    """Draw rounded code block. Returns y position after block."""

def paste_diagram(img: Image.Image, diagram_path: Path) -> None:
    """Paste diagram PNG at DIAGRAM_X/DIAGRAM_Y, scaled to fit DIAGRAM_W × DIAGRAM_H."""

def draw_logo(draw: ImageDraw.ImageDraw) -> None:
    """Draw 'LX' rounded rectangle at top-right corner."""
```

---

## Module C — `tutor/visual/slide_compositor.py`

Contains the public API. Imports draw primitives from `slide_draw` and constants
from `slide_theme`. No raw drawing constants defined here.

```python
def compose_all(
    visuals: list[VisualSpec],
    diagram_pngs: dict[int, Path],
    output_dir: Path,
    session_label: str,
) -> list[Path]:
    """Compose all slides. Returns ordered list of PNG paths."""

def compose_title_card(spec: VisualSpec, output_path: Path) -> Path:
def compose_hook_slide(spec: VisualSpec, output_path: Path) -> Path:
def compose_concept_slide(
    spec: VisualSpec,
    diagram_png: Path | None,
    output_path: Path,
) -> Path:
def compose_memory_slide(spec: VisualSpec, output_path: Path) -> Path:
def compose_outro_card(spec: VisualSpec, output_path: Path) -> Path:
```

Every `compose_*` function follows the same pattern:
```python
def compose_hook_slide(spec, output_path):
    img = Image.new("RGB", (1920, 1080))
    draw = ImageDraw.Draw(img)
    draw_background(img)
    draw_accent_strip(draw)
    draw_top_bar(draw, spec.unit_index, total_units)
    draw_concept_title(draw, spec.concept)
    draw_divider(draw)
    # slide-specific content ...
    draw_footer_bar(draw, spec.memory_hook)
    draw_logo(draw)
    img.save(output_path, "PNG")
    return output_path
```

---

## Slide types

### 1 — Title card

```
Background: BG_DEEP
Accent strip: full height, ACCENT_CYAN

Vertical centre (±30px):
  LearnX logo: 120×120px, centred horizontally, Y offset -180 from centre
  Document title: TEXT_PRIMARY, 80px bold, centred, Y offset -40 from centre
  Thin divider: 600px wide, ACCENT_CYAN, 2px, centred, Y offset +10 from centre
  Subtitle: TEXT_SECONDARY, 32px, centred, Y offset +60 from centre

Bottom-left: "week2/3.md" in TEXT_SECONDARY, 22px, X=CONTENT_LEFT, Y=FOOTER_BAR_Y+28
Bottom-right: "LearnX v2" in TEXT_SECONDARY, 22px
```

### 2 — Hook slide

```
Accent strip: full height, ACCENT_CYAN
Top bar: "UNIT N / M" in TEXT_SECONDARY 26px, right-aligned logo

Decorative "?" glyph: ACCENT_AMBER, 200px bold, X=1700, Y=150, alpha=60

Concept name: TEXT_PRIMARY, 64px bold, X=CONTENT_LEFT, Y=TITLE_Y
Divider: 1px ACCENT_CYAN, Y=DIVIDER_Y

Hook question: ACCENT_AMBER, 44px regular
  X=CONTENT_LEFT, Y=BODY_Y, max width=CONTENT_WIDTH
  Prefix: open-quote " in ACCENT_CYAN, 56px

Footer bar: BG_CARD
  Left: ⬡ in ACCENT_GREEN (20px) + memory_hook in TEXT_PRIMARY 38px bold
```

### 3 — Concept slide

```
Accent strip, top bar: same as hook slide

Concept name: TEXT_PRIMARY, 64px bold, Y=TITLE_Y
Divider: 1px ACCENT_CYAN, Y=DIVIDER_Y

Bullet area (diagram present):  X=CONTENT_LEFT, Y=BODY_Y, width=BULLET_AREA_W
Bullet area (no diagram):       X=CONTENT_LEFT, Y=BODY_Y, width=BULLET_AREA_W_FULL

Each bullet:
  Leader "•" in ACCENT_CYAN, 38px, X=CONTENT_LEFT
  Text: TEXT_PRIMARY, 38px, X=CONTENT_LEFT+36, wrapped at area width-36
  Vertical gap: BULLET_LEAD (52px)
  Max 5 bullets; 6th+ truncated with "…"

Code block (optional, below bullets):
  Background: BG_CARD rounded rect (radius 8px), 1px DIVIDER border
  Left indicator: 4px ACCENT_CYAN strip
  Header: "Java" in TEXT_SECONDARY, 22px, top-right of block
  Code text: JetBrains Mono 26px, TEXT_CODE
  Padding: 20px all sides. Max height: 200px

Diagram area (when present):
  X=DIAGRAM_X, Y=DIAGRAM_Y
  Scaled to fit DIAGRAM_W × DIAGRAM_H, preserving aspect ratio (LANCZOS)
  Centred within the bounding box

Footer bar: same as hook slide
```

### 4 — Memory hook slide

```
Background: BG_DEEP
Accent strip: full height, ACCENT_AMBER (not cyan — warmth signals closing)

Top bar: "UNIT N / M — REMEMBER THIS", TEXT_SECONDARY 26px

Decorative "✓" glyph: ACCENT_GREEN, 160px, X=1700, Y=100, alpha=80

Concept name: TEXT_PRIMARY, 64px bold, Y=TITLE_Y
Divider: 1px ACCENT_AMBER, Y=DIVIDER_Y

Memory hook text:
  ACCENT_AMBER, 52px bold, centred horizontally
  Y = vertical centre between DIVIDER_Y and FOOTER_BAR_Y
  Max width: CONTENT_WIDTH. Wrap to 2 lines if needed (line height 70px)
  Prefix: open quote " in ACCENT_CYAN, 64px, X=CONTENT_LEFT-10

Summary bullets (below memory hook, if space allows):
  All key_points, 30px, TEXT_SECONDARY, gap 40px, max 3 shown

Footer bar: BG_CARD, 4px ACCENT_GREEN left accent
  "📌 Pin this" in ACCENT_GREEN, 22px, left
  Analogy in TEXT_SECONDARY, italic, 26px, right side
```

### 5 — Outro card

```
Background: BG_DEEP
Accent strip: full height, ACCENT_CYAN

Centre layout:
  "Session Complete" — TEXT_PRIMARY, 72px bold, centred, Y=220
  Divider — ACCENT_CYAN, 400px wide, centred, Y=316
  Session stats — TEXT_SECONDARY, 30px, centred, Y=340

Memory hooks list (Y=420):
  "What to remember:" — ACCENT_GREEN, 28px bold, centred
  Each hook: ACCENT_AMBER, 34px, centred, spaced 56px apart, "—" prefix

Bottom:
  "LearnX" wordmark — TEXT_SECONDARY, 28px, centred
  "video/<session>/" path — TEXT_SECONDARY, 20px, centred, Y=960
```

---

## Output filenames

Pattern: zero-padded two-digit unit index.

```
video/<session>/slides/
  00_title.png
  01_hook.png
  01_concept.png
  01_memory.png
  02_hook.png
  02_concept.png
  02_memory.png
  ...
  99_outro.png
```

`compose_all()` returns the list in this order — it defines the slide order for
the video assembler.

---

## Acceptance criteria

- [ ] All 5 slide types render without error
- [ ] Every output is exactly 1920×1080px RGB PNG
- [ ] Output written to `video/<session>/slides/`, not `audio/<session>/slides/`
- [ ] No file in `tutor/visual/` exceeds 400 lines
- [ ] `slide_theme.py` contains only constants and font loading — no draw calls
- [ ] `slide_draw.py` contains only primitives — no VisualSpec logic
- [ ] `slide_compositor.py` contains only compose_* functions — no draw constants
- [ ] Concept name never overflows the title area
- [ ] Bullets wrap correctly and never overlap the diagram area
- [ ] Memory slide uses ACCENT_AMBER accent strip (not cyan)
- [ ] Missing bundled font → graceful fallback, no crash

## Tests — `tutor/tests/visual/test_slide_compositor.py`

- `test_title_card_is_1920x1080`
- `test_concept_slide_with_diagram`
- `test_concept_slide_no_diagram` — bullets fill full width
- `test_bullet_wrap_does_not_overflow` — long text stays within bounds
- `test_memory_slide_uses_amber_strip` — pixel at x=0, y=540 is ACCENT_AMBER
- `test_code_block_rendered_when_snippet_present`
- `test_font_fallback_on_missing_bundled_font` — no crash
- `test_compose_all_returns_correct_count` — N units → 2+3N+1 slides
