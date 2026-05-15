# Day 21 (v6) — Documentation Update (README.md and CLAUDE.md)

## Goal

Update `README.md` and the Commands Reference section of `CLAUDE.md` to reflect
the v6 launcher interface. After day1 removed the four-mode system, the docs still
describe `--mode supervised/assisted/container/yolo`. This day makes the docs match
the code.

No code changes. No new tests.

---

## Done (merge gate)

```powershell
py -m pytest scripts/tests/test_learnx_dk.py -v
py -m ruff check scripts/
py -m ruff format --check scripts/
```

Gate passes because no code changed. Manually verify each documentation acceptance
criterion below before reporting done.

---

## Data boundary

```
Modifies (existing):
  README.md          ← replace "The 4 modes" section and Running a spec day commands
  CLAUDE.md          ← replace Commands Reference section

Does NOT touch:
  scripts/learnx_dk.py        ← code unchanged (done in day1)
  scripts/tests/              ← tests unchanged
  tutor/                      ← application code unchanged
  plan/                       ← plan docs unchanged
```

---

## README.md changes

### Replace "The 4 modes" section

Remove this section entirely:

```markdown
## The 4 modes

| Mode | Where Claude runs | Prompts | Use when |
|------|-------------------|---------|----------|
| `supervised` | host | frequent | exploring, short tasks — **current mode when you open Claude Code directly** |
| `assisted` | host | rare | trusted scope, fewer interruptions |
| `container` | Docker | zero | full spec day, no interruptions |
| `yolo` | Docker + auto review | zero | walk away, come back to a full report |

python scripts/learnx_dk.py                              # supervised (default)
python scripts/learnx_dk.py --mode assisted
python scripts/learnx_dk.py --mode container
python scripts/learnx_dk.py --mode yolo --spec specs/v4/dayN.md

> Always use forward slashes in --spec ...
```

Replace with:

```markdown
## Launcher modes

Docker is the default. Always.

| Command | Effect |
|---|---|
| `python scripts/learnx_dk.py` | Docker container — implement, no review |
| `python scripts/learnx_dk.py --spec X` | Docker — implement spec X, no review |
| `python scripts/learnx_dk.py --spec X --review` | Docker — implement X, then E2E + review |
| `python scripts/learnx_dk.py --version v5 --review` | Docker — run all v5 specs with review |
| `python scripts/learnx_dk.py --explore` | Host only — questions, no code changes |

`--explore` starts Claude on the host with read-only permissions (Read, Grep, Glob,
git read commands). Use it to ask questions about the codebase without risking
accidental edits.

> Always use forward slashes in `--spec`: `specs/v5/day1.md` not `specs\v5\day1.md`.
> Backslashes corrupt the path (`\v` is a vertical-tab character).
```

### Update "Running a spec day" step 4 (dry run) and step 5 (launch)

Step 4 — replace old command:

```markdown
# Old:
python scripts/learnx_dk.py --mode yolo --spec specs/v4/dayN.md --dry-run

# New:
python scripts/learnx_dk.py --spec specs/v5/dayN.md --review --dry-run
```

Step 5 — replace old command:

```markdown
# Old:
python scripts/learnx_dk.py --mode yolo --spec specs/v4/dayN.md

# New:
python scripts/learnx_dk.py --spec specs/v5/dayN.md --review
```

---

## CLAUDE.md changes

### Replace the Commands Reference section

Find the block under `## Commands Reference` and replace the launcher commands:

```powershell
# Old (remove these lines):
# ── Start a spec day ─────────────────────────────────────────
python scripts/learnx_dk.py                         # supervised (default)
python scripts/learnx_dk.py --mode assisted
python scripts/learnx_dk.py --mode container
python scripts/learnx_dk.py --mode yolo --spec specs/v3/day13.md
```

Replace with:

```powershell
# ── Run a spec day ───────────────────────────────────────────
# Implement one spec (Docker, no review):
python scripts/learnx_dk.py --spec specs/v5/dayN.md

# Implement one spec and run review:
python scripts/learnx_dk.py --spec specs/v5/dayN.md --review

# Run all specs in a version with review:
python scripts/learnx_dk.py --version v5 --review

# Explore / ask questions (host, read-only, no Docker):
python scripts/learnx_dk.py --explore
```

### Update the dry-run example in the Commands Reference (if present)

Any reference to `--mode yolo --spec X --dry-run` should become
`--spec X --review --dry-run`.

---

## Acceptance criteria

- [ ] `README.md` no longer mentions `supervised`, `assisted`, `container`, or `yolo` modes
- [ ] `README.md` "Launcher modes" table lists all four new command forms
- [ ] `README.md` step 4 dry-run uses `--spec X --review --dry-run`
- [ ] `README.md` step 5 launch uses `--spec X --review`
- [ ] `CLAUDE.md` Commands Reference no longer uses `--mode` flag
- [ ] `CLAUDE.md` shows `--spec`, `--review`, `--version`, and `--explore` examples
- [ ] No mentions of `supervised`, `assisted`, `container`, `yolo` remain in either file
- [ ] `py -m pytest scripts/tests/ -v` still passes (no code changes)
- [ ] `py -m ruff check scripts/` still passes
