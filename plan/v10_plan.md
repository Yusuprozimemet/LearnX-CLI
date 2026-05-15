# LearnX v10 — Two-Phase Review

## The problem with v9

The current review pipeline (5 agents) runs once, at the end of each spec's
implementation. All 5 agents see the same diff at the same time. There is no
iteration. If agent 3 finds missing tests, Claude does not fix them before
agent 5 runs. Agent 5 reviews code that agent 3 already flagged as incomplete.

More critically: after the 5-agent review finds issues and Claude applies fixes,
there is no verification step. The pipeline asks "what is wrong?" but never asks
"were those wrongs actually fixed?" The gate reports `MERGE READY` based on
whether Claude said it fixed things — not based on whether the fixes are correct.

This is a single-pass review. A two-pass review catches more.

---

## How two-phase review works

### Phase 1 — Issue discovery (existing 5 agents, unchanged)

Same as today. 5 agents review the diff independently. Claude is asked to fix
all findings. Fix commits are made.

Output: a list of findings per agent, a set of fix commits.

### Phase 2 — Fix verification (2 new agents)

Phase 2 runs only after phase 1 produced actionable findings. If phase 1 found
nothing, phase 2 is skipped entirely.

Phase 2 sees:
- Phase 1's original findings list (what was wrong)
- The diff of the fix commits (what changed after phase 1)

**Phase 2 Agent A — Fix completeness:**
For each phase 1 finding: was it fully resolved, partially resolved, or not addressed?

**Phase 2 Agent B — Regression check:**
Did the phase 1 fixes introduce any new problems that were not in the original diff?

Phase 2 produces a verdict: `VERIFIED` or `STILL FAILING` (with list of unresolved items).

### Gate logic

```
Phase 1: 0 findings → gate = MERGE READY (skip phase 2)
Phase 1: N findings → Claude fixes → Phase 2:
    Phase 2 VERIFIED     → gate = MERGE READY
    Phase 2 STILL FAILING → gate = NEEDS FIXES (list unresolved items)
```

### Report structure

```
── Review: sandbox/v5-day2 ──────────────────────────────────
Phase 1 (issue discovery):
  Code quality:     2 findings — fixed
  Spec compliance:  0 findings
  Test coverage:    1 finding  — fixed
  Simplification:   1 finding  — fixed
  Security:         0 findings

Phase 2 (verification):
  Fix completeness: VERIFIED (4/4 issues resolved)
  Regression check: VERIFIED (no new issues introduced)

Gate: MERGE READY
```

### Config

Phase 2 agents are defined in `.claude/agents/` like phase 1 agents.
Phase 2 can be disabled per-project in `devloop.toml`:

```toml
[review]
agents_dir = ".claude/agents"
review_script = "scripts/run_review.py"
two_phase = true          # default: true; set false to skip phase 2
```

---

## Why not external review (codex)?

ralphex uses codex as its phase 2 external reviewer, requiring a separate
installation and API key. The same verification value is achieved here with
two Claude agents and a different prompt focus. No new external dependency.
An optional `external_reviewer` flag is reserved for a future version.

---

## What changes

| Component | Change |
|---|---|
| `scripts/run_review.py` | `run_phase1()` and `run_phase2()` functions |
| `scripts/run_review.py` | Phase 2 skip logic when phase 1 produces no findings |
| `.claude/agents/` | Two new agent files: `verify_fixes.md`, `regression_check.md` |
| `scripts/learnx_dk.py` | `run_yolo()` calls phase 2 after phase 1 fix commits |
| `devloop.toml` | `two_phase` toggle in `[review]` |

---

## What does not change

- Phase 1 agents and their prompts — unchanged
- The 5-agent lineup — unchanged
- Branch strategy and commit flow — unchanged
- The human still merges — nothing changes there
