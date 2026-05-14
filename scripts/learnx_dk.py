#!/usr/bin/env python3
"""
learnx_dk.py — Multi-mode Claude Code launcher for LearnX.

Usage:
    python scripts/learnx_dk.py [--mode MODE] [--dry-run] [--spec PATH]

Modes:
    supervised   Host machine, current settings.json (deny rules active). Default.
    assisted     Host machine, expanded allow, no deny (writes settings.local.json).
    container    Docker container, --dangerously-skip-permissions. Zero prompts.
    yolo         Docker + --dangerously-skip-permissions + auto E2E + auto review.

Examples:
    python scripts/learnx_dk.py                              # supervised
    python scripts/learnx_dk.py --mode assisted
    python scripts/learnx_dk.py --mode container
    python scripts/learnx_dk.py --mode yolo --spec specs/v3/day13.md
    python scripts/learnx_dk.py --mode container --dry-run
"""

import json
import os
import pathlib
import subprocess
import sys

_PY = sys.executable  # venv-aware Python for host post-container steps

# ── constants ────────────────────────────────────────────────────────────────

IMAGE = "learnx-dev"
WORKSPACE = "/workspace"

MODES = ("supervised", "assisted", "container", "yolo")

BANNER = {
    "supervised": "SUPERVISED  — host machine, deny rules active, prompts on risky ops",
    "assisted":   "ASSISTED    — host machine, no deny rules, prompts only for push/merge",
    "container":  "CONTAINER   — Docker, --dangerously-skip-permissions, zero prompts",
    "yolo":       "YOLO        — Docker + auto E2E + auto review after session ends",
}

ASSISTED_PERMISSIONS = {
    "permissions": {
        "allow": [
            "Bash(py -m pytest*)", "Bash(py -m ruff*)", "Bash(python*)",
            "Bash(git status*)", "Bash(git diff*)", "Bash(git log*)",
            "Bash(git add*)", "Bash(git commit*)", "Bash(git checkout*)",
            "Bash(git branch*)", "Bash(git stash*)",
            "Read(*)", "Edit(*)", "Write(*)",
        ]
    }
}

SETTINGS_LOCAL = pathlib.Path(".claude/settings.local.json")

# ── helpers ──────────────────────────────────────────────────────────────────


def _to_posix(p: pathlib.Path) -> str:
    return p.as_posix()


def _print_banner(mode: str) -> None:
    width = 60
    print("-" * width)
    print(f"  learnx_dk  |  {BANNER[mode]}")
    print("-" * width)


def build_docker_command(
    project_dir: pathlib.Path,
    home_dir: pathlib.Path,
    extra_args: list[str],
) -> list[str]:
    """Build the docker run command (unchanged from Day 2)."""
    claude_dir = home_dir / ".claude"
    gitconfig = home_dir / ".gitconfig"

    cmd = [
        "docker", "run", "--rm", "-it",
        "-v", f"{_to_posix(project_dir)}:{WORKSPACE}",
    ]
    if claude_dir.exists():
        cmd += ["-v", f"{_to_posix(claude_dir)}:/home/dev/.claude:ro"]
        # Claude Code writes session state here; anonymous volume keeps .claude read-only
        cmd += ["-v", "/home/dev/.claude/session-env"]
    if gitconfig.exists():
        cmd += ["-v", f"{_to_posix(gitconfig)}:/home/dev/.gitconfig:ro"]

    for var in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
                "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
        if var in os.environ:
            cmd += ["-e", f"{var}={os.environ[var]}"]

    cmd += ["-w", WORKSPACE, IMAGE]
    cmd += ["claude", "--dangerously-skip-permissions"] + extra_args
    return cmd


def build_host_command(extra_args: list[str]) -> list[str]:
    """Build the host claude command (supervised / assisted)."""
    return ["claude"] + extra_args


# kept for backwards-compatibility with Day 2 tests and run_review.py
def build_command(
    project_dir: pathlib.Path,
    home_dir: pathlib.Path,
    extra_args: list[str],
) -> list[str]:
    return build_docker_command(project_dir, home_dir, extra_args)


# ── mode runners ─────────────────────────────────────────────────────────────

def run_supervised(extra_args: list[str], dry_run: bool) -> None:
    cmd = build_host_command(extra_args)
    if dry_run:
        print(" ".join(cmd))
        return
    subprocess.run(cmd, check=False)


def run_assisted(extra_args: list[str], dry_run: bool) -> None:
    cmd = build_host_command(extra_args)
    if dry_run:
        print(f"[writes {SETTINGS_LOCAL}]")
        print(" ".join(cmd))
        print(f"[deletes {SETTINGS_LOCAL}]")
        return
    SETTINGS_LOCAL.write_text(json.dumps(ASSISTED_PERMISSIONS, indent=2))
    try:
        subprocess.run(cmd, check=False)
    finally:
        if SETTINGS_LOCAL.exists():
            SETTINGS_LOCAL.unlink()


def run_container(
    project_dir: pathlib.Path,
    home_dir: pathlib.Path,
    extra_args: list[str],
    dry_run: bool,
) -> None:
    cmd = build_docker_command(project_dir, home_dir, extra_args)
    if dry_run:
        print(" ".join(cmd))
        return
    subprocess.run(cmd, check=False)


def run_yolo(
    project_dir: pathlib.Path,
    home_dir: pathlib.Path,
    spec_path: pathlib.Path | None,
    extra_args: list[str],
    dry_run: bool,
) -> None:
    container_cmd = build_docker_command(project_dir, home_dir, extra_args)
    e2e_cmd = [_PY, "-m", "pytest", "tutor/tests/e2e/", "-v"]
    review_cmd = [_PY, "scripts/run_review.py"]
    if spec_path:
        review_cmd += ["--spec", spec_path.as_posix()]

    if dry_run:
        print("# Step 1 — container session")
        print(" ".join(container_cmd))
        print("# Step 2 — E2E smoke tests (runs after container exits)")
        print(" ".join(e2e_cmd))
        print("# Step 3 — review pipeline")
        print(" ".join(review_cmd))
        return

    print("\n[yolo] starting container session...")
    subprocess.run(container_cmd, check=False)

    print("\n[yolo] container exited — running E2E smoke tests...")
    e2e_result = subprocess.run(e2e_cmd, check=False)

    print("\n[yolo] running review pipeline...")
    subprocess.run(review_cmd, check=False)

    if e2e_result.returncode != 0:
        print("\n[yolo] WARNING: E2E tests had failures — review findings carefully")


# ── CLI ──────────────────────────────────────────────────────────────────────

def _parse(argv: list[str]) -> tuple[str, bool, pathlib.Path | None, list[str]]:
    mode = "supervised"
    dry_run = False
    spec = None
    rest: list[str] = []

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--mode" and i + 1 < len(argv):
            mode = argv[i + 1]; i += 2
        elif arg.startswith("--mode="):
            mode = arg.split("=", 1)[1]; i += 1
        elif arg == "--dry-run":
            dry_run = True; i += 1
        elif arg == "--spec" and i + 1 < len(argv):
            spec = pathlib.Path(argv[i + 1]); i += 2
        elif arg.startswith("--spec="):
            spec = pathlib.Path(arg.split("=", 1)[1]); i += 1
        else:
            rest.append(arg); i += 1

    if mode not in MODES:
        print(f"error: unknown mode '{mode}'. choose from: {', '.join(MODES)}")
        sys.exit(1)

    return mode, dry_run, spec, rest


def main(argv: list[str] | None = None) -> None:
    if argv is None:
        argv = sys.argv[1:]

    mode, dry_run, spec, extra = _parse(argv)
    project_dir = pathlib.Path.cwd()
    home_dir = pathlib.Path.home()

    if not dry_run:
        _print_banner(mode)

    if mode == "supervised":
        run_supervised(extra, dry_run)
    elif mode == "assisted":
        run_assisted(extra, dry_run)
    elif mode == "container":
        run_container(project_dir, home_dir, extra, dry_run)
    elif mode == "yolo":
        run_yolo(project_dir, home_dir, spec, extra, dry_run)


if __name__ == "__main__":
    main()
