# LearnX v7 — Generic Dev Loop Framework

## The problem with v6

v6 makes Docker the default and simplifies the launcher. But the launcher is
still hardcoded to LearnX-CLI. It knows about:

- `tutor/tests/` — the test directory
- `tutor/tests/e2e/` — the E2E suite
- `scripts/run_review.py` — the review agents
- The learnx-dev Docker image
- `specs/` — the spec directory layout
- ruff — the linter

This coupling means the dev loop cannot be used for any other project. If you
want to use the same "write spec → Docker → validate → review → commit" loop
for a different codebase (a Go API, a React app, a data pipeline), you must
fork the launcher and change it by hand.

The dev loop mechanism is generic. The domain-specific parts are:
- What Docker image to run
- What validation commands to run
- What review agents to use
- Where spec files live
- What E2E tests (if any) to run

These should be configuration, not code.

---

## The redesign

The launcher reads a `devloop.toml` file at the project root. This file defines
all the domain-specific parts. The launcher itself contains zero project-specific
knowledge.

### `devloop.toml`

```toml
[project]
name = "LearnX"
docker_image = "learnx-dev"
specs_dir = "specs"
workspace = "/workspace"

[validation]
unit_tests = "python -m pytest tutor/tests/ --ignore=tutor/tests/e2e/ -m 'not slow' -v"
e2e_tests = "python -m pytest tutor/tests/e2e/ -v"
lint = "python -m ruff check tutor/"
format_check = "python -m ruff format --check tutor/"

[review]
agents_dir = ".claude/agents"
review_script = "scripts/run_review.py"

[notify]
# Optional — see v9 plan
# webhook = "https://hooks.example.com/learnx"
# telegram_token_env = "NOTIFY_TELEGRAM_TOKEN"
# telegram_chat_id_env = "NOTIFY_TELEGRAM_CHAT_ID"
```

### What the generic launcher does

```
read devloop.toml
build Docker command using project.docker_image + project.workspace
for each spec in --version (or single --spec):
    open Docker session → Claude implements
    run validation.unit_tests
    run validation.lint + validation.format_check
    if --e2e: run validation.e2e_tests
    if --review: run review.review_script --spec <file>
    commit checkpoint
report
```

The launcher never imports tutor, never references `tutor/tests/`, never mentions
ruff by name. All of that is in `devloop.toml`.

### Using the loop on a different project

A Go REST API project would have:

```toml
[project]
name = "MyAPI"
docker_image = "myapi-dev"
specs_dir = "docs/specs"
workspace = "/app"

[validation]
unit_tests = "go test ./..."
lint = "golangci-lint run ./..."

[review]
agents_dir = ".claude/agents"
review_script = "scripts/run_review.py"
```

Same launcher. Zero changes to `learnx_dk.py`.

---

## Separation of concerns

```
scripts/learnx_dk.py     ← generic orchestration (no project knowledge)
devloop.toml             ← project config (images, commands, paths)
.claude/agents/          ← review agent definitions (project-specific prompts)
scripts/run_review.py    ← review executor (reads agents/, generic runner)
tutor/tests/e2e/         ← LearnX-specific E2E suite (domain code, not loop code)
```

The loop and the domain are cleanly separated. Updating the review agents does
not require changing the launcher. Adding a new validation command is one line
in `devloop.toml`, not a code change.

---

## What changes

| Component | Change |
|---|---|
| `scripts/learnx_dk.py` | Remove all hardcoded paths and commands; read from `devloop.toml` |
| `devloop.toml` | New file at project root; documents all LearnX-specific config |
| `scripts/run_review.py` | Accept `--agents-dir` and `--spec` from `devloop.toml` config |
| `scripts/tests/` | Update launcher tests for config-driven behavior |

---

## What does not change

- `tutor/` source code unchanged
- `tutor/tests/e2e/` unchanged
- `.claude/agents/` unchanged
- Review agent prompts unchanged
- Spec format unchanged
- Branch strategy unchanged

---

## Expected outcome

A new project can adopt this dev loop by:
1. Copying `scripts/learnx_dk.py` (or installing it as a package)
2. Writing a `devloop.toml` for their project
3. Writing `.claude/agents/` review definitions
4. Running: `python scripts/learnx_dk.py --version v1`

No forking, no hacking the launcher, no project-specific code in the loop.
