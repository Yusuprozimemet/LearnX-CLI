#!/usr/bin/env python3
"""
learnx_dk.py — Claude Code launcher for LearnX.

Usage:
    python scripts/learnx_dk.py [--explore] [--review] [--dry-run] [--spec PATH]

Flags:
    (none)      Docker container session (default — zero prompts)
    --explore   Host session, read-only permissions (no Docker)
    --review    After container session: run E2E + 5-agent review
    --version V Run all specs in specs/V/ sequentially

Examples:
    python scripts/learnx_dk.py                              # Docker (default)
    python scripts/learnx_dk.py --explore
    python scripts/learnx_dk.py --spec specs/v5/day18.md --review
    python scripts/learnx_dk.py --version v5 --review
    python scripts/learnx_dk.py --dry-run
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

SETTINGS_LOCAL = pathlib.Path(".claude/settings.local.json")

# ── helpers ──────────────────────────────────────────────────────────────────


def _to_posix(p: pathlib.Path) -> str:
    return p.as_posix()


def build_docker_command(
    project_dir: pathlib.Path,
    home_dir: pathlib.Path,
    extra_args: list[str],
) -> list[str]:
    """Build the docker run command."""
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


def _build_e2e_command(project_dir: pathlib.Path) -> list[str]:
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


# kept for backwards-compatibility with tests and run_review.py
def build_command(
    project_dir: pathlib.Path,
    home_dir: pathlib.Path,
    extra_args: list[str],
) -> list[str]:
    return build_docker_command(project_dir, home_dir, extra_args)


# ── runners ──────────────────────────────────────────────────────────────────


def run_explore(extra_args: list[str], dry_run: bool) -> None:
    """Run Claude on the host with read-only permissions — no Docker required."""
    cmd = ["claude"] + extra_args
    if dry_run:
        print(f"[writes {SETTINGS_LOCAL}]")
        print(" ".join(cmd))
        print(f"[deletes {SETTINGS_LOCAL}]")
        return
    SETTINGS_LOCAL.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_LOCAL.write_text(json.dumps(EXPLORE_PERMISSIONS, indent=2))
    try:
        subprocess.run(cmd, check=False)
    finally:
        if SETTINGS_LOCAL.exists():
            SETTINGS_LOCAL.unlink()


def run_implement(
    project_dir: pathlib.Path,
    home_dir: pathlib.Path,
    spec: pathlib.Path | None,
    review: bool,
    extra_args: list[str],
    dry_run: bool,
) -> None:
    container_cmd = build_docker_command(project_dir, home_dir, extra_args)

    if dry_run:
        print("# Step 1 — container session")
        print(" ".join(container_cmd))
        if review:
            e2e_cmd = _build_e2e_command(project_dir)
            review_cmd = [_PY, "scripts/run_review.py"]
            if spec:
                review_cmd += ["--spec", spec.as_posix()]
            print("# Step 2 — E2E smoke tests (inside container)")
            print(" ".join(e2e_cmd))
            print("# Step 3 — review pipeline")
            print(" ".join(review_cmd))
        return

    print("\n[implement] starting container session...")
    subprocess.run(container_cmd, check=False)

    if review:
        print("\n[implement] running E2E smoke tests...")
        e2e_result = subprocess.run(_build_e2e_command(project_dir), check=False)

        review_cmd = [_PY, "scripts/run_review.py"]
        if spec:
            review_cmd += ["--spec", spec.as_posix()]
        print("\n[implement] running review pipeline...")
        subprocess.run(review_cmd, check=False)

        if e2e_result.returncode != 0:
            print("\n[implement] WARNING: E2E tests had failures — review findings carefully")


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


def _checkout_spec_branch(branch: str, dry_run: bool) -> bool:
    """Checkout main then create a fresh branch for this spec.

    Returns True if all git commands succeeded, False otherwise.
    """
    cmds = [
        ["git", "checkout", "main"],
        ["git", "checkout", "-b", branch],
    ]
    if dry_run:
        for cmd in cmds:
            print(" ".join(cmd))
        return True
    for cmd in cmds:
        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            print(f"[version] error: '{' '.join(cmd)}' exited {result.returncode}")
            return False
    return True


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
    review: bool,
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

        t0 = time.monotonic()
        if not _checkout_spec_branch(branch, dry_run):
            duration_s = time.monotonic() - t0
            results.append(SpecResult(spec.stem, "FAILED", duration_s, branch))
            continue
        run_implement(
            project_dir, home_dir, spec=spec, review=review, extra_args=extra_args, dry_run=dry_run
        )
        duration_s = time.monotonic() - t0
        results.append(SpecResult(spec.stem, "DONE", duration_s, branch))

    _print_version_report(results, version)


# ── CLI ──────────────────────────────────────────────────────────────────────


def _parse(
    argv: list[str],
) -> tuple[bool, bool, bool, pathlib.Path | None, str | None, list[str]]:
    # returns: explore, review, dry_run, spec, version, rest
    explore = False
    review = False
    dry_run = False
    spec = None
    version: str | None = None
    rest: list[str] = []

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--explore":
            explore = True
            i += 1
        elif arg == "--review":
            review = True
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

    if spec is not None and version is not None:
        print("error: --version and --spec are mutually exclusive")
        sys.exit(1)

    if explore and review:
        print("error: --explore and --review are mutually exclusive")
        sys.exit(1)

    if explore and version is not None:
        print("error: --explore and --version are mutually exclusive")
        sys.exit(1)

    return explore, review, dry_run, spec, version, rest


def main(argv: list[str] | None = None) -> None:
    if argv is None:
        argv = sys.argv[1:]
    # Ensure Unicode output works on Windows terminals (cp1252 -> utf-8)
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    explore, review, dry_run, spec, version, extra = _parse(argv)
    project_dir = pathlib.Path.cwd()
    home_dir = pathlib.Path.home()

    if explore:
        run_explore(extra, dry_run)
        return

    if version:
        run_yolo_version(project_dir, home_dir, version, review, extra, dry_run)
        return

    run_implement(project_dir, home_dir, spec, review, extra, dry_run)


if __name__ == "__main__":
    main()
