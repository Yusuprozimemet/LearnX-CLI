# Day 7 — CLAUDE.md Update

## Goal

`CLAUDE.md` is the first file every new Claude session reads. It defines the project
context, workflow rules, and commands reference. The current version describes the
pre-v4 workflow: no Docker, no E2E tests, no review agents, and the day 13–16 status
table still says "not started."

After this day, `CLAUDE.md` reflects the complete v4 workflow so that any future Claude
session starts with the correct mental model without needing verbal correction.

Four sections need updating:
1. **Project Layout** — add `scripts/`, `dev_setup_update/`, note `ralphex/` is removed
2. **Safe Implementation Loop** — add Docker step and E2E test step
3. **Current State table** — update days 13–16 status to "merged"; add note about v4 workflow
4. **Commands Reference** — add container and E2E commands; fix `py -m pytest` to include E2E

---

## Done (merge gate)

```powershell
py -m pytest tutor/tests/ --ignore=tutor/tests/e2e/ -v
py -m ruff check tutor/
```

Report: paste gate output. List each acceptance criterion.
Stop: do not merge to main — wait for human review.

---

## Data boundary

```
Modifies (existing):
  CLAUDE.md               ← update four sections described below

Does NOT touch:
  tutor/                  ← no application code
  scripts/                ← no changes
  .claude/                ← no settings changes
  dev_setup/              ← dev_setup documentation was updated in Day 4
  Dockerfile              ← no changes
```

---

## Changes to `CLAUDE.md`

### 1. Project Layout section

Replace the current layout block with:

```
specs/          versioned spec files — source of truth for all code
  v0/ v1/ v2/   completed versions (kept for regression reference)
  v3/           completed: day13.md, day14.md, day15.md, day16.md

plan/           version-level design documents
  v0_plan.md … v3_plan.md

fixes/          post-mortem notes for surprises (fix001.md … fix017.md)
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

### 2. Safe Implementation Loop section

Replace the current 12-step loop with:

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
14. Report:
      - acceptance criteria checklist (PASS / FAIL for each)
      - gate status (all green / what failed)
      - files changed (list)
      - surprises encountered: any non-obvious env quirk, API edge case, or tool
        gotcha you hit during the session — one bullet per item, with context.
        Write "none" if nothing surprised you.
        Do NOT write to fixes/ — just list them here for the human to decide.
15. STOP — do not merge to main; the human reviews findings + diff + screenshots
```

Note: steps 6–11 use `python` (Linux inside container), not `py` (Windows host).
When running on host directly, use `py` as before.

### 3. Current State table

Replace the current status table with:

```
v3 specs — all completed and merged to main.

| Day | Spec | Status |
|-----|------|--------|
| 13 | `specs/v3/day13.md` — Exact timing capture | Merged |
| 14 | `specs/v3/day14.md` — Dialogue-aware visual segment planner | Merged |
| 15 | `specs/v3/day15.md` — HTML slide renderer (Playwright + Jinja2) | Merged |
| 16 | `specs/v3/day16.md` — Full pipeline integration | Merged |

v4 workflow upgrade — in progress. See `dev_setup_update/update_plan.md`.

| Day | Spec | Goal | Status |
|-----|------|------|--------|
| 0 | `dev_setup_update/specs/day0.md` | Repository cleanup | Not started |
| 1 | `dev_setup_update/specs/day1.md` | Docker image | Not started |
| 2 | `dev_setup_update/specs/day2.md` | Container wrapper + settings | Not started |
| 3 | `dev_setup_update/specs/day3.md` | Review pipeline + product check | Not started |
| 4 | `dev_setup_update/specs/day4.md` | Dev_setup documentation | Not started |
| 5 | `dev_setup_update/specs/day5.md` | E2E smoke tests | Not started |
| 6 | `dev_setup_update/specs/day6.md` | CI/CD update | Not started |
| 7 | `dev_setup_update/specs/day7.md` | CLAUDE.md update (this file) | Not started |

Start with Day 0. Each day depends on the previous being merged to main.
```

### 4. Commands Reference section

Replace the current commands block with:

```powershell
# ── Start a spec day ─────────────────────────────────────────
git checkout main
git checkout -b sandbox/day<N>

# ── Run agent inside container (v4 workflow — no permission prompts) ──
python scripts/learnx_dk.py

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

## Acceptance criteria

- [ ] `CLAUDE.md` Project Layout section shows `scripts/`, `dev_setup_update/`, and `tests/e2e/`
- [ ] `CLAUDE.md` Project Layout section does NOT mention `ralphex/`
- [ ] `CLAUDE.md` Safe Implementation Loop has 15 steps including Docker and E2E
- [ ] Step 4 mentions `python scripts/learnx_dk.py`
- [ ] Step 9 mentions `python -m pytest tutor/tests/e2e/`
- [ ] Step 13 mentions `python scripts/run_review.py`
- [ ] Step 14 report format lists "surprises encountered" with instruction not to write to `fixes/`
- [ ] Current State table shows days 13–16 as "Merged"
- [ ] Current State table shows v4 upgrade days 0–7 with "Not started" or correct status
- [ ] Commands Reference includes `python scripts/learnx_dk.py`
- [ ] Commands Reference includes `py -m pytest tutor/tests/e2e/`
- [ ] Commands Reference includes `python scripts/run_review.py`
- [ ] Commands Reference includes `docker build -t learnx-dev .`
- [ ] All existing unit tests still pass

---

## Tests

This day edits only `CLAUDE.md`. No new pytest functions.
Validation: read each updated section against the acceptance criteria above.
