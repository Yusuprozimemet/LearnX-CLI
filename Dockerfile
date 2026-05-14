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

# Install Python dependencies.
# requirements.txt lives in tutor/ in this project (not the root).
# Also install playwright, jinja2, Pillow which are in pyproject.toml but
# not in tutor/requirements.txt.
COPY tutor/requirements.txt /tmp/requirements.txt
COPY tutor/requirements-dev.txt /tmp/requirements-dev.txt
# audioop-lts is a Python 3.13+ backport; audioop is in the 3.12 stdlib — skip it.
RUN grep -v audioop-lts /tmp/requirements.txt > /tmp/requirements-filtered.txt && \
    pip install --no-cache-dir \
    -r /tmp/requirements-filtered.txt \
    -r /tmp/requirements-dev.txt \
    "playwright>=1.44" \
    "jinja2>=3.1" \
    "Pillow>=10.0" \
    "ruff>=0.4"

# Install Playwright system dependencies (requires root)
RUN python -m playwright install-deps chromium

USER dev

# Install Playwright browser binary for the dev user
RUN python -m playwright install chromium

WORKDIR /workspace
