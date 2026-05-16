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
specs/          versioned spec files — source of truth for all code
  v0/ v1/ v2/   completed versions (kept for regression reference)
  v3/           completed: day13.md, day14.md, day15.md, day16.md

plan/           version-level design documents
  v0_plan.md … v3_plan.md

fixes/          post-mortem notes for surprises (fix001.md … fix035.md)
                read these before starting work — they contain env/API gotchas

dev_setup/      developer process documentation
  spec-driven_plan.md      what SDD means and how to write specs
  context_hygiene_plan.md  how to manage session context
  sandbox_plan.md          git branch + test isolation strategy
  autonomy_plan.md         how to run the implement→test→fix loop (Level 1–4)
  handoff_template.md      copy-paste prompt for starting each spec day
  container_plan.md        how to run Claude inside Docker (Level 4 workflow)

dev_setup_update/  workflow upgrade specs (v4)
  update_plan.md     upgrade goals and rationale
  architecture.md    component map and data flow
  specs/day0.md … day7.md

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
  tests/             pytest unit suite — mirrors tutor/ structure
  tests/e2e/         E2E smoke tests — run real pipeline, check output quality
  infra/             LLM client wrapper

scripts/        dev workflow tooling (NOT imported by tutor/)
  learnx_dk.py    run Claude inside Docker container
  run_review.py   trigger 5-agent code + product review
  tests/          pytest tests for the scripts themselves

sandbox/        throwaway prototype scripts — NOT imported by tutor/

.claude/
  settings.json   allow list only (deny rules removed — Docker is the sandbox)
  agents/         review + product check agent definitions
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
4.  Start the container session:
      python scripts/learnx_dk.py
    (or run directly on host for quick one-off tasks)
5.  Implement only the files listed in the spec's "Data boundary"
6.  python -m pytest tutor/tests/<relevant_folder>/ -v    ← scoped run (inside container)
7.  If failures: read output, fix, go to step 6
8.  python -m pytest                                       ← full unit suite
9.  python -m pytest tutor/tests/e2e/ -v                  ← E2E smoke tests (new)
10. python -m ruff check tutor/
11. python -m ruff format --check tutor/
12. If anything fails in 8-11: fix, re-run
13. python scripts/run_review.py --spec specs/v3/dayN.md  ← review agents (new)
14. Write a fixes file for every non-obvious bug found and fixed during the session:
      - Use the next available number: fixes/fix0NN.md
      - Include: symptom, root cause, fix (with code snippet), test added, rules for
        future work
      - Write "none needed" in the report if nothing surprising was encountered
      - NEVER skip this step — fixes files are permanent project memory
15. Report:
      - acceptance criteria checklist (PASS / FAIL for each)
      - gate status (all green / what failed)
      - files changed (list)
      - fixes files written (list, or "none")
16. STOP — do not merge to main; the human reviews findings + diff + screenshots
```

Note: steps 6–11 use `python` (Linux inside container), not `py` (Windows host).
When running on host directly, use `py` as before.

Never skip step 15. Never merge autonomously.

---

## Current State

v3 specs — all completed and merged to main.

| Day | Spec | Status |
|-----|------|--------|
| 13 | `specs/v3/day13.md` — Exact timing capture | Merged |
| 14 | `specs/v3/day14.md` — Dialogue-aware visual segment planner | Merged |
| 15 | `specs/v3/day15.md` — HTML slide renderer (Playwright + Jinja2) | Merged |
| 16 | `specs/v3/day16.md` — Full pipeline integration | Merged |

v4 workflow upgrade — all completed and merged to main. See `dev_setup_update/update_plan.md`.

| Day | Spec | Goal | Status |
|-----|------|------|--------|
| 0  | `dev_setup_update/specs/day0.md`  | Repository cleanup | Merged |
| 1  | `dev_setup_update/specs/day1.md`  | Docker image | Merged |
| 2  | `dev_setup_update/specs/day2.md`  | Container wrapper + settings | Merged |
| 2b | `dev_setup_update/specs/day2b.md` | Launcher modes (retired in v6) | Merged |
| 3  | `dev_setup_update/specs/day3.md`  | Review pipeline + product check | Merged |
| 4  | `dev_setup_update/specs/day4.md`  | Dev_setup documentation | Merged |
| 5  | `dev_setup_update/specs/day5.md`  | E2E smoke tests | Merged |
| 6  | `dev_setup_update/specs/day6.md`  | CI/CD update | Merged |
| 7  | `dev_setup_update/specs/day7.md`  | CLAUDE.md update (this file) | Merged |

---

## Hard Rules

```
NEVER commit to main directly
NEVER change files not listed in the spec
NEVER branch sandbox/dayN off another sandbox branch (always branch from main)
NEVER skip the merge gate (full pytest + ruff)
NEVER merge — human merges after review
NEVER start Day N+1 until Day N is merged to main
NEVER skip writing a fixes file after finding and fixing a non-obvious bug
```

---

## Commands Reference

```powershell
# ── Start a spec day ─────────────────────────────────────────
git checkout main
git checkout -b sandbox/day<N>

# ── Run a spec day ───────────────────────────────────────────
# Implement one spec (Docker, no review):
python scripts/learnx_dk.py --spec specs/v5/dayN.md

# Implement one spec and run review:
python scripts/learnx_dk.py --spec specs/v5/dayN.md --review

# Run all specs in a version with review:
python scripts/learnx_dk.py --version v5 --review

# Explore / ask questions (host, read-only, no Docker):
python scripts/learnx_dk.py --explore

# ── Scoped test run (fast feedback) ──────────────────────────
# Inside container:      python -m pytest tutor/tests/<folder>/ -v
# On host (legacy):      py -m pytest tutor/tests/<folder>/ -v

# ── Merge gate (run before reporting done) ───────────────────
py -m pytest tutor/tests/ --ignore=tutor/tests/e2e/   # unit tests
py -m pytest tutor/tests/e2e/ -v                       # E2E smoke tests
py -m ruff check tutor/
py -m ruff format --check tutor/

# ── Review pipeline ──────────────────────────────────────────
python scripts/run_review.py --spec specs/v3/day<N>.md

# ── Rebuild Docker image (only when requirements.txt changes) ─
docker build -t learnx-dev .

# ── Merge (human runs this, not the agent) ───────────────────
git checkout main
git merge sandbox/day<N>
git branch -d sandbox/day<N>

# ── Discard a bad sandbox branch ────────────────────────────
git checkout main
git branch -D sandbox/day<N>
```

---

## Fix File Protocol

Write a fix file whenever a non-obvious bug is found and fixed — during a spec day,
a review cycle, or a standalone fix session. Do not wait to be asked.

**When to write one:**
- A bug was found where the root cause was not immediately obvious from reading the code
- A workaround was required for an environment quirk, API edge case, or tool behaviour
- A regression test was added to prevent the bug recurring

**When NOT to write one:**
- The fix was a trivial typo or obviously wrong literal
- The issue was already covered by an existing fixes file

**Required sections (use fixes/fix031.md as a template):**

```
# fixNNN — one-line description

**Date:** YYYY-MM-DD

## Symptom
What went wrong from the user's perspective.

## Root cause
Why it happened — include the specific line(s) and the reasoning gap.

## Fix
What changed — include a before/after code snippet.

## Test added
Name and purpose of the regression test.

## Rules for future work
1–3 actionable rules to prevent the same class of bug.
```

**Numbering:** check the highest existing number in `fixes/` and increment by 1.
Pad to three digits: `fix036.md`, not `fix36.md`.

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
