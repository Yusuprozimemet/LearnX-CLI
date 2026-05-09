# LearnX v3 — Conversation-Driven Slides

## The wrong mental model (v2)

v2 treats slides as **chapter markers**: one static image per phase of a lesson
(hook / concept / memory). The concept image holds for 2–3 minutes while the
conversation flows underneath it. The viewer watches a frozen diagram while ALEX
and MAYA discuss, question, correct, and demonstrate — nothing on screen changes.

This is not educational video. This is a podcast with a background image.

---

## How good educational videos actually work

Look at the tools that produce video people actually learn from:

| Tool / Creator | How visuals track the narration |
|---|---|
| Khan Academy | Tablet drawing — each shape/label appears the moment it is spoken |
| 3Blue1Brown | Animations driven by the script — every visual element tied to a sentence |
| Lumen5 / Pictory | Each sentence → its own 10–20 s scene with matching text and image |
| Coursera lectures | Slide advances with every new sub-topic (every 20–40 s on average) |
| Descript | Video editing is done by editing the transcript — timeline = text |

The common principle: **the visual IS the explanation, not a decoration beside it.**

Every time a new idea is spoken, the viewer sees that idea on screen. Every time a
comparison is made, a comparison slide appears. Every time code is shown, code appears.
The screen tracks the audio, line by line.

For LearnX the dialogue script is the source of truth. Every idea in the video is
already written — ALEX's explanations, MAYA's questions, the analogies, the code
examples, the memory hook. We just need to turn each spoken idea into its matching
visual automatically.

---

## The two problems to fix

### Problem 1 — Slide count: 3 is not a structure, it's a minimum

v2 generates 3 slides per unit. In a 3.5-minute unit:
- hook: 30 s (1 slide)
- concept: 160–170 s (1 static slide — **2.5 minutes of nothing changing**)
- memory: 15 s (1 slide)

A typical unit has 18–25 dialogue lines covering 3–5 distinct ideas. All of those
ideas are mapped to one image. The viewer cannot tell when the topic shifts, when
a new example starts, or when MAYA's question is being answered.

**The fix:** one slide per dialogue segment (1–3 lines covering one idea). A
3.5-minute unit should have 10–15 slides, each showing for 15–35 seconds.

### Problem 2 — Timing: every timestamp is an estimate

v2 estimates when each dialogue line plays by dividing word count by 130 WPM, then
adds fixed silence constants (500 ms/turn, 1200 ms/unit) — ON TOP of scaling to the
total unit duration. This inflates every timestamp by 5–15 s per unit.

The result: the slide transition from hook → concept can happen 15–20 seconds before
MAYA actually speaks. Subtitles are equally drifted.

**The fix:** capture exact per-line timestamps during audio assembly — they are already
computed for free.

---

## The key insight: exact timing already exists in the audio builder

`audio_builder._concat_with_silence()` is where TTS segments are stitched together.
At that exact point, pydub knows:

- `len(AudioSegment.from_mp3(seg.audio_path))` → exact duration of each line in ms
- The exact silence gaps: `SILENCE_BREATH_MS` (same speaker) or `SILENCE_TURN_MS` (speaker change)
- The running cursor position

This is thrown away. If we write it to `tutorial.timing.json` during assembly,
every subsequent step — subtitle writer, beat timer, slide sequencer — has
**exact, deterministic, zero-overhead timing** for every spoken line.

No Whisper. No estimation. No new dependencies. The timing is already being computed.

```json
// tutorial.timing.json
{
  "unit_1": [
    {"line_index": 0, "speaker": "ALEX", "start_ms": 0,    "end_ms": 3200},
    {"line_index": 1, "speaker": "ALEX", "start_ms": 3700,  "end_ms": 7100},
    {"line_index": 2, "speaker": "MAYA", "start_ms": 7600,  "end_ms": 9500},
    ...
  ],
  "unit_2": [...]
}
```

This includes the actual `SILENCE_TURN_MS` and `SILENCE_BREATH_MS` gaps because they
are inserted by the same function that writes the timestamps.

For sessions generated before v3 (no timing file), the video pipeline falls back to
proportional estimation — the same quality as v2, not worse.

---

## The architecture shift: dialogue → slides, not metadata → slides

### v2 approach

```
TeachingUnit (concept, key_facts, analogy, memory_hook)
  → LLM → VisualSpec (hook_question, key_points, diagram_spec, memory_hook)
    → 3 PNGs (hook, concept, memory)
      → beat timer estimates transitions from word count
        → 3 slides for 3.5 minutes
```

The LLM never sees the dialogue. It plans visuals from metadata only.

### v3 approach

```
DialogueLine[]  (the actual script, 18–25 lines per unit)
  → LLM → list[SlideSegment] (lines_start, lines_end, visual_type, content)
    → N PNGs (one per segment, 10–15 per unit)
      → tutorial.timing.json gives exact start/end for each line
        → slide_duration = line[end].end_ms − line[start].start_ms
          → 10–15 slides, each locked to its speech
```

The LLM reads the actual conversation and decides what visual matches each 1–3 lines.
Timing is derived from the audio builder, not word count.

---

## New slide types

Each type is a distinct compositor function. All use Pillow; no Graphviz required for
most of them.

### `hook_question`
*Shown during ALEX's opening hook lines. Already exists.*

```
┌──────────────────────────────────────────────────────┐
│ TOP BAR: Unit 2 of 4                                 │
├──────────────────────────────────────────────────────┤
│                                                      │
│  //  Interface or abstract class — which fits?       │
│                                                      │
│  WHAT YOU'LL LEARN:                                  │
│  + Contracts vs blueprints                           │
│  + When to use each                                  │
│  + The IS-A vs HAS-A rule                            │
│                                                      │
├──────────────────────────────────────────────────────┤
│  ● ○ ○ ○ ○ ○ ○ ○ ○                    [LEARNX]      │
└──────────────────────────────────────────────────────┘
```

### `definition`
*Shown when ALEX introduces or explains a term.*

```
┌──────────────────────────────────────────────────────┐
│ TOP BAR: Unit 2 · Interface                          │
├──────────────────────────────────────────────────────┤
│                                                      │
│  INTERFACE                               [cyan tag]  │
│  ─────────────────────────────────────              │
│  A contract that specifies what a class              │
│  MUST do, without any implementation.                │
│                                                      │
│  ┌──────────────────────────────────────┐           │
│  │  interface Animal {                  │           │
│  │      void speak();                   │           │
│  │  }                                   │           │
│  └──────────────────────────────────────┘           │
│                                                      │
├──────────────────────────────────────────────────────┤
│  ○ ● ○ ○ ○ ○ ○ ○ ○                    [LEARNX]      │
└──────────────────────────────────────────────────────┘
```

### `analogy`
*Shown when ALEX uses an analogy.*

```
┌──────────────────────────────────────────────────────┐
│ TOP BAR: Unit 2 · Think of it this way               │
├──────────────────────────────────────────────────────┤
│                                                      │
│  ┌─────────────────────┐    ┌─────────────────────┐  │
│  │  Job Description    │ ≈  │  Interface          │  │
│  │                     │    │                     │  │
│  │  Lists duties.      │    │  Lists methods.     │  │
│  │  Says nothing about │    │  Says nothing about │  │
│  │  HOW to do them.    │    │  HOW to implement.  │  │
│  └─────────────────────┘    └─────────────────────┘  │
│                                                      │
├──────────────────────────────────────────────────────┤
│  ○ ○ ● ○ ○ ○ ○ ○ ○                    [LEARNX]      │
└──────────────────────────────────────────────────────┘
```

### `comparison`
*Shown when ALEX compares two things side by side.*

```
┌──────────────────────────────────────────────────────┐
│ TOP BAR: Unit 2 · Interface vs Abstract Class        │
├──────────────────────────────────────────────────────┤
│                                                      │
│  INTERFACE              │  ABSTRACT CLASS            │
│  ───────────────────────┼──────────────────────────  │
│  No state               │  Can have fields           │
│  All methods abstract   │  Can have concrete methods  │
│  Multiple inheritance   │  Single inheritance only   │
│  Pure contract          │  Partial implementation    │
│                                                      │
├──────────────────────────────────────────────────────┤
│  ○ ○ ○ ● ○ ○ ○ ○ ○                    [LEARNX]      │
└──────────────────────────────────────────────────────┘
```

### `question_prompt`
*Shown when MAYA asks a question. Makes the question visible.*

```
┌──────────────────────────────────────────────────────┐
│ TOP BAR: Unit 2                    [MAYA] tag        │
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
*Shown when code is being demonstrated.*

```
┌──────────────────────────────────────────────────────┐
│ TOP BAR: Unit 2 · In practice                        │
├──────────────────────────────────────────────────────┤
│                                                      │
│  // Using interface                                  │
│  interface Drawable { void draw(); }                 │
│  class Circle implements Drawable { ... }            │
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

### `decision_guide`
*Shown when ALEX explains when to use which.*

```
┌──────────────────────────────────────────────────────┐
│ TOP BAR: Unit 2 · When to use each                   │
├──────────────────────────────────────────────────────┤
│                                                      │
│  USE INTERFACE when...            USE ABSTRACT when..│
│                                                      │
│  → Unrelated classes share        → Classes share    │
│    a contract                       common code      │
│                                                      │
│  → Multiple inheritance           → You want to      │
│    is needed                        force extension  │
│                                                      │
│  → Pure API definition            → Partial impl ok  │
│                                                      │
├──────────────────────────────────────────────────────┤
│  ○ ○ ○ ○ ○ ○ ● ○ ○                    [LEARNX]      │
└──────────────────────────────────────────────────────┘
```

### `key_insight`
*Shown when ALEX states a rule or key fact.*

```
┌──────────────────────────────────────────────────────┐
│ TOP BAR: Unit 2 · The rule                           │
├──────────────────────────────────────────────────────┤
│                                                      │
│                                                      │
│  If you can say "IS-A" without                       │
│  sharing code — use an interface.                    │
│                                                      │
│                                                      │
├──────────────────────────────────────────────────────┤
│  ○ ○ ○ ○ ○ ○ ○ ● ○                    [LEARNX]      │
└──────────────────────────────────────────────────────┘
```

### `memory_hook`
*Shown during ALEX's closing lines. Already exists.*

---

## New LLM prompt: read the dialogue, assign slides

The v3 visual planner gets the **full dialogue text** for each unit, not just metadata.

```
Given this dialogue transcript for a Java tutorial unit, group consecutive lines
into visual segments. Each segment = 1–3 lines covering one idea.

For each segment, specify:
  - lines_start, lines_end  (inclusive 0-based indices)
  - visual_type             (one of the types listed below)
  - title                   (short header text for the slide)
  - body                    (main content: definition, analogy text, bullet list, etc.)
  - code                    (code string if relevant, else null)
  - left / right            (for comparison type: two column labels)
  - rows                    (for comparison type: [[left_cell, right_cell], ...])

Visual types:
  hook_question | definition | analogy | comparison | code_example |
  question_prompt | decision_guide | key_insight | memory_hook

Rules:
  - Cover every line — no gaps
  - MAYA questions → question_prompt
  - ALEX introducing a named concept → definition
  - ALEX using "like" / "think of" / "imagine" → analogy
  - ALEX contrasting two things → comparison
  - ALEX showing or referencing code → code_example
  - ALEX stating a rule/condition → key_insight or decision_guide
  - Last ALEX lines (memory hook) → memory_hook
  - Opening ALEX lines (hook question) → hook_question

Output: JSON array. No prose.
```

### Example output

```json
[
  {"lines_start": 0, "lines_end": 1,  "visual_type": "hook_question",  "title": "Interface or abstract class?", "body": "..."},
  {"lines_start": 2, "lines_end": 4,  "visual_type": "definition",     "title": "Interface",   "body": "A contract specifying what a class must do", "code": "interface Animal { void speak(); }"},
  {"lines_start": 5, "lines_end": 6,  "visual_type": "analogy",        "title": "Like a job description", "body": "Lists duties, says nothing about how"},
  {"lines_start": 7, "lines_end": 7,  "visual_type": "question_prompt","title": "MAYA asks",  "body": "Can't abstract classes do the same thing?"},
  {"lines_start": 8, "lines_end": 10, "visual_type": "definition",     "title": "Abstract Class", "body": "A partial blueprint: shared code + required extensions"},
  {"lines_start": 11,"lines_end": 13, "visual_type": "comparison",     "title": "Interface vs Abstract Class", "left": "Interface", "right": "Abstract Class", "rows": [["No state", "Can have fields"], ["Multiple inheritance", "Single inheritance"]]},
  {"lines_start": 14,"lines_end": 15, "visual_type": "code_example",   "title": "In practice", "code": "interface Drawable {...}\nclass Circle implements Drawable {...}"},
  {"lines_start": 16,"lines_end": 17, "visual_type": "decision_guide", "title": "When to use each", "body": "Interface: no shared code. Abstract: shared implementation."},
  {"lines_start": 18,"lines_end": 19, "visual_type": "key_insight",    "title": "The rule", "body": "If you can say IS-A without sharing code — use interface."},
  {"lines_start": 20,"lines_end": 21, "visual_type": "memory_hook",    "title": "Remember", "body": "Interface = contract. Abstract class = blueprint."}
]
```

10 slides. Average 21 s each for a 3.5-minute unit.

---

## Implementation plan

### Day 13 — Exact timing from the audio builder

**File:** `tutor/audio/audio_builder.py`

Modify `_concat_with_silence()` to return a timing list alongside the audio:

```python
def _concat_with_silence(segments):
    result = AudioSegment.empty()
    timing = []          # [{line_index, speaker, start_ms, end_ms}, ...]
    cursor_ms = 0
    prev_speaker = None

    for seg in segments:
        audio = AudioSegment.from_mp3(seg.audio_path)
        if prev_speaker is None:
            gap = 0
        elif prev_speaker == seg.line.speaker:
            gap = SILENCE_BREATH_MS
        else:
            gap = SILENCE_TURN_MS
        cursor_ms += gap
        result += AudioSegment.silent(duration=gap) if gap else AudioSegment.empty()

        timing.append({
            "line_index": ...,
            "speaker": seg.line.speaker,
            "start_ms": cursor_ms,
            "end_ms":   cursor_ms + len(audio),
        })
        result += audio
        cursor_ms += len(audio)
        prev_speaker = seg.line.speaker

    return result, timing
```

`_assemble()` collects timing per unit and writes `tutorial.timing.json` to the
audio session directory. This file is small (a few KB) and is stable — the timing
is fixed once audio is generated.

**Impact:** `subtitle_writer`, `beat_timer`, and the new slide sequencer all read
from this file instead of estimating.

---

### Day 14 — Dialogue-aware visual planner

**File:** `tutor/generation/visual_planner.py`

New function `plan_segments(unit, dialogue_lines, llm_fn)` replaces `_plan_unit()`:

- Input: `unit: TeachingUnit` + `dialogue_lines: list[DialogueLine]` for that unit
- Output: `list[SlideSegment]` with `lines_start`, `lines_end`, `visual_type`, `content`
- Prompt: the `visual_v2.txt` prompt (reads actual dialogue, assigns visual types)
- Cache key: hash of dialogue text + unit concept

**File:** `tutor/models.py`

Add `SlideSegment` dataclass:
```python
@dataclass
class SlideSegment:
    unit_index:   int
    lines_start:  int          # 0-based index into unit dialogue lines
    lines_end:    int
    visual_type:  str          # definition | analogy | comparison | ...
    title:        str
    body:         str
    code:         str | None
    left:         str | None   # comparison column label
    right:        str | None
    rows:         list | None  # comparison rows
```

`VisualSpec` is kept for the title card and outro (which are not dialogue-driven).

**File:** `tutor/visual/__init__.py`

`run_visual_pipeline()` loads `tutorial.timing.json` if it exists.
Passes dialogue lines to `plan_visuals_v3()`.

---

### Day 15 — Slide renderers for each visual type

**File:** `tutor/visual/slide_compositor.py`

Add compositor functions:

| Function | Renders |
|---|---|
| `compose_definition(seg, output)` | Term + definition + optional code |
| `compose_analogy(seg, output)` | Two-panel layout with ≈ symbol |
| `compose_comparison(seg, output)` | Two-column table from `rows` |
| `compose_code_example(seg, output)` | Full-width monospaced code block |
| `compose_question_prompt(seg, output)` | Large centred MAYA question |
| `compose_decision_guide(seg, output)` | Two-column decision criteria |
| `compose_key_insight(seg, output)` | Large centred rule text |

No Graphviz needed for any of these. Pure Pillow. The existing diagram renderer
is still used for the `concept_diagram` type (kept as an optional enhancement).

**Progress dots** in footer: one dot per slide segment, filled dot = current slide.
This tells the viewer how far through the unit they are.

---

### Day 16 — Beat timer rewrite and full integration

**File:** `tutor/visual/beat_timer.py`

`compute_slide_timings()` is rewritten to work with `SlideSegment` lists:

```python
def compute_slide_timings(segments, timing_json, unit_durations_s):
    result = []
    for seg in segments:
        if timing_json:
            start = timing_json[unit][seg.lines_start]["start_ms"] / 1000
            end   = timing_json[unit][seg.lines_end]["end_ms"]   / 1000
            dur   = max(end - start, MIN_SLIDE_DURATION)
        else:
            dur = _proportional_fallback(seg, unit_duration)
        result.append((seg.png_path, dur))
    return result
```

**Backward compatibility:** if `tutorial.timing.json` does not exist (session
generated before v3), `dur` falls back to proportional estimation. The video
pipeline still runs; it just uses v2-quality timing.

**File:** `tutor/visual/subtitle_writer.py`

`get_line_start_offsets()` accepts the timing dict. Returns exact offsets
when available; falls back to current `_compute_timing()` otherwise.

---

## What does NOT change

- `/generate`, the audio player, Q&A engine — untouched
- The 5-stage pipeline structure (plan → diagram → composite → time → assemble)
- The title card and outro (not dialogue-driven)
- The `video_assembler.py` ffmpeg commands (already correct after v2 fixes)
- The `VisualSpec` model (title card + outro still use it)

---

## Summary: what v3 delivers

| | v2 | v3 |
|---|---|---|
| Slides per unit | 3 | 10–15 |
| Concept slide duration | ~160 s static | ~20–35 s each |
| Slide content | Metadata-derived | Dialogue-derived |
| Slide transition timing | Estimated (±15 s) | Exact (±0 ms) |
| Subtitle timing | Estimated | Exact |
| New dependencies | none | none |
| Extra processing time | 0 | ~1 s per unit (timing write) |
| Backward compat | — | yes (falls back to v2 estimation) |

The result: a video where the screen changes every 20–30 seconds, every visual
directly reflects what is being spoken, and every subtitle appears at exactly the
right moment. That is educational video worth building.
