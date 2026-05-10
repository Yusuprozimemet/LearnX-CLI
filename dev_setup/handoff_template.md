# Handoff Template — LearnX Spec Days

## What This Is

A copy-paste prompt for starting each spec day in a **fresh session**.
Fill in the blanks for the current day, paste it as the first message.
The agent needs nothing else to begin.

**Rule:** One template per session. Never reuse a session across two spec days.

---

## The Template (blank)

```
=== LEARNX HANDOFF — Day <N> ===

Spec:         specs/v3/day<N>.md
Branch:       sandbox/day<N>   ← create from main; do not reuse an existing branch
Files to change:
  - tutor/<path>/<file>.py
  - tutor/models.py            (add <Model> dataclass)
  - tutor/tests/<path>/test_<file>.py   (write new tests listed in spec)

Scoped test command:   py -m pytest tutor/tests/<folder>/ -v
Merge gate:            py -m pytest && py -m ruff check tutor/ && py -m ruff format --check tutor/

<One sentence: what this day implements and why it matters.>

INSTRUCTIONS:
1. Read the spec completely before writing any code.
2. Create the branch from main.
3. Implement only the files listed above. Do not modify other files.
4. Run the scoped test command after each change. Fix failures before continuing.
5. When the scoped tests are green, run the full merge gate.
6. Fix any gate failures. Re-run until fully clean.
7. Report: list each acceptance criterion and whether it passes. Show gate output.
8. Do NOT merge to main — I will review and merge.

Read these fix notes before starting (relevant to this day):
  - fixes/fix<NNN>.md — <reason>
```

---

## Pre-filled: Day 13 — Exact Timing Capture

```
=== LEARNX HANDOFF — Day 13 ===

Spec:         specs/v3/day13.md
Branch:       sandbox/day13   ← create from main
Files to change:
  - tutor/audio/audio_builder.py   (modify _concat_with_silence + _assemble)
  - tutor/models.py                (add TimingEntry dataclass)
  - tutor/tests/audio/test_audio_builder.py   (EXTEND existing file — 7 new tests listed in spec)

Scoped test command:   py -m pytest tutor/tests/audio/ -v
Merge gate:            py -m pytest && py -m ruff check tutor/ && py -m ruff format --check tutor/

Day 13 captures exact per-line millisecond timestamps during audio assembly and writes
them to tutorial.timing.json — giving every downstream step (subtitles, beat timer,
slide sequencer) deterministic, zero-estimation timing. JSON unit keys are plain
string integers ("1", "2", …) — not "unit_1".

INSTRUCTIONS:
1. Read the spec completely before writing any code.
2. Create the branch from main.
3. Implement only the files listed above. Do not modify other files.
4. Run the scoped test command after each change. Fix failures before continuing.
5. When the scoped tests are green, run the full merge gate.
6. Fix any gate failures. Re-run until fully clean.
7. Report: list each acceptance criterion and whether it passes. Show gate output.
8. Do NOT merge to main — I will review and merge.

Read these fix notes before starting:
  - fixes/fix001.md — ffmpeg path on Windows: pydub needs the binary patched in; tests that load MP3s will fail silently if ffmpeg is missing
  - fixes/fix013.md — timing inflation root cause: this is the exact problem Day 13 is solving; read it to understand the context
```

---

## Pre-filled: Day 14 — Dialogue-Aware Visual Segment Planner

```
=== LEARNX HANDOFF — Day 14 ===

Spec:         specs/v3/day14.md
Branch:       sandbox/day14   ← create from main (after day13 is merged)
Files to change:
  - tutor/generation/segment_planner.py            (new file — do NOT modify visual_planner.py)
  - tutor/models.py                                (add VALID_VISUAL_TYPES + SlideSegment dataclass)
  - tutor/prompts/visual_v3.txt                    (new prompt file)
  - tutor/tests/generation/test_segment_planner.py (new file — 17 tests listed in spec)

Scoped test command:   py -m pytest tutor/tests/generation/test_segment_planner.py -v
Merge gate:            py -m pytest && py -m ruff check tutor/ && py -m ruff format --check tutor/

Day 14 adds a new segment_planner.py that reads the actual dialogue transcript and asks
the LLM to assign a visual type to each 1-3 line block. SlideSegment has language and
mermaid fields. 10 visual types including diagram. visual_planner.py is untouched —
it still handles title card and outro via plan_visuals().

INSTRUCTIONS:
1. Read the spec completely before writing any code.
2. Create the branch from main (day13 must be merged first).
3. Implement only the files listed above. Do not modify other files.
4. Run the scoped test command after each change. Fix failures before continuing.
5. When the scoped tests are green, run the full merge gate.
6. Fix any gate failures. Re-run until fully clean.
7. Report: list each acceptance criterion and whether it passes. Show gate output.
8. Do NOT merge to main — I will review and merge.
```

---

## Pre-filled: Day 15 — HTML Slide Renderer (Playwright + Jinja2)

```
=== LEARNX HANDOFF — Day 15 ===

Spec:         specs/v3/day15.md
Branch:       sandbox/day15   ← create from main (after day14 is merged)

Files to CREATE:
  - tutor/visual/slide_renderer.py          (new — Playwright + Jinja2, ~100 lines)
  - tutor/visual/templates/_base.html.j2    (new — shared layout)
  - tutor/visual/templates/<type>.html.j2   (new — one per visual type, 10 types + title + outro)
  - tutor/assets/html/                      (new — CSS, JS, fonts; see spec for download instructions)
  - tutor/tests/visual/test_slide_renderer.py   (new — 9 tests listed in spec)

Files to DELETE:
  - tutor/visual/slide_compositor.py
  - tutor/visual/slide_draw.py
  - tutor/visual/slide_theme.py
  - tutor/visual/diagram_renderer.py
  - tutor/tests/visual/test_slide_compositor.py
  - tutor/tests/visual/test_slide_draw.py
  - tutor/tests/visual/test_slide_theme.py
  - tutor/tests/visual/test_diagram_renderer.py

pyproject.toml: add playwright>=1.44 and jinja2>=3.1; remove graphviz if present.

Pre-requisite (run once before starting):
  pip install playwright jinja2
  playwright install chromium

Scoped test command:   py -m pytest tutor/tests/visual/test_slide_renderer.py -v
Merge gate:            py -m pytest && py -m ruff check tutor/ && py -m ruff format --check tutor/

Day 15 replaces Pillow with Playwright + Jinja2 HTML templates. Slides are rendered
by headless Chromium (~50 ms/slide). All 10 visual types + title card + outro. Mermaid
diagrams rendered in-browser. Syntax highlighting via highlight.js. All assets committed
locally — no network calls during rendering.

INSTRUCTIONS:
1. Read the spec completely before writing any code — asset download instructions are in the spec.
2. Create the branch from main (day14 must be merged first).
3. Download and commit the static assets listed in the spec before writing Python.
4. Implement only the files listed above. Do not modify other files.
5. Run the scoped test command after each change. Fix failures before continuing.
6. When the scoped tests are green, run the full merge gate.
7. Fix any gate failures. Re-run until fully clean.
8. Report: list each acceptance criterion and whether it passes. Show gate output.
9. Do NOT merge to main — I will review and merge.

Note: slow tests (those requiring a live browser) are marked @pytest.mark.slow.
Run with -m "not slow" for fast feedback during development.
```

---

## Pre-filled: Day 16 — Full Pipeline Integration

```
=== LEARNX HANDOFF — Day 16 ===

Spec:         specs/v3/day16.md
Branch:       sandbox/day16   ← create from main (after day15 is merged)
Files to change:
  - tutor/visual/beat_timer.py
      rename compute_slide_timings() → _compute_slide_timings_v2() (private, logic unchanged)
      add compute_slide_timings_v3() (new public function, works with SlideSegment lists)
  - tutor/visual/subtitle_writer.py
      add timing_json: dict | None = None param to build_srt() and get_line_start_offsets()
      add _exact_line_offsets() private function
  - tutor/visual/__init__.py
      rewrite run_visual_pipeline() to the v3 6-step flow; add _load_timing_json() helper
  - tutor/tests/visual/test_beat_timer.py          (EXTEND — 8 new tests listed in spec)
  - tutor/tests/visual/test_subtitle_writer.py      (EXTEND — 4 new tests listed in spec)
  - tutor/tests/visual/test_pipeline_integration.py (new file — 6 tests listed in spec)

Scoped test command:   py -m pytest tutor/tests/visual/ -v
Merge gate:            py -m pytest && py -m ruff check tutor/ && py -m ruff format --check tutor/

Day 16 wires tutorial.timing.json (Day 13), segment plan (Day 14), and Playwright
renderer (Day 15) into the full end-to-end pipeline. Backward compatibility is a hard
requirement — sessions without timing.json must still produce a correct video via
proportional fallback. timing_json unit keys are plain string integers ("1", "2", …).

INSTRUCTIONS:
1. Read the spec completely before writing any code.
2. Create the branch from main (day15 must be merged first).
3. Implement only the files listed above. Do not modify other files.
4. Run the scoped test command after each change. Fix failures before continuing.
5. When the scoped tests are green, run the full merge gate.
6. Fix any gate failures. Re-run until fully clean.
7. Report: list each acceptance criterion and whether it passes. Show gate output.
8. Do NOT merge to main — I will review and merge.
```

---

## After a Day Completes — Merge Checklist

Before you (the human) run `git merge sandbox/dayN`:

```
[ ] Agent reported all acceptance criteria as green
[ ] Agent showed full pytest output (0 failures)
[ ] Agent showed ruff output (0 errors, 0 formatting issues)
[ ] No files changed outside the spec's stated file list
[ ] No new files created that the spec did not mention
[ ] git diff sandbox/dayN main shows only spec-listed changes
```

After merging:

```powershell
git checkout main
git merge sandbox/day<N>
git branch -d sandbox/day<N>
py -m pytest                    # regression check on clean main
```

If the regression check fails, fix before starting the next day.

---

## Stuck Session Protocol

If tests have been failing for 3+ iterations with no progress:

1. Stop. Write one sentence in `fixes/fix0NN.md` describing the actual problem.
2. Open a **new session**.
3. Use the same pre-filled handoff above PLUS append:

```
One test is currently failing:
  [paste the exact pytest failure output here]

The branch sandbox/day<N> already exists — do not recreate it.
Investigate only this failure. Do not refactor or change other code.
```

The agent gets a clean context focused on one specific failure.
