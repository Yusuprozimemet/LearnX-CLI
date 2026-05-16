# Day 6 — CI/CD Update

## Goal

The current GitHub Actions workflow (`.github/workflows/ci.yml`) runs only ruff lint.
It does not run pytest at all, and it uses Python 3.11 while the project targets 3.12.

After this day, CI runs three jobs in sequence:
1. **lint** — ruff check + format (existing, updated to Python 3.12)
2. **unit-tests** — full pytest suite excluding e2e (fast; no external deps)
3. **e2e-tests** — smoke tests using the committed test fixture (requires Playwright + ffmpeg)

Every push to every branch runs lint and unit tests. E2E tests run on pushes to `main`
and on pull requests targeting `main` — same trigger as before but with tests added.

CI now enforces the same merge gate as the local workflow. A branch cannot merge to main
if CI is red. The "human reads diff and decides" step is still required, but CI makes
the minimum quality bar automatic.

---

## Done (merge gate)

```powershell
# Confirm no Python or tutor code was accidentally changed
py -m pytest tutor/tests/ --ignore=tutor/tests/e2e/ -v
py -m ruff check tutor/

# CI file is valid YAML (GitHub Actions will reject malformed YAML silently)
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
```

Report: paste all outputs and list each acceptance criterion.
Stop: do not merge to main — wait for human review.

---

## Data boundary

```
Modifies (existing):
  .github/workflows/ci.yml     ← add unit-test and e2e-test jobs; fix Python version

Does NOT touch:
  tutor/                 ← no application code
  scripts/               ← no changes
  .claude/               ← no settings changes
  dev_setup/             ← no documentation changes
  Dockerfile             ← no changes
```

---

## `.github/workflows/ci.yml` — full replacement

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
          python-version: "3.12"

      - name: Install ruff
        run: pip install "ruff>=0.4"

      - name: Check style
        run: ruff check tutor/

      - name: Check formatting
        run: ruff format --check tutor/

  unit-tests:
    name: Unit Tests
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          pip install -r tutor/requirements.txt
          pip install -r tutor/requirements-dev.txt

      - name: Run unit tests
        run: python -m pytest tutor/tests/ --ignore=tutor/tests/e2e/ -v

  e2e-tests:
    name: E2E Smoke Tests
    runs-on: ubuntu-latest
    needs: unit-tests
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install system dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y ffmpeg

      - name: Install Python dependencies
        run: |
          pip install -r tutor/requirements.txt
          pip install -r tutor/requirements-dev.txt

      - name: Install Playwright browsers
        run: python -m playwright install chromium --with-deps

      - name: Run E2E smoke tests
        run: python -m pytest tutor/tests/e2e/ -v
        env:
          # LLM calls are mocked in conftest.py — no real key needed
          ANTHROPIC_API_KEY: "test-key-not-used"
```

---

## Why three jobs, not one

**Separation of feedback:** if lint fails, the developer sees "lint failed" immediately
without waiting for a 3-minute test run. If unit tests fail, e2e tests don't run — no
point verifying product quality if the code is broken.

**Speed:** lint is seconds; unit tests are ~30 seconds; e2e tests are 2–3 minutes.
Running them in sequence means fast failures stay fast.

**`needs:` dependency:** `unit-tests` needs `lint`; `e2e-tests` needs `unit-tests`.
If lint fails, no test jobs start. Both must be green before e2e runs.

---

## Why E2E tests run on every PR to main, not every push

E2E tests take 2–3 minutes and run real ffmpeg and Playwright. Running them on every
push to every branch (including sandbox/dayN branches mid-implementation) would add
noise and slow down the feedback loop. The trigger matches the existing PR filter:
`branches: ["main", "v*-*"]` — same as before for pull_request.

For `push:` events, all three jobs run on `branches: ["**"]` because the push trigger
already matched "**" for lint, and adding tests here catches issues in sandbox branches
before they become PRs. If this proves too slow, narrow `push:` to `["main", "sandbox/**"]`.

---

## Acceptance criteria

- [ ] `.github/workflows/ci.yml` is valid YAML (python yaml.safe_load passes)
- [ ] `lint` job uses Python 3.12 (not 3.11)
- [ ] `unit-tests` job exists and runs `python -m pytest tutor/tests/ --ignore=tutor/tests/e2e/`
- [ ] `unit-tests` job depends on `lint` (`needs: lint`)
- [ ] `e2e-tests` job exists and runs `python -m pytest tutor/tests/e2e/`
- [ ] `e2e-tests` job installs ffmpeg via apt-get
- [ ] `e2e-tests` job installs Playwright chromium
- [ ] `e2e-tests` job depends on `unit-tests` (`needs: unit-tests`)
- [ ] `e2e-tests` job sets `ANTHROPIC_API_KEY` env var to a dummy value
- [ ] All existing pytest unit tests still pass locally

---

## Tests

This day changes only a YAML config file. No new pytest functions.
Validation: run the three commands in the Done section and verify each acceptance criterion.
