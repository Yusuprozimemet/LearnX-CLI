# DevLoop — Workflow Instructions

> For LearnX CLI product context (tutor/ architecture, code quality rules) see **CLAUDE.md**.

DevLoop is the build system for developing LearnX CLI. It runs Claude in a Docker
container, manages spec-driven sessions, orchestrates the review pipeline, and handles
rate limits and timeouts. The launcher is `scripts/devloop.py`.

---

## Development Workflow — The Four Pillars

This project uses **Spec-Driven Development**. All four pillars must be active:

### 1. Spec-Driven
- The spec file is the source of truth. Read it completely before touching any code.
- A spec has: Goal, Data boundary, Models, Algorithm, Acceptance criteria, Test names.
- Implement exactly what the spec says. Do not add features, do not guess design.
- If the spec is ambiguous, stop and report — do not invent a resolution.

### 2. Context Hygiene
- One spec per session. Do not carry Day N context into a Day N+1 session.
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
1.  Read the spec completely (specs/vN/dayN.md)
2.  git checkout main
3.  git checkout -b sandbox/dayN
4.  Start the container session:
      python scripts/devloop.py
    (or run directly on host for quick one-off tasks)
5.  Implement only the files listed in the spec's "Data boundary"
6.  python -m pytest tutor/tests/<relevant_folder>/ -v    ← scoped run (inside container)
7.  If failures: read output, fix, go to step 6
8.  python -m pytest                                       ← full unit suite
9.  python -m pytest tutor/tests/e2e/ -v                  ← E2E smoke tests
10. python -m ruff check tutor/
11. python -m ruff format --check tutor/
12. If anything fails in 8-11: fix, re-run
13. python scripts/run_review.py --spec specs/vN/dayN.md  ← review agents
14. Write a fixes file for every non-obvious bug found and fixed during the session
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

v4 DevLoop upgrade — all completed and merged to main. See `plan/v4_update_plan.md`.

| Day | Spec | Goal | Status |
|-----|------|------|--------|
| 0  | `specs/v4-workflow/day0.md`  | Repository cleanup | Merged |
| 1  | `specs/v4-workflow/day1.md`  | Docker image | Merged |
| 2  | `specs/v4-workflow/day2.md`  | Container wrapper + settings | Merged |
| 2b | `specs/v4-workflow/day2b.md` | Launcher modes (retired in v6) | Merged |
| 3  | `specs/v4-workflow/day3.md`  | Review pipeline + product check | Merged |
| 4  | `specs/v4-workflow/day4.md`  | Dev_setup documentation | Merged |
| 5  | `specs/v4-workflow/day5.md`  | E2E smoke tests | Merged |
| 6  | `specs/v4-workflow/day6.md`  | CI/CD update | Merged |
| 7  | `specs/v4-workflow/day7.md`  | CLAUDE.md update | Merged |

v10–v11 DevLoop enhancements — completed and merged.

| Day | Spec | Goal | Status |
|-----|------|------|--------|
| 28 | `specs/v10/day28.md` | Two-phase review (phase 1 discovery) | Merged |
| 29 | `specs/v10/day29.md` | Two-phase review (phase 2 verification) | Merged |
| 30 | `specs/v11/day30.md` | Dashboard: OutputBuffer + DashboardServer | Merged |
| 31 | `specs/v11/day31.md` | Dashboard: wire into version run + --serve flag | In review |

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
NEVER let a file exceed 400 LOC — split first, then commit
```

---

## Commands Reference

```powershell
# ── Start a spec day ─────────────────────────────────────────
git checkout main
git checkout -b sandbox/day<N>

# ── Run a spec day ───────────────────────────────────────────
# Implement one spec (Docker, no review):
python scripts/devloop.py --spec specs/v5/dayN.md

# Implement one spec and run review:
python scripts/devloop.py --spec specs/v5/dayN.md --review

# Run all specs in a version with review:
python scripts/devloop.py --version v5 --review

# Explore / ask questions (host, read-only, no Docker):
python scripts/devloop.py --explore

# ── Scoped test run (fast feedback) ──────────────────────────
# Inside container:      python -m pytest tutor/tests/<folder>/ -v
# On host (legacy):      py -m pytest tutor/tests/<folder>/ -v

# ── Merge gate (run before reporting done) ───────────────────
py -m pytest tutor/tests/ --ignore=tutor/tests/e2e/   # unit tests
py -m pytest tutor/tests/e2e/ -v                       # E2E smoke tests
py -m ruff check tutor/
py -m ruff format --check tutor/

# ── Review pipeline ──────────────────────────────────────────
python scripts/run_review.py --spec specs/vN/day<N>.md

# ── Rebuild Docker image (only when requirements.txt changes) ─
docker build -t learnx-dev .

# ── Merge (human runs this, not the agent) ───────────────────
git checkout main
git merge sandbox/day<N>
git branch -d sandbox/day<N>

# ── Discard a bad sandbox branch ─────────────────────────────
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
