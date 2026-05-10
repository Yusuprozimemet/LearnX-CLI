# LearnX v3 — Conversation-Driven Slides

## The problem with v2

v2 treats slides as **chapter markers**: three static PNGs per unit.

| Slide   | Appears at     | Duration            |
| ------- | -------------- | ------------------- |
| hook    | unit start     | ~30 s               |
| concept | after hook     | ~160 s — **frozen** |
| memory  | last ALEX line | ~15 s               |

A 3.5-minute unit has 18–25 dialogue lines covering 3–5 distinct ideas. Every one
of those ideas — definitions, analogies, comparisons, code examples, MAYA's
questions — maps to the same single concept image. The viewer watches a static
bitmap for nearly three minutes while the conversation flows beneath it.

This is not educational video. This is a podcast with a background image.

Two independent failures make this worse:

**Failure 1 — Slide count.** 3 slides is not a structure, it is a minimum. A
3.5-minute unit should have 10–15 slides, each visible for 15–35 seconds, each
directly reflecting the idea being spoken.

**Failure 2 — Timing.** Every timestamp in v2 is estimated by dividing word count
by 130 WPM and adding fixed silence constants on top of a duration-scaling factor.
This inflates every timestamp by 5–15 seconds per unit. The slide transition from
hook → concept can fire 15–20 seconds before MAYA actually speaks.

**Failure 3 — Rendering quality.** Pillow is a bitmap compositor. It draws pixels
with no understanding of typography, layout, or visual hierarchy. Pillow slides look
like terminal output turned into a PNG. Code blocks have no syntax highlighting.
Two-column layouts require hardcoded pixel coordinates. Fonts cannot kern.

v3 fixes all three.

---

## How good educational videos actually work

| Tool / Creator    | How visuals track the narration                                           |
| ----------------- | ------------------------------------------------------------------------- |
| Khan Academy      | Tablet drawing — each shape/label appears the moment it is spoken         |
| 3Blue1Brown       | Animations driven by the script — every visual element tied to a sentence |
| Lumen5 / Pictory  | Each sentence → its own 10–20 s scene with matching image                 |
| Coursera lectures | Slide advances every 20–40 s on average                                   |
| Descript          | Video editing is done by editing the transcript — timeline = text         |

The common principle: **the visual IS the explanation, not a decoration beside it.**

The dialogue script is the source of truth. Every idea in the video is already
written — ALEX's explanations, MAYA's questions, the analogies, the code examples,
the memory hook. v3 turns each spoken idea into its matching visual automatically.

---

## The three fixes

### Fix 1 — More slides, derived from the dialogue

The LLM reads the full dialogue text for each unit and groups consecutive lines into
visual segments. One segment = 1–3 lines covering one idea = one slide. A 3.5-minute
unit produces 10–15 slides, each showing for 15–35 seconds.

The LLM never sees metadata only. It reads ALEX's actual words and assigns the
correct visual type to what ALEX is doing: defining a term, drawing an analogy,
comparing two things, showing code, stating a rule.

### Fix 2 — Exact timing from the audio builder

`audio_builder._concat_with_silence()` already knows the exact duration of every
TTS segment and every silence gap at the moment it stitches them together. This
information is currently discarded. v3 writes it to `tutorial.timing.json` during
assembly. Every downstream step — beat timer, subtitle writer, slide sequencer —
reads exact millisecond offsets from this file instead of estimating from word count.

No Whisper. No new dependencies. The timing is already being computed.

### Fix 3 — HTML/Playwright replaces Pillow

Slides are rendered by a headless Chromium browser (Playwright) from Jinja2 HTML
templates. This gives v3 publication-quality typography, CSS Grid layouts,
syntax-highlighted code via highlight.js, and Mermaid diagrams — all from a single
`render_slide()` function and a folder of HTML templates. Graphviz is removed.

---

## Architecture

```
                       ┌─────────────────────────────────────┐
.md file               │  EXISTING (v1)                      │
   │                   │                                     │
   ▼                   │  ingestion → summarise →            │
chunker ──────────────►│  curriculum → dialogue → TTS        │
                       │       │                             │
                       │       ▼                             │
                       │  tutorial_units/*.mp3               │
                       │  tutorial.units.json                │
                       │  tutorial.script.txt  ◄─────────────┼── dialogue lines
                       └─────────┬───────────────────────────┘
                                 │
                       ┌─────────▼───────────────────────────┐
                       │  v3 CHANGES                         │
                       │                                     │
                       │  audio_builder.py (modified)        │
                       │    _concat_with_silence() emits     │
                       │    timing per line                  │
                       │    → tutorial.timing.json           │
                       │                                     │
                       │  visual_planner.py (rewritten)      │
                       │    reads dialogue lines             │
                       │    LLM assigns SlideSegment per     │
                       │    1–3 line block                   │
                       │    → list[SlideSegment]             │
                       │                                     │
                       │  slide_renderer.py (new)            │
                       │    Jinja2 → HTML                    │
                       │    Playwright screenshot → PNG      │
                       │    → slides/*.png                   │
                       │                                     │
                       │  beat_timer.py (rewritten)          │
                       │    reads tutorial.timing.json       │
                       │    derives exact slide durations    │
                       │                                     │
                       │  subtitle_writer.py (updated)       │
                       │    reads tutorial.timing.json       │
                       │    exact per-line offsets           │
                       │                                     │
                       │  video_assembler.py (UNCHANGED)     │
                       │    same ffmpeg commands as v2       │
                       └─────────────────────────────────────┘
```

---

## The key insight: exact timing already exists in the audio builder

`audio_builder._concat_with_silence()` is where TTS segments are stitched together.
At that exact point, pydub knows:

- `len(AudioSegment.from_mp3(seg.audio_path))` → exact duration of each line in ms
- The exact silence gaps: `SILENCE_BREATH_MS` (same speaker) or `SILENCE_TURN_MS`
  (speaker change)
- The running cursor position

This is thrown away. Writing it to `tutorial.timing.json` during assembly gives
every subsequent step **exact, deterministic, zero-overhead timing** for every line.

```json
{
  "unit_1": [
    {"line_index": 0, "speaker": "ALEX", "start_ms": 0,     "end_ms": 3200},
    {"line_index": 1, "speaker": "ALEX", "start_ms": 3700,  "end_ms": 7100},
    {"line_index": 2, "speaker": "MAYA", "start_ms": 7600,  "end_ms": 9500}
  ],
  "unit_2": [...]
}
```

For sessions generated before v3 (no timing file), the pipeline falls back to
proportional estimation — the same quality as v2, not worse.

---

## The rendering stack

### Why Pillow is the wrong tool for slides

Pillow operates on individual pixels. To render a two-column comparison table you
compute x/y coordinates by hand. To wrap text you implement your own word-wrap loop.
To add code highlighting you tokenise and paint each token separately. There is no
concept of a layout engine, a box model, or a type renderer. The result looks like
what it is: a Python script manually drawing shapes on a canvas.

This matters because slides are the first thing a learner sees. A slide that looks
like terminal output erodes trust in the product.

### Why HTML + Playwright is the right tool

A browser is the world's best document layout engine. CSS Grid and Flexbox handle
two-column layouts with one line each. `font-feature-settings: "liga" 1` gives
ligatures in JetBrains Mono. Mermaid renders flowcharts, class diagrams, and
sequence diagrams from a text string. highlight.js syntax-highlights any language.
Web fonts (Inter, JetBrains Mono) are loaded from a local bundle — no network calls.

Playwright is the Python library for controlling headless Chromium. A screenshot of
a 1920×1080 page takes ~50 ms. For 10–15 slides per unit, that is under 1 second.
Playwright is free, MIT-licensed, and installs with `pip install playwright &&
playwright install chromium` (one-time ~150 MB download).

### Rendering pipeline

```
SlideSegment
  → Jinja2 template (tutor/visual/templates/<type>.html.j2)
    → full HTML string with embedded CSS + JS assets
      → Playwright page.set_content(html)
        → wait for Mermaid / highlight.js if needed
          → page.screenshot(path=output_png)
```

One browser context is opened per `/video` run and reused for all slides. Chromium
startup cost (~300 ms) is paid once.

### Local asset bundling

All JS and CSS assets are committed to `tutor/assets/html/`:

```
tutor/assets/html/
  mermaid.min.js        # mermaid v10, MIT, ~2.4 MB
  highlight.min.js      # highlight.js core, MIT, ~60 KB
  highlight-java.min.js # Java language pack
  highlight-python.min.js
  theme-dark.min.css    # highlight.js dark theme
  fonts/
    Inter-Regular.woff2
    Inter-SemiBold.woff2
    JetBrainsMono-Regular.woff2
```

No CDN. No network calls during rendering. Works offline.

---

## Slide types

Each type maps to one Jinja2 template. All templates share a single base CSS file
(`slide_base.css`) that defines the dark theme, spacing grid, typography scale,
progress dots, and top bar. Individual templates override only what they need.

### `hook_question`

Shown during ALEX's opening hook lines.

```
┌──────────────────────────────────────────────────────┐
│ Unit 2 of 4                                          │  ← top bar
├──────────────────────────────────────────────────────┤
│                                                      │
│  Interface or abstract class — which fits?           │  ← large hook question
│                                                      │
│  WHAT YOU'LL LEARN                                   │
│  → Contracts vs blueprints                           │
│  → When to use each                                  │
│  → The IS-A vs CAN-DO rule                           │
│                                                      │
├──────────────────────────────────────────────────────┤
│  ● ○ ○ ○ ○ ○ ○ ○ ○                    [LEARNX]      │  ← progress dots + logo
└──────────────────────────────────────────────────────┘
```

### `definition`

Shown when ALEX introduces or defines a named term. Includes an optional Mermaid
diagram or code block.

```
┌──────────────────────────────────────────────────────┐
│ Unit 2 · Interface                                   │
├──────────────────────────────────────────────────────┤
│                                                      │
│  INTERFACE                             [cyan badge]  │
│  ────────────────────────────────────────────────── │
│  A contract specifying what a class MUST do,         │
│  without any implementation.                         │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │  interface Animal {                          │   │  ← highlight.js code block
│  │      void speak();                           │   │
│  │  }                                           │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
├──────────────────────────────────────────────────────┤
│  ○ ● ○ ○ ○ ○ ○ ○ ○                    [LEARNX]      │
└──────────────────────────────────────────────────────┘
```

### `analogy`

Shown when ALEX uses "like", "think of", or "imagine".

```
┌──────────────────────────────────────────────────────┐
│ Unit 2 · Think of it this way                        │
├──────────────────────────────────────────────────────┤
│                                                      │
│  ┌──────────────────────┐   ┌──────────────────────┐ │
│  │  Job Description     │ ≈ │  Interface           │ │  ← CSS Grid two-panel
│  │                      │   │                      │ │
│  │  Lists duties.       │   │  Lists methods.      │ │
│  │  Says nothing about  │   │  Says nothing about  │ │
│  │  HOW to do them.     │   │  HOW to implement.   │ │
│  └──────────────────────┘   └──────────────────────┘ │
│                                                      │
├──────────────────────────────────────────────────────┤
│  ○ ○ ● ○ ○ ○ ○ ○ ○                    [LEARNX]      │
└──────────────────────────────────────────────────────┘
```

### `comparison`

Shown when ALEX contrasts two concepts. Two-column table from `rows` data.

```
┌──────────────────────────────────────────────────────┐
│ Unit 2 · Interface vs Abstract Class                 │
├──────────────────────────────────────────────────────┤
│                                                      │
│  INTERFACE              │  ABSTRACT CLASS            │
│  ───────────────────────┼──────────────────────────  │  ← CSS Grid, no pixel math
│  No state               │  Can have fields           │
│  All methods abstract   │  Can have concrete methods │
│  Multiple inheritance   │  Single inheritance only   │
│  Pure contract          │  Partial implementation    │
│                                                      │
├──────────────────────────────────────────────────────┤
│  ○ ○ ○ ● ○ ○ ○ ○ ○                    [LEARNX]      │
└──────────────────────────────────────────────────────┘
```

### `question_prompt`

Shown when MAYA asks a question. Makes the question visible to the learner.

```
┌──────────────────────────────────────────────────────┐
│ Unit 2                                   [MAYA]      │
├──────────────────────────────────────────────────────┤
│                                                      │
│                                                      │
│  "But wait — can't abstract classes                  │
│   do the same thing as interfaces?"                  │
│                                                      │
│                                                      │
├──────────────────────────────────────────────────────┤
│  ○ ○ ○ ○ ● ○ ○ ○ ○                    [LEARNX]      │
└──────────────────────────────────────────────────────┘
```

### `code_example`

Shown when code is being demonstrated. Full-width highlight.js block.

```
┌──────────────────────────────────────────────────────┐
│ Unit 2 · In practice                                 │
├──────────────────────────────────────────────────────┤
│                                                      │
│  // Using interface                                  │
│  interface Drawable { void draw(); }                 │  ← syntax-highlighted
│  class Circle implements Drawable { ... }            │    JetBrains Mono
│  class Square implements Drawable { ... }            │
│                                                      │
│  // Using abstract class                             │
│  abstract class Shape { abstract void draw(); }      │
│  class Circle extends Shape { ... }                  │
│                                                      │
├──────────────────────────────────────────────────────┤
│  ○ ○ ○ ○ ○ ● ○ ○ ○                    [LEARNX]      │
└──────────────────────────────────────────────────────┘
```

### `diagram`

Shown when a structural relationship should be visualised. The LLM outputs a Mermaid
string; Playwright waits for Mermaid to render the SVG before screenshotting.
Replaces Graphviz entirely.

```
┌──────────────────────────────────────────────────────┐
│ Unit 2 · Class relationships                         │
├──────────────────────────────────────────────────────┤
│                                                      │
│        ┌─────────────┐      ┌──────────────┐         │
│        │ «interface» │      │ «abstract»   │         │  ← Mermaid SVG,
│        │  Drawable   │      │   Shape      │         │    rendered in browser
│        └──────┬──────┘      └──────┬───────┘         │
│               │                   │                  │
│         ┌─────┴────┐        ┌──────┴──────┐          │
│         │  Circle  │        │   Circle    │          │
│         └──────────┘        └─────────────┘          │
│                                                      │
├──────────────────────────────────────────────────────┤
│  ○ ○ ○ ○ ○ ○ ● ○ ○                    [LEARNX]      │
└──────────────────────────────────────────────────────┘
```

### `decision_guide`

Shown when ALEX explains when to use which option.

```
┌──────────────────────────────────────────────────────┐
│ Unit 2 · When to use each                            │
├──────────────────────────────────────────────────────┤
│                                                      │
│  USE INTERFACE when…         USE ABSTRACT when…      │
│                                                      │
│  → Unrelated classes share   → Classes share         │
│    a contract                  common code           │
│                                                      │
│  → Multiple inheritance      → You want to           │
│    is needed                   force extension       │
│                                                      │
│  → Pure API definition       → Partial impl ok       │
│                                                      │
├──────────────────────────────────────────────────────┤
│  ○ ○ ○ ○ ○ ○ ○ ● ○                    [LEARNX]      │
└──────────────────────────────────────────────────────┘
```

### `key_insight`

Shown when ALEX states a rule or memorable fact.

```
┌──────────────────────────────────────────────────────┐
│ Unit 2 · The rule                                    │
├──────────────────────────────────────────────────────┤
│                                                      │
│                                                      │
│  If you can say "IS-A" without sharing code —        │
│  use an interface.                                   │
│                                                      │
│                                                      │
├──────────────────────────────────────────────────────┤
│  ○ ○ ○ ○ ○ ○ ○ ○ ●                    [LEARNX]      │
└──────────────────────────────────────────────────────┘
```

### `memory_hook`

Shown during ALEX's closing lines. Large, centred, single statement.

---

## New LLM prompt: read the dialogue, assign slides

The v3 visual planner receives the **full dialogue text** for each unit, not just
metadata.

```
Given this dialogue transcript for a tutorial unit, group consecutive lines
into visual segments. Each segment = 1–3 lines covering one idea = one slide.

For each segment specify:
  - lines_start, lines_end   (inclusive 0-based indices)
  - visual_type              (one of the types listed below)
  - title                    (short header text for the slide, ≤ 8 words)
  - body                     (main content: definition, analogy text, bullet list)
  - code                     (code string if relevant, else null)
  - language                 (highlight.js language id if code present, else null)
  - mermaid                  (Mermaid diagram string if visual_type is "diagram", else null)
  - left / right             (column labels for comparison type, else null)
  - rows                     (for comparison: [[left_cell, right_cell], ...], else null)

Visual types:
  hook_question | definition | analogy | comparison | code_example |
  diagram | question_prompt | decision_guide | key_insight | memory_hook

Assignment rules:
  - Cover every line — no gaps, no overlaps
  - MAYA lines → question_prompt
  - ALEX introducing a named concept → definition
  - ALEX using "like" / "think of" / "imagine" → analogy
  - ALEX contrasting two things → comparison
  - ALEX showing or referencing code → code_example
  - ALEX describing a structural relationship → diagram
  - ALEX stating when-to-use conditions → decision_guide
  - ALEX stating a rule or law → key_insight
  - Last ALEX lines (memory hook) → memory_hook
  - Opening ALEX lines (hook question) → hook_question

Output: JSON array only. No prose, no markdown fences.
```

### Example LLM output

```json
[
  {
    "lines_start": 0,
    "lines_end": 1,
    "visual_type": "hook_question",
    "title": "Interface or abstract class?",
    "body": "Contracts vs blueprints — when does each fit?",
    "code": null,
    "language": null,
    "mermaid": null,
    "left": null,
    "right": null,
    "rows": null
  },
  {
    "lines_start": 2,
    "lines_end": 4,
    "visual_type": "definition",
    "title": "Interface",
    "body": "A contract specifying what a class must do, without any implementation.",
    "code": "interface Animal {\n    void speak();\n}",
    "language": "java",
    "mermaid": null,
    "left": null,
    "right": null,
    "rows": null
  },
  {
    "lines_start": 5,
    "lines_end": 6,
    "visual_type": "analogy",
    "title": "Think of it this way",
    "body": "Job description lists duties without saying how. Interface lists methods without saying how.",
    "code": null,
    "language": null,
    "mermaid": null,
    "left": null,
    "right": null,
    "rows": null
  },
  {
    "lines_start": 7,
    "lines_end": 7,
    "visual_type": "question_prompt",
    "title": "MAYA asks",
    "body": "Can't abstract classes do the same thing as interfaces?",
    "code": null,
    "language": null,
    "mermaid": null,
    "left": null,
    "right": null,
    "rows": null
  },
  {
    "lines_start": 8,
    "lines_end": 10,
    "visual_type": "definition",
    "title": "Abstract Class",
    "body": "A partial blueprint: shared code plus required extensions.",
    "code": null,
    "language": null,
    "mermaid": null,
    "left": null,
    "right": null,
    "rows": null
  },
  {
    "lines_start": 11,
    "lines_end": 11,
    "visual_type": "diagram",
    "title": "Class relationships",
    "body": null,
    "code": null,
    "language": null,
    "mermaid": "classDiagram\n  class Drawable { <<interface>> draw() }\n  class Shape { <<abstract>> draw()* }\n  Circle ..|> Drawable\n  Circle --|> Shape",
    "left": null,
    "right": null,
    "rows": null
  },
  {
    "lines_start": 12,
    "lines_end": 13,
    "visual_type": "comparison",
    "title": "Interface vs Abstract Class",
    "body": null,
    "code": null,
    "language": null,
    "mermaid": null,
    "left": "Interface",
    "right": "Abstract Class",
    "rows": [
      ["No state", "Can have fields"],
      ["All methods abstract", "Can have concrete methods"],
      ["Multiple inheritance", "Single inheritance only"]
    ]
  },
  {
    "lines_start": 14,
    "lines_end": 15,
    "visual_type": "code_example",
    "title": "In practice",
    "body": null,
    "code": "interface Drawable { void draw(); }\nclass Circle implements Drawable {\n    public void draw() { ... }\n}",
    "language": "java",
    "mermaid": null,
    "left": null,
    "right": null,
    "rows": null
  },
  {
    "lines_start": 16,
    "lines_end": 17,
    "visual_type": "decision_guide",
    "title": "When to use each",
    "body": "Interface: unrelated classes share a contract. Abstract: classes share implementation.",
    "code": null,
    "language": null,
    "mermaid": null,
    "left": null,
    "right": null,
    "rows": null
  },
  {
    "lines_start": 18,
    "lines_end": 19,
    "visual_type": "key_insight",
    "title": "The rule",
    "body": "If you can say IS-A without sharing code — use an interface.",
    "code": null,
    "language": null,
    "mermaid": null,
    "left": null,
    "right": null,
    "rows": null
  },
  {
    "lines_start": 20,
    "lines_end": 21,
    "visual_type": "memory_hook",
    "title": "Remember",
    "body": "Interface = contract. Abstract class = blueprint.",
    "code": null,
    "language": null,
    "mermaid": null,
    "left": null,
    "right": null,
    "rows": null
  }
]
```

10 slides. Average 21 s each for a 3.5-minute unit.

---

## File size discipline

Every Python file in the v3 visual pipeline must stay under 400 lines.
Files that would exceed this are split at clear conceptual boundaries:

| Day 13 — Audio builder modification | in-place edit                                                                   |
| ----------------------------------- | ------------------------------------------------------------------------------- |
| `audio_builder.py`                  | `_concat_with_silence()` modified; `_write_timing_json()` added (~30 new lines) |

| Day 14 — Visual planner | single file                                                                         |
| ----------------------- | ----------------------------------------------------------------------------------- |
| `visual_planner.py`     | `plan_segments()` replaces `_plan_unit()`; cache logic unchanged (~280 lines total) |

| Day 15 — Slide renderer | split into renderer + templates                                                |
| ----------------------- | ------------------------------------------------------------------------------ |
| `slide_renderer.py`     | `render_all_slides()`, `_render_html()` — Playwright lifecycle (~150 lines)    |
| `templates/`            | one `.html.j2` per visual type; `_base.html.j2` shared layout (~30 lines each) |
| `assets/html/`          | CSS, JS, and font files — committed, not generated                             |

| Day 16 — Beat timer + subtitle writer | in-place rewrites                                                         |
| ------------------------------------- | ------------------------------------------------------------------------- |
| `beat_timer.py`                       | `compute_slide_timings()` rewritten; fallback path preserved (~130 lines) |
| `subtitle_writer.py`                  | `get_line_start_offsets()` updated; fallback path preserved (~120 lines)  |
| `__init__.py`                         | `run_visual_pipeline()` updated call order (~160 lines)                   |

---

## Implementation plan

### Day 13 — Exact timing from the audio builder

**File:** `tutor/audio/audio_builder.py`

Modify `_concat_with_silence()` to build a timing list alongside the audio:

```python
def _concat_with_silence(segments: list[AudioSegment]) -> tuple[AudioSegment, list[dict]]:
    result = AudioSegment.empty()
    timing: list[dict] = []
    cursor_ms = 0
    prev_speaker: str | None = None

    for i, seg in enumerate(segments):
        audio = AudioSegment.from_mp3(seg.audio_path)

        if prev_speaker is None:
            gap = 0
        elif prev_speaker == seg.line.speaker:
            gap = SILENCE_BREATH_MS
        else:
            gap = SILENCE_TURN_MS

        cursor_ms += gap
        if gap:
            result += AudioSegment.silent(duration=gap)

        timing.append({
            "line_index": i,
            "speaker":    seg.line.speaker,
            "start_ms":   cursor_ms,
            "end_ms":     cursor_ms + len(audio),
        })
        result += audio
        cursor_ms += len(audio)
        prev_speaker = seg.line.speaker

    return result, timing
```

`_assemble()` collects the timing list for each unit and writes
`tutorial.timing.json` to the audio session directory once assembly is complete.

```json
{
  "unit_1": [...],
  "unit_2": [...]
}
```

**Impact:** `subtitle_writer`, `beat_timer`, and the slide renderer all read from
this file. Word-count estimation is retired for new sessions.

**Backward compatibility:** if `tutorial.timing.json` is absent (session generated
before Day 13), every downstream step falls back to proportional estimation — v2
quality, not worse.

---

### Day 14 — Dialogue-aware visual planner

**File:** `tutor/models.py`

Add `SlideSegment` dataclass alongside the existing `VisualSpec`:

```python
@dataclass
class SlideSegment:
    unit_index:  int
    lines_start: int           # 0-based index into unit dialogue lines
    lines_end:   int
    visual_type: str           # hook_question | definition | analogy | ...
    title:       str
    body:        str | None
    code:        str | None
    language:    str | None    # highlight.js language id
    mermaid:     str | None    # Mermaid diagram string
    left:        str | None    # comparison column label
    right:       str | None
    rows:        list | None   # [[left_cell, right_cell], ...]
    png_path:    str = ""      # filled in by slide_renderer
```

`VisualSpec` is kept unchanged — title card and outro still use it.

**File:** `tutor/generation/visual_planner.py`

Replace `_plan_unit()` with `plan_segments(unit, dialogue_lines, llm_fn)`:

- Input: `unit: TeachingUnit` + `dialogue_lines: list[DialogueLine]` for that unit
- Output: `list[SlideSegment]`
- Prompt template: `tutor/prompts/visual_v3.txt` (the dialogue-aware prompt above)
- Cache key: `sha256(unit.concept + "".join(l.text for l in dialogue_lines))`
- Validation: assert every line index 0..N-1 is covered exactly once; re-prompt once
  on failure before raising `VideoError`

**File:** `tutor/visual/__init__.py`

`run_visual_pipeline()` loads `tutorial.timing.json` if present and passes dialogue
lines into `plan_segments()` for each unit.

---

### Day 15 — HTML templates and slide renderer

#### 15a — Asset bundle

Commit to `tutor/assets/html/`:

```
mermaid.min.js            # mermaid v10, MIT
highlight.min.js          # highlight.js core, MIT
highlight-java.min.js
highlight-python.min.js
highlight-javascript.min.js
highlight-typescript.min.js
theme-learnx-dark.css     # custom highlight.js theme matching LearnX palette
slide_base.css            # shared layout: dark bg, top bar, progress dots, footer
fonts/
  Inter-Regular.woff2
  Inter-SemiBold.woff2
  Inter-Bold.woff2
  JetBrainsMono-Regular.woff2
```

All assets are loaded via `file://` URI from absolute paths so the page renders
without a network connection.

#### 15b — Jinja2 templates

**Directory:** `tutor/visual/templates/`

One `.html.j2` file per visual type. Each template extends `_base.html.j2`.

`_base.html.j2` defines:

- CSS custom properties (colour palette, spacing scale, font stack)
- Top bar (`Unit N · {{ title }}`)
- Progress dots footer (`{{ current_dot }}` of `{{ total_dots }}`)
- LearnX logo (bottom-right, base64-embedded PNG)
- `<link>` for `slide_base.css`
- `<script>` tags for highlight.js and mermaid.min.js loaded from `file://`

Each child template uses `{% block content %}` for its body.

Examples:

```jinja2
{# templates/definition.html.j2 #}
{% extends "_base.html.j2" %}
{% block content %}
<div class="definition-slide">
  <span class="badge badge--{{ seg.visual_type }}">{{ seg.visual_type | upper }}</span>
  <h2>{{ seg.title }}</h2>
  <p class="body-text">{{ seg.body }}</p>
  {% if seg.code %}
  <pre><code class="language-{{ seg.language or 'java' }}">{{ seg.code | e }}</code></pre>
  {% endif %}
</div>
{% endblock %}
```

```jinja2
{# templates/comparison.html.j2 #}
{% extends "_base.html.j2" %}
{% block content %}
<div class="comparison-slide">
  <div class="col col--left">
    <h3>{{ seg.left }}</h3>
    {% for row in seg.rows %}<div class="cell">{{ row[0] }}</div>{% endfor %}
  </div>
  <div class="divider"></div>
  <div class="col col--right">
    <h3>{{ seg.right }}</h3>
    {% for row in seg.rows %}<div class="cell">{{ row[1] }}</div>{% endfor %}
  </div>
</div>
{% endblock %}
```

```jinja2
{# templates/diagram.html.j2 #}
{% extends "_base.html.j2" %}
{% block content %}
<div class="diagram-slide">
  <div class="mermaid">{{ seg.mermaid }}</div>
</div>
{% endblock %}
```

#### 15c — Slide renderer

**File:** `tutor/visual/slide_renderer.py`

```python
from playwright.sync_api import sync_playwright, Browser
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from tutor.models import SlideSegment

TEMPLATE_DIR = Path(__file__).parent / "templates"
ASSET_DIR    = Path(__file__).parent.parent / "assets" / "html"
ENV = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=False)

MIN_SLIDE_DURATION_MS = 3_000


def render_all_slides(
    segments: list[SlideSegment],
    output_dir: Path,
    total_slides: int,
) -> list[SlideSegment]:
    """Render all segments to PNG. Returns segments with png_path filled."""
    with sync_playwright() as pw:
        browser: Browser = pw.chromium.launch()
        page = browser.new_page()
        page.set_viewport_size({"width": 1920, "height": 1080})

        for i, seg in enumerate(segments):
            html = _render_html(seg, current_dot=i + 1, total_dots=total_slides)
            page.set_content(html, wait_until="domcontentloaded")

            if seg.mermaid:
                page.wait_for_function(
                    "() => document.querySelector('.mermaid svg') !== null",
                    timeout=10_000,
                )
            if seg.code:
                page.wait_for_function(
                    "() => document.querySelector('pre code.hljs') !== null",
                    timeout=5_000,
                )

            out = output_dir / f"slide_{i:03d}_{seg.visual_type}.png"
            page.screenshot(path=str(out), full_page=False)
            seg.png_path = str(out)

        browser.close()
    return segments


def _render_html(seg: SlideSegment, current_dot: int, total_dots: int) -> str:
    template = ENV.get_template(f"{seg.visual_type}.html.j2")
    return template.render(seg=seg, current_dot=current_dot, total_dots=total_dots,
                           asset_dir=ASSET_DIR.as_uri())
```

**No Graphviz calls anywhere in this file.** `diagram_renderer.py` is retired.
`slide_compositor.py`, `slide_draw.py`, and `slide_theme.py` are removed (their
responsibilities move to CSS + templates).

---

### Day 16 — Beat timer rewrite and full integration

**File:** `tutor/visual/beat_timer.py`

`compute_slide_timings()` is rewritten to accept `list[SlideSegment]` and the
timing dict loaded from `tutorial.timing.json`:

```python
def compute_slide_timings(
    segments: list[SlideSegment],
    timing: dict | None,
    unit_key: str,
    unit_duration_s: float,
) -> list[tuple[str, float]]:
    result = []
    unit_timing = timing.get(unit_key) if timing else None

    for seg in segments:
        if unit_timing:
            start_ms = unit_timing[seg.lines_start]["start_ms"]
            end_ms   = unit_timing[seg.lines_end]["end_ms"]
            dur_s    = max((end_ms - start_ms) / 1000.0, MIN_SLIDE_DURATION_S)
        else:
            dur_s = _proportional_fallback(seg, unit_duration_s, len(segments))

        result.append((seg.png_path, dur_s))

    return result
```

**File:** `tutor/visual/subtitle_writer.py`

`get_line_start_offsets()` is updated to accept the timing dict:

```python
def get_line_start_offsets(
    dialogue_lines: list[DialogueLine],
    timing: dict | None,
    unit_key: str,
) -> list[float]:
    if timing and unit_key in timing:
        return [entry["start_ms"] / 1000.0 for entry in timing[unit_key]]
    return _compute_timing_fallback(dialogue_lines)   # v2 estimation
```

**File:** `tutor/visual/__init__.py`

`run_visual_pipeline()` updated call order:

1. Load `tutorial.timing.json` if present (None otherwise)
2. For each unit: call `plan_segments()` → `list[SlideSegment]`
3. Call `render_all_slides()` → PNGs written to `video/<session>/slides/`
4. Call `compute_slide_timings()` per unit → durations
5. Call `get_line_start_offsets()` → subtitle SRT
6. `video_assembler.py` — unchanged ffmpeg commands

**File:** `tutor/visual/video_assembler.py` — **no changes required.** The assembler
already accepts `(png_path, duration_s)` tuples from `beat_timer`. It does not care
whether those tuples came from Pillow PNGs or Playwright PNGs.

---

## Dependency changes

### Added

| Package      | Purpose                          | Install                  |
| ------------ | -------------------------------- | ------------------------ |
| `playwright` | Headless Chromium for HTML → PNG | `pip install playwright` |
| `jinja2`     | HTML template rendering          | `pip install jinja2`     |

One-time Chromium setup: `playwright install chromium` (~150 MB, cached).

Add to `pyproject.toml` under `[project.dependencies]`:

```toml
"playwright>=1.44",
"jinja2>=3.1",
```

Add `playwright install chromium` to the CI workflow (`ci.yml`) under setup steps.

### Removed

| Package             | Was used for             | Removal                               |
| ------------------- | ------------------------ | ------------------------------------- |
| `graphviz` (system) | DOT → PNG via subprocess | Remove from README setup instructions |
| `graphviz` (Python) | Python bindings          | Remove from `pyproject.toml`          |

`diagram_renderer.py` is deleted. `slide_compositor.py`, `slide_draw.py`, and
`slide_theme.py` are deleted. Their test files are deleted or repurposed.

---

## File layout after v3

```
tutor/
  generation/
    visual_planner.py       ← rewritten (Day 14) — dialogue-aware
  visual/
    __init__.py             ← updated (Day 16)
    slide_renderer.py       ← new (Day 15) — Playwright + Jinja2
    beat_timer.py           ← rewritten (Day 16) — timing.json aware
    subtitle_writer.py      ← updated (Day 16) — timing.json aware
    video_assembler.py      ← UNCHANGED
    templates/
      _base.html.j2
      hook_question.html.j2
      definition.html.j2
      analogy.html.j2
      comparison.html.j2
      code_example.html.j2
      diagram.html.j2
      question_prompt.html.j2
      decision_guide.html.j2
      key_insight.html.j2
      memory_hook.html.j2
  audio/
    audio_builder.py        ← modified (Day 13) — emits tutorial.timing.json
  assets/
    html/
      mermaid.min.js
      highlight.min.js
      highlight-java.min.js
      highlight-python.min.js
      theme-learnx-dark.css
      slide_base.css
      fonts/
        Inter-Regular.woff2
        Inter-SemiBold.woff2
        Inter-Bold.woff2
        JetBrainsMono-Regular.woff2
  models.py                 ← SlideSegment added (Day 14)
  prompts/
    visual_v3.txt           ← new (Day 14) — dialogue-aware prompt

audio/<session>/
  tutorial.timing.json      ← new (Day 13)

video/<session>/
  slides/
    slide_000_hook_question.png
    slide_001_definition.png
    ...
  full_session.mp4
  subtitles.srt
  tutorial.visuals.json     ← title card + outro (VisualSpec, unchanged)
```

Files deleted in v3:

```
tutor/visual/diagram_renderer.py    ← deleted (Graphviz retired)
tutor/visual/slide_compositor.py    ← deleted (Pillow retired)
tutor/visual/slide_draw.py          ← deleted
tutor/visual/slide_theme.py         ← deleted
tutor/prompts/visual_v2.txt         ← deleted (replaced by visual_v3.txt)
```

---

## What does NOT change

- `/generate`, the audio player, Q&A engine — untouched
- The 5-stage pipeline structure (plan → render → time → subtitle → assemble)
- The title card and outro (still `VisualSpec`-driven)
- `video_assembler.py` — ffmpeg commands are identical
- Shell commands `/video` and `/vsessions` — no changes
- `tutorial.units.json`, `tutorial.script.txt`, all v1 outputs — unchanged

---

## What this does NOT do

- **No real-time animation** — slides are stills; CSS transitions and ff

| Risk                          | Likelihood                    | Mitigation                                                                     |
| ----------------------------- | ----------------------------- | ------------------------------------------------------------------------------ |
| LLM generates invalid Mermaid | Medium                        | Catch render timeout; fall back to `key_insight` slide with body text          |
| LLM leaves lines uncovered    | Low-Medium                    | Validate coverage; re-prompt once before raising `VideoError`                  |
| Playwright not installed      | Low                           | Clear error message with install command; `_check_playwright()` in `config.py` |
| Chromium binary missing       | Low                           | `playwright install chromium` added to CI and README                           |
| Font file missing             | Very low                      | Fonts committed to `tutor/assets/html/fonts/`; no network fetch                |
| Mermaid render timeout        | Low                           | 10 s timeout; fallback to `diagram_error.html.j2`                              |
| Screenshot speed regression   | Very low                      | ~50 ms/slide × 12 slides = ~600 ms per unit; acceptable                        |
| Sessions without timing.json  | Certain for existing sessions | Fallback to v2 estimation; same quality as before                              |

---

## Summary: what v3 delivers

|                            | v2                             | v3                                                  |
| -------------------------- | ------------------------------ | --------------------------------------------------- |
| Slides per unit            | 3                              | 10–15                                               |
| Concept slide duration     | ~160 s static                  | ~20–35 s each                                       |
| Slide content source       | Unit metadata                  | Actual dialogue lines                               |
| Slide transition timing    | Estimated (±15 s)              | Exact (±0 ms)                                       |
| Subtitle timing            | Estimated                      | Exact                                               |
| Rendering engine           | Pillow (bitmap)                | Playwright + CSS (browser)                          |
| Diagram tool               | Graphviz subprocess            | Mermaid (JS in browser)                             |
| Code highlighting          | None                           | highlight.js                                        |
| Typography                 | PIL ImageFont                  | Inter + JetBrains Mono, kerned                      |
| New slide types            | 3 (hook/concept/memory)        | 10 types                                            |
| Adding a new slide type    | New Python compositor function | New 20-line HTML template                           |
| Graphviz system dependency | Required                       | Removed                                             |
| New dependencies           | None                           | playwright, jinja2                                  |
| Extra processing time      | 0                              | ~600 ms per unit (Chromium screenshots)             |
| Backward compat            | —                              | Yes (falls back to v2 estimation if no timing file) |

The result: a video where the screen changes every 20–30 seconds, every visual
directly reflects what is being spoken, code is syntax-highlighted, diagrams are
rendered by a proper engine, and every subtitle appears at exactly the right moment.
