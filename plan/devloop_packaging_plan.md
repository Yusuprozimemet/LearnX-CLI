# DevLoop Packaging & Distribution Plan

**Goal:** Make `devloop` installable as a global CLI command on Windows, macOS, and
Ubuntu from a single source — no manual PATH editing, no venv activation, no
`python scripts/devloop.py` invocations.

---

## The Method: pipx

`pipx` installs Python CLI tools in isolated environments and puts them on PATH
automatically. It is the standard way to distribute Python CLI tools globally.

```
pipx install .           # install from local repo
pipx install devloop     # install from PyPI (once published)
devloop --help           # works immediately, no activation needed
```

`pipx` works identically on Windows (PowerShell), macOS (zsh/bash), and Ubuntu
(bash). It ships with Python 3.11+ on macOS/Ubuntu and is one command to add on
Windows (`winget install pipx` or `pip install pipx`).

---

## pyproject.toml Changes

The existing `pyproject.toml` (used for the tutor package) needs a `devloop` entry
point added:

```toml
[project]
name = "devloop"
version = "0.1.0"
description = "Spec-driven development loop for Claude Code projects"
requires-python = ">=3.12"
dependencies = [
    "typer>=0.12",
    "rich>=13",          # colour output, tables, spinners
]

[project.scripts]
devloop = "devloop.main:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

The `tutor` package and the `devloop` package live in the same repo but are
separate installable packages. Users who only want the CLI install `devloop`;
users who want to develop LearnX install both.

---

## Installation Instructions (per platform)

### Windows (PowerShell)

```powershell
# 1. Install pipx (one time)
pip install pipx
pipx ensurepath          # adds ~/.local/bin to PATH; restart terminal after

# 2. Install devloop
cd C:\Users\you\LearnX-CLI
pipx install .

# 3. Verify
devloop --version
devloop --help
```

### macOS

```zsh
# 1. Install pipx (one time)
brew install pipx        # or: pip install pipx
pipx ensurepath

# 2. Install devloop
cd ~/LearnX-CLI
pipx install .

# 3. Verify
devloop --version
devloop --help
```

### Ubuntu

```bash
# 1. Install pipx (one time)
sudo apt install pipx    # Ubuntu 23.04+; or: pip install --user pipx
pipx ensurepath

# 2. Install devloop
cd ~/LearnX-CLI
pipx install .

# 3. Verify
devloop --version
devloop --help
```

---

## Upgrading After Code Changes

While the tool is still in the same repo (pre-PyPI):

```
pipx reinstall devloop   # picks up all code changes
```

Later, once published to PyPI:

```
pipx upgrade devloop
```

---

## Shell Completion

After installing, users get tab-completion in one command:

```powershell
devloop --install-completion   # PowerShell, bash, zsh, fish — auto-detected
```

Typer generates and installs the completion script automatically.

---

## Two Packages, One Repo

This repo will contain two installable packages:

| Package | Install command | Provides |
|---|---|---|
| `tutor` | `pip install .` | `python -m tutor` (LearnX CLI) |
| `devloop` | `pipx install .` | `devloop` (global CLI tool) |

They share the same `pyproject.toml` or use separate ones under subdirectories.
Simplest approach: one `pyproject.toml` at root that declares both entry points,
users install whichever they need.

---

## Docker Prerequisite Check

When `devloop run` or `devloop version` is invoked, the tool checks that Docker is
running before attempting anything:

```
$ devloop run specs/v11/day32.md
✗ Docker is not running. Start Docker Desktop and try again.
```

Platform-specific check:
- **Windows/macOS**: `docker info` — Docker Desktop must be running
- **Ubuntu**: `docker info` — Docker daemon must be running (`systemctl start docker`)

This replaces the current silent failure where the container command just hangs or
errors cryptically.

---

## CI / GitHub Actions

The existing CI runs `py -m pytest`. After this plan it also runs:

```yaml
- name: Install devloop
  run: pip install .

- name: Smoke-test CLI
  run: devloop --help && devloop config
```

This confirms the entry point is wired correctly on every push.

---

## PyPI Publishing (future, not this plan)

When ready to share publicly:

```
pipx run build           # builds wheel + sdist
pipx run twine upload dist/*
```

Then anyone installs with `pipx install devloop`. Not needed now — local install
from the repo is sufficient.

---

## Summary

| Step | Action |
|---|---|
| Restructure | Move `scripts/dk/` → `devloop/core/`, add `devloop/cli/`, add `devloop/main.py` |
| Package | Update `pyproject.toml` with `devloop` entry point and `typer`/`rich` deps |
| Install | `pipx install .` on each machine (Windows, macOS, Ubuntu) |
| Upgrade | `pipx reinstall devloop` after code changes |
| Completion | `devloop --install-completion` once per machine |
| CI | Add `pip install . && devloop --help` smoke test |
