#!/usr/bin/env python3
"""
learnx-dk.py — Run Claude Code inside the learnx-dev Docker container.

Usage:
    python scripts/learnx_dk.py [--dry-run] [extra claude flags]

The container mounts the current directory at /workspace and your ~/.claude
credentials read-only. Claude runs with --dangerously-skip-permissions so the
implement→test→fix loop is uninterrupted.

Safety: the container can only write to /workspace (this repo). It cannot
reach your home directory, SSH keys, other repos, or the Docker daemon.
"""

import os
import pathlib
import subprocess
import sys


IMAGE = "learnx-dev"
WORKSPACE = "/workspace"


def _to_posix(p: pathlib.Path) -> str:
    """Convert Windows path to forward-slash form Docker accepts."""
    return p.as_posix()


def build_command(
    project_dir: pathlib.Path,
    home_dir: pathlib.Path,
    extra_args: list[str],
) -> list[str]:
    claude_dir = home_dir / ".claude"
    gitconfig = home_dir / ".gitconfig"

    cmd = [
        "docker", "run", "--rm", "-it",
        "-v", f"{_to_posix(project_dir)}:{WORKSPACE}",
    ]

    if claude_dir.exists():
        cmd += ["-v", f"{_to_posix(claude_dir)}:/home/dev/.claude:ro"]

    if gitconfig.exists():
        cmd += ["-v", f"{_to_posix(gitconfig)}:/home/dev/.gitconfig:ro"]

    for var in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
                "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
        if var in os.environ:
            cmd += ["-e", f"{var}={os.environ[var]}"]

    cmd += ["-w", WORKSPACE, IMAGE]
    cmd += ["claude", "--dangerously-skip-permissions"] + extra_args

    return cmd


def main(argv: list[str] | None = None) -> None:
    if argv is None:
        argv = sys.argv[1:]

    dry_run = "--dry-run" in argv
    extra = [a for a in argv if a != "--dry-run"]

    project_dir = pathlib.Path.cwd()
    home_dir = pathlib.Path.home()

    cmd = build_command(project_dir, home_dir, extra)

    if dry_run:
        print(" ".join(cmd))
        return

    subprocess.run(cmd, check=False)


if __name__ == "__main__":
    main()
