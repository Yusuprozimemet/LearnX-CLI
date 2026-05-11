# Day 1 — Docker Foundation

## Goal

Create a Docker image for LearnX development that contains Python 3.12, ffmpeg, and
Claude Code. The image must be able to run the full pytest suite and ruff linting against
the mounted project directory. This container is the execution environment that all
subsequent days depend on.

No changes to any `tutor/` code. No changes to `.claude/settings.json`. This day is
pure infrastructure — a Dockerfile and a .dockerignore file.

---

## Done (merge gate)

```powershell
# Build the image
docker build -t learnx-dev .

# Run pytest inside the container against your local code
docker run --rm -v "${PWD}:/workspace" learnx-dev python -m pytest tutor/tests/ -v

# Run ruff inside the container
docker run --rm -v "${PWD}:/workspace" learnx-dev python -m ruff check tutor/

# Confirm ffmpeg is available (pydub requires it)
docker run --rm learnx-dev ffmpeg -version

# Confirm Claude Code CLI is installed
docker run --rm learnx-dev claude --version
```

All five commands must exit 0. Report: paste exit codes and pytest summary line.
Stop: do not merge to main — wait for human review.

---

## Data boundary

```
Creates (new):
  Dockerfile          ← image definition
  .dockerignore       ← keeps context small; excludes audio/, __pycache__, .git

Does NOT touch:
  tutor/              ← no application code changes
  .claude/            ← no settings changes
  dev_setup/          ← no documentation changes
  requirements.txt    ← read but not modified
```

---

## Dockerfile — full content

```dockerfile
# Stage 1: build base with system tools
FROM python:3.12-slim

# System tools
# - nodejs/npm: required by Claude Code CLI
# - ffmpeg: required by pydub (audio processing)
# - git: required for branch operations inside container
# - curl: for any download steps
RUN apt-get update && apt-get install -y \
    nodejs npm \
    ffmpeg \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI globally
RUN npm install -g @anthropic-ai/claude-code

# Create non-root user matching typical host UID
RUN useradd -m -u 1000 dev

# Install Python dependencies from project requirements
# requirements.txt is copied here so the layer is cached; the project
# itself is mounted at runtime and never copied into the image.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

USER dev
WORKDIR /workspace
```

---

## .dockerignore — full content

```
# Large generated directories — not needed in build context
audio/
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.ruff_cache/

# Version control
.git/
.gitignore

# Dev environment
.venv/
*.egg-info/

# OS noise
.DS_Store
Thumbs.db
```

---

## Why these choices

**python:3.12-slim not python:3.12-alpine** — pydub's ffmpeg bindings compile more
reliably on Debian-based images. Alpine's musl libc causes intermittent issues with
audio libraries. Slim is smaller than full but avoids Alpine compatibility problems.

**npm install -g @anthropic-ai/claude-code** — same method ralphex uses in its published
Docker image. Claude Code requires Node.js at runtime; installing via npm is the official
distribution method.

**COPY requirements.txt only (not the full project)** — project code is mounted at
runtime via `-v "${PWD}:/workspace"`. Copying only requirements.txt keeps the layer
cached across code changes. Rebuilding the image is only needed when dependencies change.

**useradd -u 1000** — files created by the container inside the mounted volume will be
owned by UID 1000. On most Linux hosts this matches the primary user. On Windows with
Docker Desktop the ownership mapping is handled by Docker automatically.

---

## Acceptance criteria

- [ ] `docker build -t learnx-dev .` completes with exit code 0
- [ ] `docker run --rm -v "${PWD}:/workspace" learnx-dev python -m pytest tutor/tests/ -v` exits 0 (all tests green)
- [ ] `docker run --rm -v "${PWD}:/workspace" learnx-dev python -m ruff check tutor/` exits 0
- [ ] `docker run --rm learnx-dev ffmpeg -version` exits 0 (ffmpeg is on PATH)
- [ ] `docker run --rm learnx-dev claude --version` exits 0 (Claude Code CLI installed)
- [ ] `.dockerignore` excludes `audio/`, `__pycache__/`, `.git/`, `.venv/`
- [ ] Image runs as non-root user (`whoami` returns `dev`, not `root`)
- [ ] `Dockerfile` is at the project root, not inside any subdirectory

---

## Tests

This day creates infrastructure files, not Python application code. There are no new
pytest functions. Validation is the five `docker run` commands in the Done section.

Run them in order. If `docker build` fails, fix the Dockerfile before proceeding.
If pytest fails inside the container but passes on the host, the cause is a missing
dependency in requirements.txt or a PATH issue — check `pip list` inside the container.
