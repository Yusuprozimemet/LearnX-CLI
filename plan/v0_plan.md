# LearnX v0 — Engineering Foundations

## What v0 is

v0 is not a feature version. It is the set of cross-cutting engineering practices
that make the codebase trustworthy, consistent, and easy to contribute to — across
all feature versions.

v1 (audio), v2 (video), and v3 (conversation-driven slides) are feature milestones.
v0 is the baseline they all sit on. Some of it is already in place. This document
audits what exists, names the real gaps, and closes them in priority order.

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

**The single most important gap.**

115 tests exist but run only manually. There is no GitHub Actions workflow. This means:
- A PR can merge with broken tests and nobody knows
- The "115 tests" claim in the README has no automation behind it
- Linting and type errors accumulate silently

**What is missing:**
```
.github/
  workflows/
    ci.yml      ← ruff check + mypy + pytest on every push and PR
```

**Fix:** One workflow file. Three steps. No external services.

---

### 2 — `pyproject.toml` is almost empty

The current `pyproject.toml` contains only pytest configuration:
```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tutor/tests"]
```

There is no:
- Package name, version, or description
- Dependency list (`pydub`, `edge-tts`, `pillow`, `groq`, etc.)
- Build system (`[build-system]`)
- Tool configurations for ruff and mypy

`pip install learnx-cli` does not work. `pip install -e .` does not work. A contributor
cannot install the project cleanly from the repository.

**Fix:** Complete `pyproject.toml` with Hatchling as the build backend, all runtime
dependencies pinned to minimum versions, and dev dependencies in an optional group.

---

### 3 — No linting or formatting configuration

`ruff` is not configured and not enforced. There is no `[tool.ruff]` section in
`pyproject.toml`. Style inconsistencies are fixed manually, inconsistently, or not at all.

**Fix:** Add `[tool.ruff]` and `[tool.ruff.lint]` to `pyproject.toml`. Run `ruff format`
across the codebase once to establish a clean baseline. After that, CI enforces it.

---

### 4 — Type hints exist but mypy is not configured

The code uses type annotations throughout, but:
- There is no `mypy.ini` or `[tool.mypy]` configuration
- mypy is not in the CI pipeline
- Some annotations are incorrect or incomplete (particularly in the visual pipeline added in v2)

This means the type hints provide documentation value but no enforcement. Type errors
accumulate until something breaks at runtime.

**Fix:** Add `[tool.mypy]` to `pyproject.toml` with strict settings. Fix all existing
mypy errors. After that, CI blocks any new type errors.

---

### 5 — No pre-commit hooks

There is no `.pre-commit-config.yaml`. Contributors can commit code that fails ruff
or mypy, which then fails in CI. The feedback loop is: commit → push → CI fail → fix →
push again. Pre-commit hooks move the feedback loop to before the commit.

**Fix:** `.pre-commit-config.yaml` with two hooks: `ruff format` and `ruff check --fix`.
mypy is intentionally kept in CI only (too slow for pre-commit).

---

### 6 — Session listing shows too little

`/sessions` prints session names and unit counts. It does not show:
- Total audio duration
- Whether a video (`full_session.mp4`) exists
- When the session was generated

This is not a feature gap — `tutorial.meta.json` already exists and is written at
generate time. It just does not capture duration or timestamp.

**Fix:** Write `generated_at` (ISO 8601) and `total_duration_s` to `tutorial.meta.json`
at the end of `/generate`. Update `/sessions` to read and display them.

---

## What v0 explicitly does NOT include

These are real engineering practices. They are not right for this project at this scale.

| Recommendation | Why not |
|---|---|
| FastAPI / web API | The CLI is the product. A web layer triples the codebase for zero benefit until there is a user who requires a web interface. |
| Redis / Celery | The full pipeline runs in ~45 s on one machine. Distributed workers solve a concurrency problem that does not exist yet. |
| PostgreSQL / Alembic | File-based sessions are self-contained and portable. A database migration breaks the clean `audio/<session>/` mental model and introduces a new operational dependency. |
| Prometheus / OpenTelemetry | Observability infrastructure for whom? This is a single-user CLI. File logging is sufficient and already in place. |
| Plugin system for TTS providers | No current demand for multiple providers. `edge-tts` works. Build the abstraction when a second provider is needed, not before. |
| Docker | Useful for a server deployment. LearnX installs in 5 minutes on a laptop. Containerising a local CLI adds complexity with no benefit until there is a server to run. |
| Pydantic-settings | The current `.env` + TOML config works. Adding a third config layer costs more than it saves at this scale. |
| Dependency injection framework | The codebase already passes `llm_fn: Callable` as a function argument — that is dependency injection. A DI container is not needed. |

The pattern: every item above solves a scaling or deployment problem. LearnX does not
have scaling or deployment problems. It has engineering quality gaps that are far simpler
to fix.

---

## Implementation

### Week 1 — CI and linting (highest return, lowest risk)

1. Complete `pyproject.toml`:
   - `[project]` with name, version, description, Python ≥ 3.11
   - All runtime dependencies with minimum versions
   - `[project.optional-dependencies]` dev group: ruff, mypy, pytest, pytest-asyncio
   - `[project.scripts]` entry point: `learnx = tutor.__main__:main`
   - `[tool.ruff]` and `[tool.ruff.lint]` configuration
2. Run `ruff format .` — establish clean baseline, commit as a single formatting commit
3. Add `.github/workflows/ci.yml`:
   - Trigger: push and pull_request to main and v*-* branches
   - Jobs: `ruff check` → `pytest` (two jobs, run in parallel)
4. Add CI badge to README

### Week 2 — Type safety

5. Add `[tool.mypy]` to `pyproject.toml` — strict, exclude `tutor/tests/`
6. Run `mypy tutor/` — collect all errors
7. Fix errors module by module: `models.py` first, then `infra/`, then `generation/`,
   then `visual/`; `tests/` is excluded from strict checking
8. CI now runs mypy as a third job

### Week 3 — Pre-commit and session UX

9. Add `.pre-commit-config.yaml` with ruff format + ruff check
10. Document setup in README: `pre-commit install`
11. Add `generated_at` + `total_duration_s` to `tutorial.meta.json` at generate time
12. Rewrite `/sessions` output:
    ```
    LearnX > /sessions
      week2_3     4 units  26:14  [video]  2026-05-09
      week3_1     3 units  18:42           2026-05-07
    ```

---

## Outcome

After v0, the codebase will have:

| Concern | Before | After |
|---|---|---|
| Tests run automatically | Never | Every push and PR |
| Type errors caught | At runtime | In CI before merge |
| Style enforced | Manually | Pre-commit + CI |
| Clean install | Does not work | `pip install -e .[dev]` |
| Session metadata | Name + unit count | + duration + video status + date |

These changes do not add features. They make the existing 115 tests and type hints
do the job they were written for. v3 implementation should be built on this baseline.
