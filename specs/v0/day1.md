# Day 1 — Continuous Integration

## Goal

Add a GitHub Actions CI workflow that runs on every push and pull request.
Every check that currently requires a human to run manually should run automatically.
After this day, the "115 tests" claim in the README has a badge behind it.

---

## What CI must enforce

| Check | Tool | Why |
|---|---|---|
| Code style | `ruff check` + `ruff format --check` | Catch lint errors and unformatted code before review |
| Test suite | `pytest` | Catch regressions on every push |
| No check runs twice | Parallel jobs | Fast feedback — total wall time ≤ 3 min |

Type checking (mypy) is added to CI in Day 2 after the type errors are fixed.
Adding it before the errors are fixed would make every existing push fail.

---

## File — `.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches: ["**"]
  pull_request:
    branches: ["main", "v*-*"]

jobs:
  lint:
    name: Lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install ruff
        run: pip install "ruff>=0.4"

      - name: Check style
        run: ruff check tutor/

      - name: Check formatting
        run: ruff format --check tutor/

  test:
    name: Test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip

      - name: Install dependencies
        run: pip install -e ".[dev]"

      - name: Run tests
        run: pytest --tb=short
        env:
          SDL_VIDEODRIVER: dummy
          SDL_AUDIODRIVER: dummy
```

### Design decisions

**`branches: ["**"]` for push** — CI runs on every branch, not just `main`. A
broken feature branch is caught before a PR is opened.

**`branches: ["main", "v*-*"]` for pull_request** — PRs targeting `main` or any
version branch (e.g. `v2-visual-pipeline`) trigger CI. PRs to other branches do not.

**`SDL_VIDEODRIVER: dummy` + `SDL_AUDIODRIVER: dummy`** — pygame requires a display
and audio device to initialise. Without these env vars, importing pygame on a
headless CI runner raises `pygame.error: No available video device`. Setting both
to `dummy` gives pygame a fake device so imports succeed and player state-machine
tests run without a real display.

**`cache: pip`** — caches pip's download cache keyed by the Python version and
`pyproject.toml` hash. Saves 30–60 s on repeated runs.

**Two separate jobs (lint, test)** — they run in parallel. A lint failure does not
block the test job. Both statuses appear independently in the PR checks panel.

---

## README badge

Add to `README.md` immediately below the `# LearnX CLI` heading:

```markdown
![CI](https://github.com/Yusuprozimemet/LearnX-CLI/actions/workflows/ci.yml/badge.svg)
```

Place it on its own line, before the description paragraph. This badge reflects
the `main` branch status by default.

---

## Branch protection (recommended, not enforced by this spec)

After CI is green on `main`, enable branch protection in GitHub settings:

- Require status checks: `Lint`, `Test`
- Require branches to be up to date before merging
- Do not require administrator bypass

This converts CI from informational to blocking.

---

## Acceptance criteria

- [ ] `.github/workflows/ci.yml` exists with `lint` and `test` jobs
- [ ] Lint job runs `ruff check` and `ruff format --check` — both pass on current code
- [ ] Test job runs `pytest --tb=short` — passes 115+ tests
- [ ] Both jobs triggered on push to any branch
- [ ] Both jobs triggered on PR to `main` or `v*-*` branches
- [ ] `SDL_VIDEODRIVER=dummy` and `SDL_AUDIODRIVER=dummy` set in test job
- [ ] `pip` cache enabled in test job
- [ ] CI badge added to `README.md`
- [ ] First workflow run on push shows both jobs green

## Local verification before pushing

```bash
# Simulate the lint job locally
ruff check tutor/
ruff format --check tutor/

# Simulate the test job locally
pytest --tb=short

# Verify the workflow file is valid YAML
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
```
