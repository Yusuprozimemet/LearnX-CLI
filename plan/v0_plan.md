# LearnX v0 — Engineering Foundations

## What v0 is

v0 is not a feature version. It is the set of cross-cutting engineering practices
that make the codebase trustworthy, consistent, and easy to contribute to — across
all feature versions.

v1 (audio), v2 (video), and v3 (conversation-driven slides) are feature milestones.
v0 is the baseline they all sit on. Some of it is already in place. This document
audits what exists, names the real gaps, and closes them in priority order.

The guiding principle: **fix what is missing, don't add what isn't needed.**
Every item below has a specific problem it solves in this codebase. Nothing is
included because it "looks professional" in the abstract.

---

## What is already solid

Before listing gaps, name what works so it is not accidentally "improved" away.

| Concern | Current state |
|---|---|
| Separation of concerns | Each module has one job; clear boundary between audio and video sessions |
| Concurrency | TTS rendering uses `asyncio` + semaphore — already async where it matters |
| LLM caching | MD5-keyed file cache in `.tutor_cache/`; `no_cache` flag to bust it |
| LLM error handling | Every LLM call has a `_fallback_*` path; parse errors never crash |
| Spec-driven development | Every feature has a written spec reviewed before implementation |
| Test coverage | 115 tests across ingestion, generation, audio, player, and visual |
| Config management | `llm_config.toml` for model names and limits; `.env` for secrets |
| Data isolation | `audio/<session>/` and `video/<session>/` never bleed into each other |

These are not problems. v0 does not refactor them.

---

## The actual gaps

### 1 — No CI

There is no GitHub Actions workflow. Linting errors accumulate silently and are
only caught when someone remembers to run ruff manually.

CI at this stage has one job: fast lint. Running the full test suite or type
checker in CI adds minutes to every push for no practical gain — tests are run
locally before pushing, and CodeRabbit handles automated code review on PRs.

**What is missing:**
```
.github/
  workflows/
    ci.yml      ← ruff check + ruff format --check on every push
```

**Fix:** One workflow, one lint job, under 15 seconds. No external services.

---

### 2 — `pyproject.toml` is almost empty

The current `pyproject.toml` contains only pytest configuration:
```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tutor/tests"]
```

There is no package name, version, dependency list, build system, or tool
configuration. `pip install -e .` does not work. A contributor cannot set up
the project cleanly without reading source files to discover dependencies.

**Fix:** Complete `pyproject.toml` — build system, runtime deps, dev deps group,
entry point (`learnx`), ruff and mypy configuration.

---

### 3 — No linting or formatting configuration

`ruff` is not configured and not enforced anywhere. There is no `[tool.ruff]`
section in `pyproject.toml`. Style inconsistencies accumulate silently.

**Fix:** Add `[tool.ruff]` and `[tool.ruff.lint]` to `pyproject.toml`. Run
`ruff format` once to establish a clean baseline. CI enforces it on every push.

---

### 4 — Type hints exist but mypy is not configured

The code uses type annotations throughout but there is no mypy configuration.
Some annotations are incorrect or incomplete (notably `VisualSpec.diagram_spec: object`
and `ShellContext.player: object`). These provide documentation value but no enforcement.

mypy is a **local developer tool** in v0 — it is not added to CI. Running the full
type checker on every push is time-consuming and the fix burden (strict mode on an
existing codebase) is not worth the gain at this stage. Configure it, fix the most
egregious errors, run it manually before PRs.

**Fix:** Add `[tool.mypy]` to `pyproject.toml`. Fix the known incorrect annotations.
Document that `mypy tutor/` should pass before opening a PR.

---

### 5 — No pre-commit hooks

There is no `.pre-commit-config.yaml`. The feedback loop for lint errors is:
commit → push → CI fail → fix → push again. Pre-commit hooks shorten this to:
commit → auto-fix → done.

**Fix:** `.pre-commit-config.yaml` with ruff format and ruff check. mypy is
intentionally excluded — too slow for a commit hook.

---

### 6 — Session listing shows too little

`/sessions` shows names and file sizes. It does not show duration, video status,
or date. `tutorial.meta.json` is already written at generate time but only holds
`source_file`. This is a one-line change at write time and a small rewrite of the
display.

**Fix:** Add `generated_at` and `total_duration_s` to `tutorial.meta.json` at the
end of `/generate`. Rewrite `/sessions` to show duration, `[video]` badge, and date.

---

## What v0 explicitly does NOT include

| Recommendation | Why not |
|---|---|
| pytest in CI | Tests run in ~6 s locally. Running them in CI adds pipeline time with no practical benefit for a single-developer project. Run before pushing. |
| mypy in CI | Type-checking an existing codebase under strict mode requires a dedicated cleanup sprint. It is not a lightweight CI gate. Run locally before PRs. |
| FastAPI / web API | The CLI is the product. A web layer triples the codebase for zero benefit until there is a user who requires it. |
| Redis / Celery | The full pipeline runs in ~45 s on one machine. Distributed workers solve a problem that does not exist yet. |
| PostgreSQL / Alembic | File-based sessions are self-contained and portable. A database adds an operational dependency and breaks the `audio/<session>/` mental model. |
| Prometheus / OpenTelemetry | Observability infrastructure for a single-user CLI. File logging is sufficient and already in place. |
| Plugin system for TTS | No demand for multiple providers. Build the abstraction when a second provider is needed, not before. |
| Docker | Useful for a server. LearnX installs in 5 minutes on a laptop. Containerising a local CLI adds complexity with no benefit until there is a server to run. |

The pattern: each item solves a problem this project does not have yet.

---

## Implementation

### Week 1 — Packaging and CI (highest return, lowest risk)

1. Complete `pyproject.toml` — build system, deps, entry point, ruff config
2. Run `ruff format tutor/` — clean baseline, single standalone commit
3. Add `.github/workflows/ci.yml` — one lint job, under 15 s
4. Add CI badge to README

### Week 2 — Type safety (local)

5. Add `[tool.mypy]` to `pyproject.toml`
6. Fix known incorrect annotations (`diagram_spec`, `ShellContext.player`, `LLMFn`)
7. Run `mypy tutor/` and fix remaining errors module by module
8. Document: "run `mypy tutor/` before opening a PR"

### Week 3 — Pre-commit and session UX

9. Add `.pre-commit-config.yaml` — ruff format + ruff check
10. Add `generated_at` + `total_duration_s` to `tutorial.meta.json`
11. Rewrite `/sessions` to show duration, video badge, and date

---

## Outcome

After v0, the codebase will have:

| Concern | Before | After |
|---|---|---|
| Lint enforced | Never | Every push (CI) + every commit (pre-commit) |
| Type errors caught | At runtime | Before PRs (mypy locally) |
| Clean install | Does not work | `pip install -e .[dev]` |
| Session metadata | Name + file size | + duration + video badge + date |

v3 implementation begins on this baseline.
