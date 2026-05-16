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
import re
import subprocess
import sys
import time
from dataclasses import dataclass

_PY = sys.executable  # venv-aware Python for host post-container steps


@dataclass
class SpecResult:
    spec_name: str
    status: str  # "DONE" | "FAILED"
    duration_s: float
    branch: str


# ── constants ────────────────────────────────────────────────────────────────

IMAGE = "learnx-dev"
WORKSPACE = "/workspace"

MODES = ("supervised", "assisted", "container", "yolo")

BANNER = {
    "supervised": "SUPERVISED  — host machine, deny rules active, prompts on risky ops",
    "assisted": "ASSISTED    — host machine, no deny rules, prompts only for push/merge",
    "container": "CONTAINER   — Docker, --dangerously-skip-permissions, zero prompts",
    "yolo": "YOLO        — Docker + auto E2E + auto review after session ends",
}

ASSISTED_PERMISSIONS = {
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
            "Write(*)",
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
    claude_json = home_dir / ".claude.json"
    gitconfig = home_dir / ".gitconfig"

    cmd = [
        "docker",
        "run",
        "--rm",
        "-it",
        "-v",
        f"{_to_posix(project_dir)}:{WORKSPACE}",
    ]
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


def _build_e2e_command(project_dir: pathlib.Path) -> list[str]:
    """Run E2E tests inside the container — ffmpeg, Playwright, and chromium are there."""
    return [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{_to_posix(project_dir)}:{WORKSPACE}",
        "-w",
        WORKSPACE,
        IMAGE,
        "python",
        "-m",
        "pytest",
        "tutor/tests/e2e/",
        "-v",
    ]


def run_yolo(
    project_dir: pathlib.Path,
    home_dir: pathlib.Path,
    spec_path: pathlib.Path | None,
    extra_args: list[str],
    dry_run: bool,
) -> None:
    container_cmd = build_docker_command(project_dir, home_dir, extra_args)
    e2e_cmd = _build_e2e_command(project_dir)
    review_cmd = [_PY, "scripts/run_review.py"]
    if spec_path:
        review_cmd += ["--spec", spec_path.as_posix()]

    if dry_run:
        print("# Step 1 — container session")
        print(" ".join(container_cmd))
        print("# Step 2 — E2E smoke tests (inside container — ffmpeg + Playwright available)")
        print(" ".join(e2e_cmd))
        print("# Step 3 — review pipeline")
        print(" ".join(review_cmd))
        return

    print("\n[yolo] starting container session...")
    subprocess.run(container_cmd, check=False)

    print("\n[yolo] container exited — running E2E smoke tests in container...")
    e2e_result = subprocess.run(e2e_cmd, check=False)

    print("\n[yolo] running review pipeline...")
    subprocess.run(review_cmd, check=False)

    if e2e_result.returncode != 0:
        print("\n[yolo] WARNING: E2E tests had failures — review findings carefully")


# ── version-level execution ──────────────────────────────────────────────────


def _discover_specs(specs_dir: pathlib.Path, version: str) -> list[pathlib.Path]:
    """Return spec .md files in specs/{version}/ sorted by embedded day number."""
    version_dir = specs_dir / version
    if not version_dir.is_dir():
        print(f"error: specs directory not found: {version_dir}")
        sys.exit(1)
    files = list(version_dir.glob("*.md"))

    def _key(p: pathlib.Path) -> tuple[int, str]:
        m = re.search(r"(\d+)", p.stem)
        return (int(m.group(1)) if m else 0, p.stem)

    return sorted(files, key=_key)


def _spec_branch_name(version: str, spec_stem: str) -> str:
    """Return the sandbox branch name for one spec in a version run."""
    return f"sandbox/{version}-{spec_stem}"


def _checkout_spec_branch(branch: str, dry_run: bool) -> None:
    """Checkout main then create a fresh branch for this spec."""
    cmds = [
        ["git", "checkout", "main"],
        ["git", "checkout", "-b", branch],
    ]
    if dry_run:
        for cmd in cmds:
            print(" ".join(cmd))
        return
    for cmd in cmds:
        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            print(f"[version] warning: '{' '.join(cmd)}' exited {result.returncode}")


def _print_version_report(results: list[SpecResult], version: str) -> None:
    width = 60
    print(f"\n{'-' * width}")
    print(f"  {version} Execution Summary")
    print(f"{'-' * width}")
    for r in results:
        icon = "✓" if r.status == "DONE" else "✗"
        mins = int(r.duration_s / 60)
        print(f"  {r.spec_name:<12}  {icon} {r.status:<8}  {mins} min")
    print(f"{'-' * width}")
    total_mins = int(sum(r.duration_s for r in results) / 60)
    done = sum(1 for r in results if r.status == "DONE")
    failed = len(results) - done
    print(
        f"  {len(results)}/{len(results)} specs attempted · "
        f"{done} done · {failed} failed · Total: {total_mins} min"
    )


def run_yolo_version(
    project_dir: pathlib.Path,
    home_dir: pathlib.Path,
    version: str,
    extra_args: list[str],
    dry_run: bool,
) -> None:
    specs_dir = project_dir / "specs"
    specs = _discover_specs(specs_dir, version)
    if not specs:
        print(f"[version] no spec files found in specs/{version}/")
        return

    print(f"\n[version] {version} - {len(specs)} spec(s) found")
    results: list[SpecResult] = []

    for spec in specs:
        branch = _spec_branch_name(version, spec.stem)
        print(f"\n[version] -- spec: {spec.name}  branch: {branch} --")
        _checkout_spec_branch(branch, dry_run)

        t0 = time.monotonic()
        run_yolo(project_dir, home_dir, spec_path=spec, extra_args=extra_args, dry_run=dry_run)
        duration_s = time.monotonic() - t0

        results.append(SpecResult(spec.stem, "DONE", duration_s, branch))

    _print_version_report(results, version)


# ── CLI ──────────────────────────────────────────────────────────────────────


def _parse(argv: list[str]) -> tuple[str, bool, pathlib.Path | None, str | None, list[str]]:
    mode = "supervised"
    dry_run = False
    spec = None
    version: str | None = None
    rest: list[str] = []

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--mode" and i + 1 < len(argv):
            mode = argv[i + 1]
            i += 2
        elif arg.startswith("--mode="):
            mode = arg.split("=", 1)[1]
            i += 1
        elif arg == "--dry-run":
            dry_run = True
            i += 1
        elif arg == "--spec" and i + 1 < len(argv):
            spec = pathlib.Path(argv[i + 1])
            i += 2
        elif arg.startswith("--spec="):
            spec = pathlib.Path(arg.split("=", 1)[1])
            i += 1
        elif arg == "--version" and i + 1 < len(argv):
            version = argv[i + 1]
            i += 2
        elif arg.startswith("--version="):
            version = arg.split("=", 1)[1]
            i += 1
        else:
            rest.append(arg)
            i += 1

    if mode not in MODES:
        print(f"error: unknown mode '{mode}'. choose from: {', '.join(MODES)}")
        sys.exit(1)

    if spec is not None and version is not None:
        print("error: --version and --spec are mutually exclusive")
        sys.exit(1)

    if version is not None:
        mode = "yolo"

    return mode, dry_run, spec, version, rest


def main(argv: list[str] | None = None) -> None:
    if argv is None:
        argv = sys.argv[1:]

    mode, dry_run, spec, version, extra = _parse(argv)
    project_dir = pathlib.Path.cwd()
    home_dir = pathlib.Path.home()

    if version:
        run_yolo_version(project_dir, home_dir, version, extra, dry_run)
        return

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
