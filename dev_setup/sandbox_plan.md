# Sandbox Plan for LearnX — Spec-Driven Development

## What Problem Does a Sandbox Solve?

You are working spec-by-spec: Day 13, Day 14, Day 15, Day 16. Each day changes real
files in `tutor/`. Without isolation:

- Day 14 code can accidentally break Day 13's passing tests
- Half-finished Day 15 renderers pollute the main branch
- If something goes wrong, you can't tell which day's change caused it

A sandbox gives each spec its own protected workspace. You implement inside it, run
tests inside it, and only merge to `main` when the spec's acceptance criteria are all
green.

This is the core SDD loop:

```
Read spec → Sandbox → Implement → Test → Green? → Merge to main
                                        ↓ Red?  → Fix inside sandbox → Re-test
```

---

## How This Project Maps to the Sandbox Concept

| Spec-Driven Concept    | What It Means for LearnX                         |
| ---------------------- | ------------------------------------------------ |
| Spec = source of truth | `specs/v3/day13.md`, `day14.md`, etc.            |
| Sandbox                | A git branch with its own isolated working tree  |
| Acceptance criteria    | The `- [ ]` checklist at the bottom of each spec |
| Merge gate             | All `pytest` tests pass + `ruff` clean           |
| Regression protection  | Re-running earlier spec tests after each merge   |

---

## Phase 1 — Simple Sandbox (Start Here)

This uses only what you already have: **git + pytest**. No Docker needed yet.

### Step 1: Create a branch for the spec

Before starting any day's work, create a branch from main:

```powershell
git checkout main
git pull
git checkout -b sandbox/day13
```

Name pattern: `sandbox/day<N>` — keeps them easy to find and delete.

### Step 2: Open the spec and list the acceptance criteria

Open `specs/v3/day13.md` and find the acceptance criteria section.
Write them down or keep the file open. These are your exit conditions — you are
done only when every checkbox is green.

Day 13's criteria (example):

```
- [ ] tutorial.timing.json written to audio/<session>/ on every /generate run
- [ ] Teaching units 1..N present in "units" dict; unit 0 and -1 excluded
- [ ] start_ms of each entry equals previous end_ms + silence gap
- [ ] end_ms - start_ms equals len(AudioSegment.from_mp3(seg.audio_path))
- [ ] JSON is valid UTF-8 with "version": 1 at top level
- [ ] audio_builder.py stays under 400 lines
- [ ] All existing build() callers run without modification
```

### Step 3: Implement inside the branch

Make changes only to the files the spec says to change. For Day 13:

- `tutor/audio/audio_builder.py` (the only file)
- `tutor/models.py` (add `TimingEntry`)
- `tutor/tests/audio/test_audio_builder.py` (add the new tests)

### Step 4: Run spec-scoped tests

Run only the tests for what you just changed — not the whole suite:

```powershell
# Run only the audio builder tests
py -m pytest tutor/tests/audio/ -v

# Run ruff on only the changed files
py -m ruff check tutor/audio/audio_builder.py tutor/models.py
```

This is fast and tells you exactly what is broken.

### Step 5: Run the full suite before merging

When the spec tests are green, run everything:

```powershell
py -m pytest
py -m ruff check tutor/
py -m ruff format --check tutor/
```

If something fails that you did not touch, that is a regression. Fix it before merging.

### Step 6: Merge to main only when all green

```powershell
git checkout main
git merge sandbox/day13
git branch -d sandbox/day13
```

---

## Phase 2 — Sandbox Folder as Experiment Space

The `sandbox/` folder in this repo is your scratch pad. Use it to test ideas
**before** writing real code. Nothing in `sandbox/` is imported by the main package.

### What to put here

**Quick prototype scripts** — before touching `audio_builder.py`, prove your
timing logic works in a throwaway file:

```
sandbox/
  proto_timing.py       ← quick test of the cursor_ms accumulation logic
  proto_segments.py     ← test the LLM JSON parsing approach for Day 14

```

### How to use a prototype

Example workflow for Day 13:

```python
# sandbox/proto_timing.py
# Test the timing cursor logic before touching audio_builder.py

SILENCE_BREATH_MS = 300
SILENCE_TURN_MS   = 600

fake_segments = [
    {"speaker": "ALEX", "duration_ms": 3200},
    {"speaker": "ALEX", "duration_ms": 2400},
    {"speaker": "MAYA", "duration_ms": 1840},
    {"speaker": "ALEX", "duration_ms": 2100},
]

cursor_ms = 0
prev_speaker = None
entries = []

for idx, seg in enumerate(fake_segments):
    if prev_speaker is None:
        gap = 0
    elif prev_speaker == seg["speaker"]:
        gap = SILENCE_BREATH_MS
    else:
        gap = SILENCE_TURN_MS
    cursor_ms += gap
    entries.append({"line_index": idx, "start_ms": cursor_ms})
    cursor_ms += seg["duration_ms"]
    entries.append({"end_ms": cursor_ms})
    prev_speaker = seg["speaker"]

for e in entries:
    print(e)
```

Run it, verify the numbers make sense, then write the real implementation.

This prevents the "write 50 lines, discover the logic is wrong" problem.

---

## Phase 3 — Docker Sandbox (For Later, Optional)

When you are comfortable with the git-branch workflow, Docker adds a harder isolation
layer: the sandbox runs in a container with no access to your files or secrets.

This is valuable when:

- An AI agent is writing the code and you do not fully trust it
- You want to test on a clean environment (no local venv drift)
- You are running multiple specs in parallel

### Minimal Dockerfile for LearnX

```dockerfile
FROM python:3.12-slim
RUN useradd -m -u 1000 sandbox
USER sandbox
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
```

### Build and run tests inside the container

```powershell
# Build once
docker build -t learnx-sandbox .

# Run tests in isolation — mounts the current branch read-only
docker run --rm `
  --network none `
  --memory=1g --cpus=1.0 `
  -v "${PWD}:/app:ro" `
  learnx-sandbox `
  python -m pytest tutor/tests/audio/ -v
```

The `:ro` mount means the container cannot write back to your repo — it can only read.
This mirrors the "main codebase read-only" pattern from `box.md`.

For now, stick with Phase 1 and Phase 2. Add Docker when the project needs it.

---

## Day-by-Day Workflow Cheat Sheet

```
Day 13: sandbox/day13 branch
  Files: audio_builder.py, models.py
  Test:  py -m pytest tutor/tests/audio/ -v
  Gate:  tutorial.timing.json written + all timing assertions pass

Day 14: sandbox/day14 branch (from main, AFTER day13 merged)
  Files: generation/segment_planner.py (new), models.py, prompts/visual_v2.txt
  Test:  py -m pytest tutor/tests/generation/test_segment_planner.py -v
  Gate:  all 12 acceptance criteria pass

Day 15: sandbox/day15 branch (from main, AFTER day14 merged)
  Files: visual/slide_compositor.py
  Test:  py -m pytest tutor/tests/visual/test_slide_compositor.py -v
  Gate:  all compositor functions produce valid PNGs

Day 16: sandbox/day16 branch (from main, AFTER day15 merged)
  Files: visual/beat_timer.py, visual/subtitle_writer.py
  Test:  py -m pytest tutor/tests/visual/ -v
  Gate:  compute_slide_timings() uses timing.json when present; falls back when absent
```

**Always create the next branch from `main` after the previous one is merged.**
Never branch off a sandbox branch — that defeats the isolation.

---

## Regression Check After Each Merge

After merging any day, run the full suite to confirm nothing broke:

```powershell
py -m pytest
```

If a test that was passing before now fails, that is a **regression**. Read which
test failed, figure out which merge caused it (use `git log`), and fix it before
starting the next day.

This is the "re-run all previous specs" step that `box.md` describes as regression
protection.

---

## What the Sandbox Is Not

- **Not a virtual environment** — you still use the same venv; the sandbox is the
  git branch, not Python's package isolation.
- **Not a backup** — git handles history; the sandbox branch is a working space,
  not an archive.
- **Not Docker yet** — Phase 1 is just branches. Docker is Phase 3 and is optional.

---

## Quick Commands Reference

```powershell
# Start a new spec sandbox
git checkout main && git checkout -b sandbox/day<N>

# Run spec-scoped tests
py -m pytest tutor/tests/<relevant_folder>/ -v

# Run lint check
py -m ruff check tutor/

# Run the full suite (merge gate)
py -m pytest && py -m ruff check tutor/ && py -m ruff format --check tutor/

# Merge when green
git checkout main && git merge sandbox/day<N> && git branch -d sandbox/day<N>

# If something went badly wrong — discard the sandbox branch entirely
git checkout main && git branch -D sandbox/day<N>
```

---

## Learning Goals

By the end of Days 13–16 with this workflow, you will have:

1. Experienced what it feels like to have spec acceptance criteria act as real tests
2. Seen how a regression in Day 14 can surface as a failing Day 13 test
3. Understood why "merge only when green" protects the stable baseline
4. Built a mental model for why Docker (Phase 3) adds value but is not required to start

That mental model is what `box.md` is actually teaching — start simple, add isolation
layers only when the project demands them.
