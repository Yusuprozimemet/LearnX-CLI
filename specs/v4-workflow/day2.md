# Day 2 — Container Wrapper + Settings Overhaul

## Goal

Create `scripts/learnx-dk.py`, a Python wrapper that launches Claude Code inside the
`learnx-dev` Docker container with `--dangerously-skip-permissions`. The container
provides isolation; the flag removes the per-step permission prompts that slow down
the implement→test→fix loop.

Also update `.claude/settings.json`: remove the four `deny` rules and replace them with
a comment block explaining why they are no longer needed. The allow rules stay.

After this day, starting a spec session means running `python scripts/learnx-dk.py`
instead of opening Claude Code directly.

---

## Done (merge gate)

```powershell
# Wrapper generates correct docker command (dry run, no container started)
python scripts/learnx-dk.py --dry-run

# Wrapper tests pass
py -m pytest scripts/tests/test_learnx_dk.py -v

# Full suite still green
py -m pytest
py -m ruff check tutor/
py -m ruff format --check tutor/
```

Report: paste dry-run output, test results, gate output.
Stop: do not merge to main — wait for human review.

---

## Data boundary

```
Creates (new):
  scripts/__init__.py              ← makes scripts/ a package for pytest
  scripts/learnx_dk.py             ← wrapper script
  scripts/tests/__init__.py        ← test package marker
  scripts/tests/test_learnx_dk.py  ← pytest tests for the wrapper

Modifies (existing):
  .claude/settings.json            ← remove deny block; add explanatory comment

Does NOT touch:
  tutor/            ← no application code changes
  Dockerfile        ← no changes to the image
  dev_setup/        ← documentation update is Day 4
```

---

## `scripts/learnx_dk.py` — algorithm

```python
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
    gitconfig  = home_dir / ".gitconfig"

    cmd = [
        "docker", "run", "--rm", "-it",
        "-v", f"{_to_posix(project_dir)}:{WORKSPACE}",
    ]

    if claude_dir.exists():
        cmd += ["-v", f"{_to_posix(claude_dir)}:/home/dev/.claude:ro"]

    if gitconfig.exists():
        cmd += ["-v", f"{_to_posix(gitconfig)}:/home/dev/.gitconfig:ro"]

    # Pass git identity from host environment if set
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
    extra   = [a for a in argv if a != "--dry-run"]

    project_dir = pathlib.Path.cwd()
    home_dir    = pathlib.Path.home()

    cmd = build_command(project_dir, home_dir, extra)

    if dry_run:
        print(" ".join(cmd))
        return

    subprocess.run(cmd, check=False)


if __name__ == "__main__":
    main()
```

---

## `.claude/settings.json` — updated content

```json
{
  "_comment": [
    "Deny rules removed in dev_setup_update Day 2.",
    "Previously: git push, git merge, git reset, git branch -D were denied.",
    "Now: agent runs inside the learnx-dev Docker container via scripts/learnx_dk.py.",
    "The container mounts only this repo at /workspace — it cannot reach GitHub,",
    "other directories, or your SSH keys. The container IS the sandbox.",
    "See dev_setup/container_plan.md for the rationale."
  ],
  "permissions": {
    "allow": [
      "Bash(py -m pytest*)",
      "Bash(py -m ruff check*)",
      "Bash(py -m ruff format*)",
      "Bash(git status*)",
      "Bash(git diff*)",
      "Bash(git log*)",
      "Bash(git checkout main)",
      "Bash(git checkout -b sandbox/*)",
      "Bash(git branch*)"
    ]
  }
}
```

Note: the `_comment` key is non-standard JSON but is ignored by the Claude Code settings
parser. It serves as documentation for anyone reading the file. If Claude Code rejects it,
move the comment to a separate `settings.json.md` note file.

---

## Acceptance criteria

- [ ] `scripts/learnx_dk.py` exists and is importable as a module
- [ ] `python scripts/learnx_dk.py --dry-run` prints a `docker run` command (no container started)
- [ ] Dry-run output contains `--dangerously-skip-permissions`
- [ ] Dry-run output contains `-v <project_path>:/workspace`
- [ ] Dry-run output contains `-v <home>/.claude:/home/dev/.claude:ro` (when `~/.claude` exists)
- [ ] Dry-run output contains `-v <home>/.gitconfig:/home/dev/.gitconfig:ro` (when `~/.gitconfig` exists)
- [ ] `.claude/settings.json` has no `deny` key
- [ ] `.claude/settings.json` has a `_comment` block explaining removal
- [ ] `allow` list in settings.json is unchanged from before
- [ ] All existing pytest tests still pass (no regressions)

---

## Tests — `scripts/tests/test_learnx_dk.py`

Write these exact test functions. Use `tmp_path` (pytest fixture) to simulate home and
project directories without touching real paths.

- `test_command_contains_skip_permissions` — `build_command(...)` output includes `--dangerously-skip-permissions`
- `test_command_mounts_project_as_workspace` — output contains `-v` mount ending in `:/workspace`
- `test_command_mounts_claude_dir_readonly` — when a fake `~/.claude` dir exists, output contains `:ro`
- `test_command_omits_gitconfig_when_absent` — when `~/.gitconfig` does not exist, no gitconfig `-v` flag
- `test_command_omits_claude_mount_when_absent` — when `~/.claude` does not exist, no claude `-v` flag
- `test_dry_run_prints_command_no_subprocess` — `main(["--dry-run"])` writes to stdout, does not call `subprocess.run`
- `test_extra_args_forwarded_to_claude` — `build_command(..., extra_args=["--model", "opus"])` includes those args after `claude`
