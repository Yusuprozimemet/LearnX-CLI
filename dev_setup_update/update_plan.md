# LearnX Dev Workflow Upgrade — v4 Plan

## What This Upgrades

The current 4-pillar workflow (spec-driven, context hygiene, sandbox, autonomy) is sound
in design but has two operational gaps:

**Gap 1 — Sandbox is a git branch, not an execution container.**
The deny rules in `.claude/settings.json` interrupt the implement→test→fix loop with
permission prompts. Docker replaces those guardrails with a container boundary: the
agent lives inside the container, can only touch `/workspace`, and runs with
`--dangerously-skip-permissions` — zero prompts, same safety.

**Gap 2 — Tests verify code logic, not product quality.**
Unit tests mock pydub, mock ffmpeg, mock the LLM. A passing test suite tells you the
code is internally consistent. It does not tell you the video has audio, the slides
rendered with fonts loaded, or the A/V sync is within human tolerance. These are
product quality failures that only a real pipeline run can catch.

The upgrade fixes both gaps. The four pillars do not change. Specs, context hygiene,
git branches, and exit conditions stay exactly the same.

---

## Why Now

**Gap 1 — senior developer feedback:**

> "When I was talking about sandbox, I meant to run agent inside docker container.
> You have container with your code. Agent is inside and then you go full YOLO.
> For example you can skip those denies — idea here is to reduce time spent on approving changes."

**Gap 2 — your own experience:**

> "Last times, I ran agents without looking at the actual results. Even all tests passed,
> looks everything is working, but the presentation looks awful, audio is not heard on the video."

Both gaps have the same root: the testing and execution environment is not the real
environment. Docker fixes the execution environment; E2E smoke tests fix the test environment.

Reference: ralphex (github.com/umputun/ralphex) documents its own version of this:
"Unit tests mock external calls. After ANY code changes, run e2e test with a toy project
to verify actual claude/codex integration and output streaming."

---

## The Three Layers of Verification

```
Layer 1 — Unit tests (already have)
  What they catch:  wrong return values, missing fields, off-by-one errors
  What they miss:   anything that depends on real ffmpeg, real audio, real browser

Layer 2 — E2E smoke tests (Day 5 adds this)
  What they catch:  silent audio in video, blank slides, broken CSS, A/V sync drift,
                    missing output files, pipeline crashes on real input
  What they miss:   subjective quality (rhythm, voice, curriculum clarity)
  How they work:    run the real pipeline on a tiny fixed test document,
                    assert on actual output using ffprobe + pydub + Playwright

Layer 3 — Human review (unchanged)
  What it catches:  curriculum quality, slide aesthetics, natural speech rhythm,
                    anything subjective
  When it runs:     after E2E smoke tests pass; human watches/listens to the output
```

The rule: **before any merge, all three layers must pass**. Unit tests alone are not enough.

---

## What Changes

| Component | Before | After |
|-----------|--------|-------|
| Sandbox unit | git branch only | git branch + Docker container |
| Agent permissions | allow list + deny list; prompts on risky ops | 4 modes: supervised / assisted / container / yolo |
| Test coverage | unit tests only | unit tests + E2E smoke tests |
| Output verification | none | ffprobe (audio/video streams), pydub (silence detection), Playwright (slide screenshots) |
| Review step | human reads diff | automated multi-agent review + product verification, then human decides |
| Autonomy level | Level 2–3 | Level 4 (hand off spec, walk away, come back to result + smoke test output) |
| Institutional memory (`fixes/`) | updated manually when human remembers | agents flag candidates in review output; human decides what gets written |

---

## Upgrade Sequence

| Day | Spec | Deliverable | Depends on |
|-----|------|-------------|------------|
| 0 | `specs/day0.md` | Repository cleanup: untrack output files, gitignore ralphex/ | nothing |
| 1 | `specs/day1.md` | Docker image: Python 3.12 + ffmpeg + Claude Code, pytest passes inside | Day 0 merged |
| 2 | `specs/day2.md` | `scripts/learnx_dk.py` wrapper + settings.json overhaul | Day 1 merged |
| 2b | `specs/day2b.md` | Multi-mode launcher: supervised/assisted/container/yolo | Day 2 merged |
| 3 | `specs/day3.md` | Multi-agent review + product verification agent | Day 2b merged |
| 4 | `specs/day4.md` | Updated dev_setup docs: container workflow documented | Day 3 merged |
| 5 | `specs/day5.md` | E2E smoke test suite: real pipeline on test fixture, ffprobe + Playwright | Day 4 merged |
| 6 | `specs/day6.md` | CI/CD: add pytest + e2e jobs to GitHub Actions, fix Python 3.11 → 3.12 | Day 5 merged |
| 7 | `specs/day7.md` | CLAUDE.md update: reflect v4 workflow, new commands, updated merge gate | Day 6 merged |

Never start Day N+1 until Day N is merged to main.

---

## The New Workflow (After Day 5)

```
Start a spec day (unchanged):
  git checkout main
  git checkout -b sandbox/dayN

Run implementation (inside container — no prompts):
  python scripts/learnx_dk.py
  → agent implements, runs pytest, fixes, reports when unit tests green

Run E2E smoke tests (new — before review):
  python -m pytest tutor/tests/e2e/ -v
  → real pipeline runs on test fixture
  → ffprobe checks audio stream in output video
  → Playwright screenshots slide renders
  → pydub checks audio is not silent
  → ALL must pass before proceeding to review

Run review (new — agents check code AND product):
  python scripts/run_review.py --spec specs/v3/dayN.md
  → code review agents: quality, implementation, testing, simplification
  → product check agent: runs pipeline, verifies output, screenshots slides
  → every agent appends "Suggested Fix Notes" for novel surprises
  → human reads findings + diff + screenshots + fix note candidates

Update fixes/ (new — optional, human only):
  if a finding is a novel env/API/tool gotcha not obvious from code:
    write fixes/fixNNN.md
  otherwise: skip (code or tests already explain it)

Human merge (unchanged):
  git checkout main
  git merge sandbox/dayN
  git branch -d sandbox/dayN
```

The new merge gate is:
```powershell
py -m pytest                          # unit tests
py -m pytest tutor/tests/e2e/ -v     # E2E smoke tests — new
py -m ruff check tutor/
py -m ruff format --check tutor/
```

---

## What You Were Missing

| Gap | Symptom | Fix |
|-----|---------|-----|
| No real pipeline execution in tests | Silent audio in video passes all tests | E2E smoke test runs real ffmpeg, checks audio stream with ffprobe |
| No output quality verification | Slide CSS doesn't load, looks broken | Playwright screenshots the rendered HTML slide, checks for visible content |
| No silence detection | Audio present but inaudible (encoding bug) | pydub checks max amplitude of output audio > threshold |
| No A/V sync check | Audio and slides drift apart | Compare audio duration from pydub to total timing from timing.json |
| Review agents check code, not product | Agent reports LGTM, video is broken | Product check agent actually runs the pipeline during review |
| No test fixture document | E2E tests have no stable input | Committed `tutor/tests/e2e/fixtures/sample.md` (tiny, deterministic) |
| Institutional memory has no update loop | Hard-won fixes/ knowledge gets lost after sessions end | Agents flag "Suggested Fix Notes" in review output; human decides what enters fixes/ |

---

## Hard Rules (Unchanged)

```
NEVER commit to main directly
NEVER start Day N+1 until Day N is green
NEVER merge — human merges after review
NEVER skip the merge gate (unit tests + E2E + ruff)
NEVER change files not listed in the spec
```

---

## Where to Find Things After Upgrade

| Question | Where to look |
|---|---|
| How to run agent in container | `dev_setup/container_plan.md` |
| What the four launcher modes do | `dev_setup_update/specs/day2b.md` + banner in `scripts/learnx_dk.py` |
| Why deny rules were removed from default | `.claude/settings.json` (comment block at top) |
| How review agents work | `.claude/agents/README.md` |
| What E2E smoke tests verify | `dev_setup_update/specs/day5.md` + `tutor/tests/e2e/README.md` |
| Full workflow cheat sheet | `dev_setup/handoff_template.md` (container-mode section) |
| When to write a new fix note | `dev_setup_update/architecture.md` (Institutional Memory section) |
| What existing fix notes cover | `fixes/fix001.md` … `fixes/fix0NN.md` — read before any spec day |
