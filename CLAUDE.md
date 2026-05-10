# LearnX — Agent Onboarding & Project Instructions

## What This Project Is

LearnX is a Python CLI that converts a Markdown document into an audio-first tutorial
with optional video. The pipeline is:

```
Document → chunk → LLM summarise → LLM curriculum → LLM dialogue
        → TTS render → assemble audio (+ timing.json)
        → (optional) LLM visual plan → render slides → subtitle → mp4
```

Entry point: `tutor/__main__.py`. CLI commands live in `tutor/cli/`.
Primary platform: Windows / PowerShell. Python 3.12+.

---

## Project Layout

```
specs/          versioned spec files — the source of truth for all code
  v0/ v1/ v2/   completed versions (kept for regression reference)
  v3/           current work: day13.md, day14.md, day15.md, day16.md

plan/           version-level design documents
  v0_plan.md … v3_plan.md

fixes/          post-mortem notes for surprises (fix001.md … fix015.md)
                read these before starting work — they contain env/API gotchas

dev_setup/      developer process documentation (read before first session)
  spec-driven_plan.md      what SDD means and how to write specs
  context_hygiene_plan.md  how to manage session context
  sandbox_plan.md          git branch + test isolation strategy
  autonomy_plan.md         how to run the implement→test→fix loop
  handoff_template.md      copy-paste prompt for starting each spec day

tutor/          the Python package
  models.py          all dataclasses — start here to understand data shapes
  constants.py       silence gap constants, limits
  config.py          LLM provider / model config
  audio/             audio pipeline (audio_builder.py, tts_renderer.py)
  generation/        LLM pipeline (curriculum, dialogue, narrator, visual_planner)
  ingestion/         document processing (chunker, doc_analyzer)
  visual/            video pipeline (beat_timer, slide_compositor, subtitle_writer…)
  player/            interactive playback
  cli/               CLI commands and shell
  tests/             pytest suite — mirrors tutor/ structure
  infra/             LLM client wrapper

sandbox/        throwaway prototype scripts — NOT imported by tutor/
```

---

## Development Workflow — The Four Pillars

This project uses **Spec-Driven Development**. All four pillars must be active:

### 1. Spec-Driven
- The spec file is the source of truth. Read it completely before touching any code.
- A spec has: Goal, Data boundary, Models, Algorithm, Acceptance criteria, Test names.
- Implement exactly what the spec says. Do not add features, do not guess design.
- If the spec is ambiguous, stop and report — do not invent a resolution.

### 2. Context Hygiene
- One spec per session. Do not carry Day 13 context into a Day 14 session.
- Only attach/read the files the spec lists. Not the whole `tutor/` tree.
- If the session has been running long and you are confused about earlier decisions,
  state that clearly. Do not continue with a muddled mental model.

### 3. Sandbox (Git Branch Isolation)
- Never work directly on `main`. Always create `sandbox/dayN` from `main`.
- Only modify files listed in the spec. Do not edit adjacent code "while you're there."
- The sandbox branch is disposable. If something goes badly wrong, report it and let
  the human discard the branch.

### 4. Autonomy (Implement → Test → Fix Loop)
- Run tests yourself after every change. Do not wait to be asked.
- Read pytest output, identify the failure, fix, re-run. Repeat until green.
- Exit the loop when: all acceptance criteria pass AND the merge gate is clean.
- Report once at the end — what changed, which criteria are green, gate status.

---

## The Safe Implementation Loop

Follow these steps for every spec day, in order:

```
1.  Read the spec completely (specs/v3/dayN.md)
2.  git checkout main
3.  git checkout -b sandbox/dayN
4.  Implement only the files listed in the spec's "Data boundary" / file list
5.  py -m pytest tutor/tests/<relevant_folder>/ -v          ← scoped run
6.  If failures: read output, fix, go to step 5
7.  py -m pytest                                            ← full suite
8.  py -m ruff check tutor/
9.  py -m ruff format --check tutor/
10. If anything fails in 7-9: fix it, re-run
11. Report: acceptance criteria checklist, gate status, files changed
12. STOP — do not merge to main; the human reviews and merges
```

Never skip step 12. Never merge autonomously.

---

## Current State — What Is Ready to Implement

v3 specs are written and waiting. None have been started yet.

| Day | Spec | Status | Branch to create |
|-----|------|--------|-----------------|
| 13  | `specs/v3/day13.md` — Exact timing capture from audio builder | **Not started** | `sandbox/day13` |
| 14  | `specs/v3/day14.md` — Dialogue-aware visual segment planner | Not started | `sandbox/day14` |
| 15  | `specs/v3/day15.md` — HTML slide renderer (Playwright + Jinja2) | Not started | `sandbox/day15` |
| 16  | `specs/v3/day16.md` — Full pipeline integration | Not started | `sandbox/day16` |

**Day 13 is the correct starting point.** Days 14–16 depend on it.

Day 13 key facts:
- Modify `_concat_with_silence()` in `tutor/audio/audio_builder.py` to capture timing
- Add `TimingEntry` dataclass to `tutor/models.py`
- Write `tutorial.timing.json` from `_assemble()`; keys are plain string integers (`"1"`, `"2"`, …)
- Extend `tutor/tests/audio/test_audio_builder.py` with 7 new tests
- `build()` public API must not change

Day 15 key facts (different from old plan — read carefully):
- Replaces Pillow with Playwright + Jinja2 HTML templates
- Deletes `slide_compositor.py`, `slide_draw.py`, `slide_theme.py`, `diagram_renderer.py`
  and their test files
- New file: `tutor/visual/slide_renderer.py`
- New directories: `tutor/visual/templates/` and `tutor/assets/html/`
- Adds `playwright>=1.44` and `jinja2>=3.1` to `pyproject.toml`
- Requires one-time `playwright install chromium` (add to CI)

---

## Hard Rules

```
NEVER commit to main directly
NEVER change files not listed in the spec
NEVER branch sandbox/dayN off another sandbox branch (always branch from main)
NEVER skip the merge gate (full pytest + ruff)
NEVER merge — human merges after review
NEVER start Day N+1 until Day N is merged to main
```

---

## Commands Reference

```powershell
# Start a spec day
git checkout main
git checkout -b sandbox/day<N>

# Scoped test run (fast feedback)
py -m pytest tutor/tests/<folder>/ -v

# Merge gate (run before reporting done)
py -m pytest
py -m ruff check tutor/
py -m ruff format --check tutor/

# Merge (human runs this, not the agent)
git checkout main
git merge sandbox/day<N>
git branch -d sandbox/day<N>

# Discard a bad sandbox branch
git checkout main
git branch -D sandbox/day<N>
```

---

## Where to Find Things

| Question | Where to look |
|---|---|
| What does this feature do? | `specs/v3/dayN.md` |
| Why was this approach chosen? | `plan/v3_plan.md` |
| Why does this edge case exist? | `fixes/fix0NN.md` |
| What dataclasses exist? | `tutor/models.py` |
| What silence constants are used? | `tutor/constants.py` |
| How is the LLM called? | `tutor/infra/llm.py` |
| How to start a new spec day? | `dev_setup/handoff_template.md` |

---

## Read Before Starting Any v3 Day

1. `fixes/fix001.md` — ffmpeg is not always on PATH on Windows; pydub needs the binary patched in at startup. If tests that load MP3s silently fail, this is why.
2. `fixes/fix013.md` — timing inflation root cause: `compute_slide_timings()` was using estimated beat offsets instead of actual MP3 durations. Day 13 exists to fix this permanently.
3. `fixes/fix009.md` — per-unit loudnorm breaks audio duration with image-based concat video; volume boost is applied at encode time instead.
4. `plan/v3_plan.md` — the architectural rationale for the whole v3 approach.

These four give the context for the problems Day 13–16 are solving.
