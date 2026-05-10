# LearnX Dev Setup — Start Here

Four pillars govern all work on this project. Read this page first; follow links for depth.

## The Four Pillars

| Pillar | One-liner | Detail |
|---|---|---|
| Spec-driven | The spec is the source of truth — implement exactly what it says | [spec-driven_plan.md](spec-driven_plan.md) |
| Context hygiene | One spec · one session · one branch — no context bleed | [context_hygiene_plan.md](context_hygiene_plan.md) |
| Sandbox | Branch from `main`; never work on `main` directly | [sandbox_plan.md](sandbox_plan.md) |
| Autonomy | Run tests yourself; iterate until green; stop and report | [autonomy_plan.md](autonomy_plan.md) |

## Minimal Workflow (every spec day)

```powershell
# 1. Start clean
git checkout main
git checkout -b sandbox/day<N>

# 2. Read the spec fully before touching any code
#    specs/v3/day<N>.md

# 3. Implement → test → fix loop
py -m pytest tutor/tests/<folder>/ -v   # scoped; fix failures; repeat

# 4. Merge gate — must be fully clean before reporting done
py -m pytest
py -m ruff check tutor/
py -m ruff format --check tutor/

# 5. Report each acceptance criterion (pass/fail) + paste gate output
#    STOP — do not merge; human reviews and merges
```

## Starting a New Session

Use the pre-filled handoff prompt in [handoff_template.md](handoff_template.md).
Copy it verbatim, paste it as the first message of the new session.

## Before Starting Any v3 Day

Read these four files — they contain constraints that are NOT in the specs:

- `fixes/fix001.md` — ffmpeg not on PATH (causes silent test failures on Windows)
- `fixes/fix013.md` — timing inflation root cause (why Day 13 exists)
- `fixes/fix009.md` — per-unit loudnorm breaks video audio duration
- `plan/v3_plan.md` — architectural rationale for the whole v3 approach
