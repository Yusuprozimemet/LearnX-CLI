# Day 0 — Project Packaging

## Goal

Replace the near-empty `pyproject.toml` with a complete project definition:
package metadata, all runtime and dev dependencies, build system, entry point,
and tool configuration for ruff. After this day, `pip install -e .[dev]` works
from a clean clone and a contributor has a reproducible dev environment without
consulting any external doc.

This day produces one file change and one one-off command.

---

## The problem

Current `pyproject.toml`:
```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tutor/tests"]
```

Missing: `[project]`, `[build-system]`, `[project.scripts]`, all dependencies,
`[tool.ruff]`. The package is not installable. The entry point `learnx` does not exist.

---

## Target `pyproject.toml`

Complete replacement. Every section is specified below.

### `[build-system]`

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

Hatchling is the build backend recommended by PyPA for new projects. It has no
configuration overhead for a simple single-package layout.

### `[project]`

```toml
[project]
name = "learnx-cli"
version = "0.3.0"
description = "Turn any Markdown document into an audio tutorial and MP4 video"
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }

dependencies = [
    "pydub>=0.25",
    "tqdm>=4.60",
    "python-dotenv>=1.0",
    "openai>=1.30",
    "pygame>=2.5",
    "Pillow>=10.0",
    "edge-tts>=6.1",
]
```

**Version rationale:** v1 (audio) = 0.1, v2 (video) = 0.2, v3 specs written = 0.3.
`requires-python = ">=3.11"` matches the `str | None` union syntax already in the code.

**Dependency versions:** these are minimum compatible versions, not pinned. Pin
in a `requirements-lock.txt` for reproducible installs.

### `[project.optional-dependencies]`

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "ruff>=0.4",
    "mypy>=1.10",
    "pre-commit>=3.7",
    "types-Pillow",
    "types-tqdm",
]
```

All dev tools in one group. `pip install -e .[dev]` installs everything needed
to run tests, lint, and type-check.

`types-Pillow` and `types-tqdm` are mypy stub packages needed for type-checked
code that imports those libraries.

### `[project.scripts]`

```toml
[project.scripts]
learnx = "tutor.cli.shell:run_shell"
```

After install, `learnx` in the terminal launches the shell. No need to run
`python -m tutor`. The existing `python -m tutor` path is kept (via `__main__.py`)
for backward compatibility.

### `[tool.hatch.build.targets.wheel]`

```toml
[tool.hatch.build.targets.wheel]
packages = ["tutor"]
```

Tells Hatchling to package only the `tutor/` directory, not `audio/`, `video/`,
`specs/`, or `plan/`.

### `[tool.pytest.ini_options]`

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths  = ["tutor/tests"]
asyncio_mode = "auto"
```

Add `asyncio_mode = "auto"` — `pytest-asyncio` requires this for automatic
async test discovery. Without it, async tests are silently skipped.

### `[tool.ruff]`

```toml
[tool.ruff]
line-length    = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B"]
ignore = ["E501"]

[tool.ruff.lint.per-file-ignores]
"tutor/tests/**" = ["S101"]
```

**Rule groups:**
- `E`, `W` — pycodestyle errors and warnings
- `F` — pyflakes (unused imports, undefined names)
- `I` — isort (import ordering)
- `UP` — pyupgrade (modernise syntax to py311)
- `B` — bugbear (common Python mistakes)

`E501` (line too long) is ignored in lint because `ruff format` handles wrapping.
`S101` (assert statements) ignored in tests — pytest uses `assert` by design.

---

## Ruff format baseline

After updating `pyproject.toml`, run once:

```
ruff format tutor/
```

Commit the resulting diff as a standalone commit with message:
`style: apply ruff format baseline`

This is a one-time formatting normalisation. After this commit, CI enforces the
same formatting on every future change, so no style noise in later diffs.

---

## Entry point addition — `tutor/__main__.py`

The existing `__main__.py` runs only when invoked as `python -m tutor`. The script
entry point `tutor.cli.shell:run_shell` points directly at `run_shell`, which is
already the main function. No changes needed to `__main__.py`.

Verify after install:
```
pip install -e .[dev]
learnx
```
The LearnX banner should appear.

---

## Acceptance criteria

- [ ] `pip install -e .[dev]` succeeds from a clean clone
- [ ] `learnx` command is available after install and launches the shell
- [ ] `python -m tutor` still works (backward compatibility)
- [ ] `pytest` runs 115+ tests without error after install
- [ ] `ruff check tutor/` reports zero errors after format baseline
- [ ] `ruff format --check tutor/` reports zero diffs after format baseline
- [ ] `pyproject.toml` has `[build-system]`, `[project]`, `[project.scripts]`,
      `[project.optional-dependencies]`, `[tool.ruff]`, `[tool.pytest.ini_options]`
- [ ] No `requirements.txt` left — all deps declared in `pyproject.toml`
- [ ] Format baseline committed separately from the pyproject.toml change

## Verification commands

```bash
pip install -e .[dev]
learnx --help          # or just: learnx
ruff check tutor/
ruff format --check tutor/
pytest
```

All four must pass cleanly.
