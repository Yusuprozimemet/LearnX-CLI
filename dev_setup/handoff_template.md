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
  - tutor/tests/audio/test_audio_builder.py   (new file — 7 tests listed in spec)

Scoped test command:   py -m pytest tutor/tests/audio/ -v
Merge gate:            py -m pytest && py -m ruff check tutor/ && py -m ruff format --check tutor/

Day 13 captures exact per-line millisecond timestamps during audio assembly and writes
them to tutorial.timing.json — giving every downstream step (subtitles, beat timer,
slide sequencer) deterministic, zero-estimation timing.

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
  - tutor/generation/segment_planner.py   (new file)
  - tutor/models.py                       (add SlideSegment dataclass)
  - tutor/prompts/visual_v2.txt           (new prompt file)
  - tutor/tests/generation/test_segment_planner.py   (new file — tests listed in spec)

Scoped test command:   py -m pytest tutor/tests/generation/test_segment_planner.py -v
Merge gate:            py -m pytest && py -m ruff check tutor/ && py -m ruff format --check tutor/

Day 14 replaces the metadata-driven visual planner with a dialogue-aware one that reads
the actual conversation script and assigns a visual type + content to each 1-3 line segment.

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

## Pre-filled: Day 15 — Slide Renderers for Each Visual Type

```
=== LEARNX HANDOFF — Day 15 ===

Spec:         specs/v3/day15.md
Branch:       sandbox/day15   ← create from main (after day14 is merged)
Files to change:
  - tutor/visual/slide_compositor.py   (add compositor functions for new slide types)
  - tutor/tests/visual/test_slide_compositor.py   (extend with new tests listed in spec)

Scoped test command:   py -m pytest tutor/tests/visual/test_slide_compositor.py -v
Merge gate:            py -m pytest && py -m ruff check tutor/ && py -m ruff format --check tutor/

Day 15 adds Pillow-based compositor functions for each visual type defined in Day 14
(definition, analogy, comparison, code_example, question_prompt, decision_guide,
key_insight). Each produces a 1280×720 PNG.

INSTRUCTIONS:
1. Read the spec completely before writing any code.
2. Create the branch from main (day14 must be merged first).
3. Implement only the files listed above. Do not modify other files.
4. Run the scoped test command after each change. Fix failures before continuing.
5. When the scoped tests are green, run the full merge gate.
6. Fix any gate failures. Re-run until fully clean.
7. Report: list each acceptance criterion and whether it passes. Show gate output.
8. Do NOT merge to main — I will review and merge.
```

---

## Pre-filled: Day 16 — Full Pipeline Integration

```
=== LEARNX HANDOFF — Day 16 ===

Spec:         specs/v3/day16.md
Branch:       sandbox/day16   ← create from main (after day15 is merged)
Files to change:
  - tutor/visual/beat_timer.py          (add compute_slide_timings_v3; keep v2 function)
  - tutor/visual/subtitle_writer.py     (add timing_json param to build_srt + get_line_start_offsets)
  - tutor/visual/__init__.py            (rewrite run_visual_pipeline to v3 6-step flow)
  - tutor/tests/visual/test_beat_timer.py        (extend — tests listed in spec)
  - tutor/tests/visual/test_subtitle_writer.py   (extend — tests listed in spec)
  - tutor/tests/visual/test_pipeline_integration.py   (new file)

Scoped test command:   py -m pytest tutor/tests/visual/ -v
Merge gate:            py -m pytest && py -m ruff check tutor/ && py -m ruff format --check tutor/

Day 16 wires timing.json (Day 13), segment plan (Day 14), and slide renderers (Day 15)
into the full end-to-end video pipeline. Backward compatibility with pre-v3 sessions is
a hard requirement.

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
