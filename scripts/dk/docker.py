import os
import pathlib
import shlex
import sys

from scripts.dk.config import _DEFAULTS

IMAGE = "learnx-dev"
WORKSPACE = "/workspace"
SETTINGS_LOCAL = pathlib.Path(".claude/settings.local.json")

EXPLORE_PERMISSIONS = {
    "permissions": {
        "allow": [
            "Read(*)",
            "Glob(*)",
            "Grep(*)",
            "Bash(git status*)",
            "Bash(git log*)",
            "Bash(git diff*)",
            "Bash(git branch*)",
        ]
    }
}


def _to_posix(p: pathlib.Path) -> str:
    return p.as_posix()


def build_docker_command(
    project_dir: pathlib.Path,
    home_dir: pathlib.Path,
    extra_args: list[str],
    image: str = IMAGE,
    workspace: str = WORKSPACE,
    interactive: bool = True,
) -> list[str]:
    """Build the docker run command."""
    claude_dir = home_dir / ".claude"
    claude_json = home_dir / ".claude.json"
    gitconfig = home_dir / ".gitconfig"

    cmd = ["docker", "run", "--rm"]
    if interactive:
        cmd.append("-it")
    cmd += ["-v", f"{_to_posix(project_dir)}:{workspace}"]
    if claude_dir.exists():
        cmd += ["-v", f"{_to_posix(claude_dir)}:/home/dev/.claude:ro"]
        # Claude Code writes session state here; anonymous volume keeps .claude read-only
        cmd += ["-v", "/home/dev/.claude/session-env"]
    if claude_json.exists():
        cmd += ["-v", f"{_to_posix(claude_json)}:/home/dev/.claude.json:ro"]
    if gitconfig.exists():
        cmd += ["-v", f"{_to_posix(gitconfig)}:/home/dev/.gitconfig:ro"]

    for var in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
        if var in os.environ:
            cmd += ["-e", f"{var}={os.environ[var]}"]

    cmd += ["-w", workspace, image]
    cmd += ["claude", "--dangerously-skip-permissions"] + extra_args
    return cmd


def _build_e2e_command(
    project_dir: pathlib.Path,
    e2e_cmd: str = "python -m pytest tutor/tests/e2e/ -v",
    image: str = IMAGE,
    workspace: str = WORKSPACE,
) -> list[str]:
    """Build docker run command that executes e2e_cmd inside the container."""
    try:
        inner = shlex.split(e2e_cmd)
    except ValueError as exc:
        print(f"error: invalid e2e_tests command in config: {exc}")
        sys.exit(1)
    return [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{_to_posix(project_dir)}:{workspace}",
        "-w",
        workspace,
        image,
    ] + inner


def build_command(
    project_dir: pathlib.Path,
    home_dir: pathlib.Path,
    extra_args: list[str],
    image: str = IMAGE,
    workspace: str = WORKSPACE,
    interactive: bool = True,
) -> list[str]:
    return build_docker_command(project_dir, home_dir, extra_args, image, workspace, interactive)
