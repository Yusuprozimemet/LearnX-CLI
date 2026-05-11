# Day 2b — Multi-Mode Launcher

## Goal

Day 2 created `scripts/learnx_dk.py` as a Docker-only wrapper. This day extends it into
a four-mode launcher so you can choose how much autonomy to give the agent depending on
the situation. The entry point becomes:

```powershell
python scripts/learnx_dk.py [--mode supervised|assisted|container|yolo] [--dry-run] [--spec PATH]
```

The four modes:

| Mode | Where | Permissions | Prompts | Use when |
|------|-------|-------------|---------|----------|
| `supervised` | Host | Current deny rules active | Frequent | New spec, unfamiliar territory |
| `assisted` | Host | No deny rules, expanded allow | Rare | Trusted scope, iterating fast |
| `container` | Docker | `--dangerously-skip-permissions` | Zero | Standard autonomous spec day |
| `yolo` | Docker | `--dangerously-skip-permissions` | Zero | Walk away; returns full report |

Default mode is `supervised` so running with no flags keeps existing behaviour.

Day 2 already removed deny rules from `settings.json`. This day restores them — because
`supervised` is now the committed safe default for running on the host. Container modes
bypass `settings.json` entirely via `--dangerously-skip-permissions`.

---

## Done (merge gate)

```powershell
# Wrapper tests — all four modes
py -m pytest scripts/tests/test_learnx_dk.py -v

# Confirm settings.json has deny rules restored
python -c "import json; s=json.load(open('.claude/settings.json')); assert 'deny' in s['permissions'], 'deny missing'"

# Confirm settings.local.json is gitignored
git check-ignore -v .claude/settings.local.json

# Full suite
py -m pytest
py -m ruff check tutor/
py -m ruff format --check tutor/
```

Report: paste all outputs. List each acceptance criterion.
Stop: do not merge to main — wait for human review.

---

## Data boundary

```
Modifies (existing):
  scripts/learnx_dk.py                    ← extend with --mode, banner, yolo pipeline
  .claude/settings.json                   ← restore deny rules; add mode comment
  scripts/tests/test_learnx_dk.py         ← extend with mode tests

Creates (new):
  .claude/settings.assisted.json          ← committed reference for assisted permissions

Adds to .gitignore:
  .claude/settings.local.json             ← runtime override; must not be committed

Does NOT touch:
  tutor/              ← no application code
  Dockerfile          ← no changes
  dev_setup/          ← documentation is Day 4
  scripts/run_review.py  ← already created in Day 3 (yolo imports it)
```

---

## Permission definitions

### Supervised — `.claude/settings.json` (restored, committed)

```json
{
  "_comment": [
    "Supervised mode — the committed host default.",
    "Use python scripts/learnx_dk.py --mode to select a different mode.",
    "Container modes (container, yolo) ignore this file entirely."
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
    ],
    "deny": [
      "Bash(git push*)",
      "Bash(git merge*)",
      "Bash(git reset*)",
      "Bash(git branch -D*)"
    ]
  }
}
```

### Assisted — `.claude/settings.assisted.json` (committed reference)

```json
{
  "_comment": [
    "Assisted mode reference. NOT loaded directly by Claude Code.",
    "The wrapper writes this content to .claude/settings.local.json at session start",
    "and deletes it on exit. settings.local.json is gitignored.",
    "Deny rules removed — local git ops happen without prompts.",
    "git push and git merge to main still require approval (no allow rule for them)."
  ],
  "permissions": {
    "allow": [
      "Bash(py -m pytest*)",
      "Bash(py -m ruff*)",
      "Bash(python*)",
      "Bash(git status*)",
      "Bash(git diff*)",
      "Bash(git log*)",
      "Bash(git add*)",
      "Bash(git commit*)",
      "Bash(git checkout*)",
      "Bash(git branch*)",
      "Bash(git stash*)",
      "Read(*)",
      "Edit(*)",
      "Write(*)"
    ]
  }
}
```

Note: `git push` and `git merge` are intentionally absent from the allow list. They
will still prompt — that is by design for the assisted mode. The agent can work freely
locally but cannot publish to remote or merge to main without you seeing it.

---

## Extended `scripts/learnx_dk.py` — full replacement

```python
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

# ── constants ────────────────────────────────────────────────────────────────

IMAGE     = "learnx-dev"
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
    print("─" * width)
    print(f"  learnx_dk  ·  {BANNER[mode]}")
    print("─" * width)


def build_docker_command(
    project_dir: pathlib.Path,
    home_dir: pathlib.Path,
    extra_args: list[str],
) -> list[str]:
    """Build the docker run command (unchanged from Day 2)."""
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
    e2e_cmd    = ["python", "-m", "pytest", "tutor/tests/e2e/", "-v"]
    review_cmd = ["python", "scripts/run_review.py"]
    if spec_path:
        review_cmd += ["--spec", str(spec_path)]

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
    mode    = "supervised"
    dry_run = False
    spec    = None
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
    home_dir    = pathlib.Path.home()

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
```

---

## `.gitignore` addition

Append to `.gitignore` (in the `# Dev workflow scripts output` block added in Day 0):

```gitignore
# Assisted mode runtime settings override — written and deleted by learnx_dk.py
.claude/settings.local.json
```

---

## Acceptance criteria

- [ ] `python scripts/learnx_dk.py --dry-run` uses supervised mode (default) and prints `claude` (not docker)
- [ ] `python scripts/learnx_dk.py --mode supervised --dry-run` prints `claude` without docker
- [ ] `python scripts/learnx_dk.py --mode assisted --dry-run` prints `[writes settings.local.json]` then `claude`
- [ ] `python scripts/learnx_dk.py --mode container --dry-run` prints a `docker run` command with `--dangerously-skip-permissions`
- [ ] `python scripts/learnx_dk.py --mode yolo --dry-run` prints three labelled steps: container, e2e, review
- [ ] `python scripts/learnx_dk.py --mode yolo --spec specs/v3/day13.md --dry-run` includes `--spec specs/v3/day13.md` in the review step
- [ ] Assisted mode writes `.claude/settings.local.json` before launching and deletes it after (even if Claude exits non-zero)
- [ ] `settings.local.json` contains no `deny` key in assisted mode
- [ ] `settings.local.json` is absent from the working tree after an assisted session ends
- [ ] `.claude/settings.json` has `deny` rules restored
- [ ] `.claude/settings.assisted.json` exists as committed reference
- [ ] `.gitignore` includes `.claude/settings.local.json`
- [ ] Unknown `--mode` value exits 1 with a useful error message
- [ ] Banner is printed before launch in non-dry-run mode
- [ ] All existing Day 2 tests still pass

---

## Tests — extend `scripts/tests/test_learnx_dk.py`

Add these functions to the existing test file:

- `test_default_mode_is_supervised` — `main(["--dry-run"])` output contains `claude` but not `docker`
- `test_supervised_dry_run_no_docker` — `_parse(["--mode", "supervised"])` returns mode `"supervised"`; `run_supervised([], dry_run=True)` output is `claude`
- `test_assisted_dry_run_shows_settings_write` — `run_assisted([], dry_run=True)` stdout contains `settings.local.json`
- `test_assisted_writes_and_deletes_settings_local` — mock `subprocess.run`; call `run_assisted([], dry_run=False)`; assert `settings.local.json` does not exist after call (use `tmp_path` and monkeypatch `SETTINGS_LOCAL`)
- `test_assisted_cleans_up_on_exception` — mock `subprocess.run` to raise; call `run_assisted`; assert `settings.local.json` still deleted
- `test_assisted_permissions_have_no_deny` — `ASSISTED_PERMISSIONS` dict has no `"deny"` key
- `test_assisted_permissions_allow_git_commit` — `ASSISTED_PERMISSIONS["permissions"]["allow"]` contains a rule matching `"Bash(git commit*)"`
- `test_container_dry_run_has_skip_permissions` — `run_container(..., dry_run=True)` output contains `--dangerously-skip-permissions`
- `test_yolo_dry_run_shows_three_steps` — `run_yolo(..., dry_run=True)` output contains `Step 1`, `Step 2`, `Step 3`
- `test_yolo_dry_run_with_spec` — when `spec_path` given, `--spec` appears in the review step output
- `test_unknown_mode_exits_1` — `main(["--mode", "invalid"])` raises `SystemExit(1)`
- `test_parse_mode_long_form` — `_parse(["--mode=container"])` returns `"container"`
