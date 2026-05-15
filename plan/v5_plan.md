# LearnX v5 — Version-Level Yolo (Multi-Spec Execution)

## The problem with v4

v4's yolo mode runs one spec file per invocation:

```powershell
python scripts/learnx_dk.py --mode yolo --spec specs/v4/day5.md
```

This means:
- Human launches the run
- Claude implements the spec (~20–40 minutes)
- Human reads the report
- Human launches the next spec

A version (e.g., v5) might contain 10 spec days. With v4, running all 10 requires
the human to be present 10 times. That is not "walk away" — that is babysitting
with longer intervals.

The current design also treats one spec day as the unit of autonomy. But a single
spec day finishes within one Claude session. The real opportunity is running an
entire roadmap version autonomously — all 10 specs, sequential, no human between
them.

---

## How version-level yolo works

```powershell
python scripts/learnx_dk.py --mode yolo --version v5
```

This finds all spec files in `specs/v5/` (sorted by day number), then runs them
in sequence. Each spec gets:

1. Its own fresh Docker container session
2. Its own validation run (pytest + ruff)
3. Its own review (5-agent review)
4. Its own checkpoint commit

Between specs: no human input required. The launcher reads the next spec and
starts immediately.

### Execution model

```
for each spec in specs/v5/ (sorted):
    open fresh Docker container
    Claude implements the spec
    run validation
    if validation fails: attempt one fix session, then mark spec FAILED
    run 5-agent review
    commit checkpoint
    print per-spec summary line
    continue to next spec

print consolidated report for all specs
send notification (if configured)
```

### Per-spec fresh session

Each spec starts with a clean Docker container. No state, no history, no context
from the previous spec. This is the context hygiene guarantee. A spec that
implements confusing or wrong code does not pollute the next spec's session.

### Consolidated report

After all specs complete, the launcher prints:

```
── v5 Execution Summary ─────────────────────────────────────
  day1 — Docker as default                  ✓ MERGE READY   22 min
  day2 — Generic dev loop framework         ✓ MERGE READY   34 min
  day3 — Session timeouts                   ✓ MERGE READY   18 min
  day4 — Notifications                      ✗ NEEDS FIXES   41 min
  day5 — Two-phase review                   ✓ MERGE READY   29 min
─────────────────────────────────────────────────────────────
  5/5 specs completed · 1 needs fixes · Total: 2h24m
```

Specs marked `NEEDS FIXES` require human review. All others are ready to merge.

### Targeting a single spec (still supported)

```powershell
python scripts/learnx_dk.py --mode yolo --spec specs/v5/day3.md
```

Single-spec execution still works. `--version` and `--spec` are mutually exclusive.

---

## What changes

| Component | Change |
|---|---|
| `scripts/learnx_dk.py` | `run_yolo_version()` — iterates specs in a version directory |
| `scripts/learnx_dk.py` | `--version` flag; mutual exclusion with `--spec` |
| `scripts/learnx_dk.py` | Per-spec result collection; consolidated report |
| `scripts/learnx_dk.py` | Branch management: one branch per spec (`sandbox/v5-day1`, etc.) |

---

## What does not change

- Spec file format is unchanged
- Single-spec yolo (`--spec`) still works
- Docker isolation unchanged
- Review pipeline unchanged
- Human merges (does not change — the yolo report tells human what is ready)

---

## Expected outcome

Write 10 spec files for v5. Start yolo before bed:

```powershell
python scripts/learnx_dk.py --mode yolo --version v5
```

Wake up to a consolidated report. 8 specs are `MERGE READY`. 2 need fixes.
Open the 2 PRs with issues, read the findings, fix. Merge the other 8 cleanly.
