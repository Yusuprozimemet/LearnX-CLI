# Day 1 — Continuous Integration

## Goal

Add a GitHub Actions CI workflow that runs a fast lint check on every push and
pull request. The total CI run time is under 15 seconds.

Code review automation is handled by CodeRabbit, which is already configured on
the repository. CI's only responsibility here is catching lint and formatting
errors that should never reach a reviewer in the first place.

Tests and type checking are run locally before pushing — they are not CI jobs
in v0.

---

## What CI enforces

| Check | Tool | Run time |
|---|---|---|
| Lint errors | `ruff check tutor/` | ~5 s |
| Formatting | `ruff format --check tutor/` | ~3 s |

Nothing else. One job, two commands.

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
```

### Design decisions

**`branches: ["**"]` for push** — lint runs on every branch. A formatting error
on a feature branch is caught before a PR is opened, not after.

**`branches: ["main", "v*-*"]` for pull_request** — PR checks trigger on PRs to
`main` or any version branch (e.g. `v3-conversation-slides`). PRs between
short-lived branches do not trigger CI.

**No dependency install** — ruff is installed directly (`pip install ruff`), not
through `pip install -e .[dev]`. This keeps the lint job fast: no audio, video, or
Pillow dependencies needed to check code style.

**One job, not two** — there is no parallel test job. Lint is fast enough that
running both `ruff check` and `ruff format --check` sequentially in a single job
is simpler than splitting them.

---

## README badge

Add immediately below the `# LearnX CLI` heading:

```markdown
![CI](https://github.com/Yusuprozimemet/LearnX-CLI/actions/workflows/ci.yml/badge.svg)
```

The badge reflects the `main` branch status. It turns red when a push introduces
a lint or formatting error.

---

## Branch protection (recommended)

After CI is green on `main`, enable in GitHub → Settings → Branches:

- Required status check: `Lint`
- Require branch to be up to date before merging

This makes CI blocking rather than informational. One required check, not three.

---

## Acceptance criteria

- [ ] `.github/workflows/ci.yml` exists with a single `lint` job
- [ ] Lint job installs only ruff — no other dependencies
- [ ] `ruff check tutor/` passes on current codebase
- [ ] `ruff format --check tutor/` passes on current codebase (after day0 format baseline)
- [ ] Workflow triggers on push to any branch
- [ ] Workflow triggers on PR to `main` or `v*-*`
- [ ] No test job, no typecheck job
- [ ] CI badge added to `README.md`
- [ ] First push after adding the workflow shows the lint job green

## Local verification before pushing

```bash
ruff check tutor/
ruff format --check tutor/

# Verify the workflow file is valid YAML
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
```
