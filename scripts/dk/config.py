import pathlib
import sys
import tomllib
from dataclasses import dataclass

_PY = sys.executable

_DEFAULTS: dict = {
    "project": {
        "name": "LearnX",
        "docker_image": "learnx-dev",
        "specs_dir": "specs",
        "workspace": "/workspace",
    },
    "validation": {
        "unit_tests": "python -m pytest tutor/tests/ --ignore=tutor/tests/e2e/ -m 'not slow' -v",
        "e2e_tests": "python -m pytest tutor/tests/e2e/ -v",
        "lint": "python -m ruff check tutor/",
        "format_check": "python -m ruff format --check tutor/",
    },
    "review": {
        "agents_dir": ".claude/agents",
        "review_script": "scripts/run_review.py",
        "two_phase": True,
    },
    "resilience": {
        "session_timeout_minutes": 30,
        "idle_timeout_minutes": 5,
        "rate_limit_wait_minutes": 2,
        "max_retries_per_spec": 1,
        "rate_limit_patterns": [
            "rate limit exceeded",
            "you've hit your limit",
            "429 too many requests",
            "quota exceeded",
        ],
    },
    "notify": {
        "webhook_url": None,
        "telegram_token_env": None,
        "telegram_chat_id_env": None,
        "script": None,
    },
    "dashboard": {
        "default_port": 8080,
    },
}


def _load_config(project_dir: pathlib.Path) -> dict:
    """Load devloop.toml from project_dir; fall back to _DEFAULTS if absent."""
    config_path = project_dir / "devloop.toml"
    if not config_path.exists():
        return _DEFAULTS
    with open(config_path, "rb") as fh:
        raw = tomllib.load(fh)
    config: dict = {}
    for section, defaults in _DEFAULTS.items():
        config[section] = {**defaults, **raw.get(section, {})}
    return config


@dataclass
class SpecResult:
    spec_name: str
    status: str  # "DONE" | "FAILED" | "TIMED_OUT"
    duration_s: float
    branch: str
    retries: int = 0  # rate-limit retries consumed
