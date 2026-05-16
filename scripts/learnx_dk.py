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
import shlex
import subprocess
import sys
import threading
import time
import tomllib
from dataclasses import dataclass

_PY = sys.executable  # venv-aware Python for host post-container steps

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
    image: str = IMAGE,
    workspace: str = WORKSPACE,
    interactive: bool = True,
) -> list[str]:
    """
    Build the docker command that runs the Claude CLI inside a container with project and user mounts.
    
    Parameters:
        project_dir (pathlib.Path): Host project directory mounted into the container workspace.
        home_dir (pathlib.Path): Host home directory used to locate optional files to mount (`.claude`, `.claude.json`, `.gitconfig`).
        extra_args (list[str]): Arguments appended to the `claude --dangerously-skip-permissions` invocation inside the container.
        image (str): Docker image to run.
        workspace (str): Container path used as the working directory and target mount for `project_dir`.
        interactive (bool): If true, allocate a TTY and enable interactive mode (`-it`).
    
    Returns:
        list[str]: The full `docker run` command and arguments ready for subprocess execution.
    """
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


# kept for backwards-compatibility with tests and run_review.py
def build_command(
    project_dir: pathlib.Path,
    home_dir: pathlib.Path,
    extra_args: list[str],
    image: str = IMAGE,
    workspace: str = WORKSPACE,
    interactive: bool = True,
) -> list[str]:
    """
    Constructs the command-line invocation to run Claude inside the project's container.
    
    Parameters:
        project_dir (pathlib.Path): Path to the project directory to mount into the container.
        home_dir (pathlib.Path): User home directory used to locate host config files to mount.
        extra_args (list[str]): Additional CLI arguments to pass to Claude.
        image (str): Docker image name to run.
        workspace (str): Container working directory path that maps to the project mount.
        interactive (bool): If True, allocate a TTY and attach stdin; if False, run non-interactively.
    
    Returns:
        list[str]: The composed command and arguments suitable for subprocess execution.
    """
    return build_docker_command(project_dir, home_dir, extra_args, image, workspace, interactive)


def _extract_int_flag(args: list[str], flag: str) -> tuple[int | None, list[str]]:
    """
    Extracts and removes an integer value for a named flag from an argument list.
    
    Parameters:
        args (list[str]): The argument list to search.
        flag (str): The flag to look for (e.g. '--session-timeout').
    
    Returns:
        tuple[int | None, list[str]]: A pair where the first element is the parsed integer value for the flag, or `None` if the flag is absent or its value is missing/invalid; the second element is the argument list with the flag and its value removed when a valid integer was parsed, otherwise the original list.
    """
    if flag not in args:
        return None, args
    idx = args.index(flag)
    try:
        val = int(args[idx + 1])
        return val, args[:idx] + args[idx + 2 :]
    except (IndexError, ValueError):
        return None, args


def _run_with_timeout(
    cmd: list[str],
    session_timeout_s: float,
    idle_timeout_s: float,
) -> tuple[int, list[str], bool]:
    """
    Run a subprocess command while streaming its combined stdout/stderr and enforcing session and idle timeouts.
    
    Streams each output line to the current stdout, keeps a rolling buffer of the last 200 output lines, and kills the subprocess if total runtime exceeds session_timeout_s or if no output has appeared for idle_timeout_s (if idle_timeout_s > 0).
    
    Parameters:
        cmd (list[str]): Command and arguments to execute.
        session_timeout_s (float): Maximum total runtime in seconds before the process is killed.
        idle_timeout_s (float): Maximum allowed seconds without any output before the process is killed; use 0 to disable idle-timeout.
    
    Returns:
        tuple[int, list[str], bool]:
            returncode — process exit code (may reflect kill signal if terminated by the watchdog).
            last_lines — list of the last up to 200 combined stdout/stderr lines captured.
            timed_out — `True` if the process was killed due to a session or idle timeout, `False` otherwise.
    """
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )

    ring: list[str] = []
    last_output_at = [time.monotonic()]
    timed_out = [False]

    def _reader() -> None:
        """
        Continuously reads lines from the subprocess stdout, prints them, stores a rolling buffer of the last 200 lines, and updates the last-output timestamp.
        
        Reads each raw line from the global `proc.stdout`, decodes bytes to text (replacing invalid bytes), strips trailing newline characters, prints the resulting line to stdout (flushed), appends the line to the global `ring` list while keeping its length at most 200, and sets `last_output_at[0]` to the current monotonic time.
        """
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = raw.decode(errors="replace").rstrip()
            print(line, flush=True)
            ring.append(line)
            if len(ring) > 200:
                ring.pop(0)
            last_output_at[0] = time.monotonic()

    def _watchdog() -> None:
        """
        Monitor a running subprocess and kill it if idle or total session timeouts are exceeded.
        
        Runs until the monitored process `proc` exits. If `idle_timeout_s` > 0 and no new output has appeared for that many seconds, or if the total runtime exceeds `session_timeout_s`, prints a timeout message, sets `timed_out[0] = True`, and kills `proc`.
        """
        deadline = time.monotonic() + session_timeout_s
        while proc.poll() is None:
            now = time.monotonic()
            if idle_timeout_s > 0 and (now - last_output_at[0]) > idle_timeout_s:
                print(
                    f"\n[resilience] idle timeout "
                    f"({idle_timeout_s / 60:.0f} min) — killing session",
                    flush=True,
                )
                timed_out[0] = True
                proc.kill()
                return
            if now > deadline:
                print(
                    f"\n[resilience] session timeout "
                    f"({session_timeout_s / 60:.0f} min) — killing session",
                    flush=True,
                )
                timed_out[0] = True
                proc.kill()
                return
            time.sleep(2)

    t_read = threading.Thread(target=_reader, daemon=True)
    t_watch = threading.Thread(target=_watchdog, daemon=True)
    t_read.start()
    t_watch.start()
    proc.wait()
    t_read.join(timeout=5)

    return proc.returncode, ring, timed_out[0]


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
    image: str = IMAGE,
    workspace: str = WORKSPACE,
    config: dict | None = None,
) -> None:
    cfg = config or {}
    e2e_cmd = cfg.get("validation", {}).get("e2e_tests") or _DEFAULTS["validation"]["e2e_tests"]
    review_script = (
        cfg.get("review", {}).get("review_script") or _DEFAULTS["review"]["review_script"]
    )

    container_cmd = build_docker_command(
        project_dir, home_dir, extra_args, image=image, workspace=workspace
    )

    if dry_run:
        print("# Step 1 — container session")
        print(" ".join(container_cmd))
        if review:
            e2e_docker_cmd = _build_e2e_command(project_dir, e2e_cmd, image, workspace)
            rev_cmd = [_PY, review_script]
            if spec:
                rev_cmd += ["--spec", spec.as_posix()]
            print("# Step 2 — E2E smoke tests (inside container)")
            print(" ".join(e2e_docker_cmd))
            print("# Step 3 — review pipeline")
            print(" ".join(rev_cmd))
        return

    print("\n[implement] starting container session...")
    subprocess.run(container_cmd, check=False)

    if review:
        print("\n[implement] running E2E smoke tests...")
        e2e_result = subprocess.run(
            _build_e2e_command(project_dir, e2e_cmd, image, workspace), check=False
        )

        rev_cmd = [_PY, review_script]
        if spec:
            rev_cmd += ["--spec", spec.as_posix()]
        print("\n[implement] running review pipeline...")
        subprocess.run(rev_cmd, check=False)

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
    """
    Print a concise execution summary for a version's spec run results.
    
    Parameters:
        results (list[SpecResult]): Per-spec outcomes; each entry's `spec_name`, `status`, and `duration_s` are used.
        version (str): Version identifier to display in the report header.
    
    Description:
        Emits a formatted table to stdout listing each spec, an icon for its status (✓ for DONE, ⏱ for TIMED_OUT, ✗ for FAILED),
        the textual status, and the duration rounded down to whole minutes. Prints aggregate counts for attempted, done,
        failed, and timed-out specs and the total elapsed minutes across all specs.
    """
    width = 60
    print(f"\n{'-' * width}")
    print(f"  {version} Execution Summary")
    print(f"{'-' * width}")
    for r in results:
        if r.status == "DONE":
            icon = "✓"
        elif r.status == "TIMED_OUT":
            icon = "⏱"
        else:
            icon = "✗"
        mins = int(r.duration_s / 60)
        print(f"  {r.spec_name:<12}  {icon} {r.status:<10}  {mins} min")
    print(f"{'-' * width}")
    total_mins = int(sum(r.duration_s for r in results) / 60)
    done = sum(1 for r in results if r.status == "DONE")
    timed_out = sum(1 for r in results if r.status == "TIMED_OUT")
    failed = len(results) - done - timed_out
    print(
        f"  {len(results)}/{len(results)} specs attempted · "
        f"{done} done · {failed} failed · {timed_out} timed out · "
        f"Total: {total_mins} min"
    )


def run_yolo_version(
    project_dir: pathlib.Path,
    home_dir: pathlib.Path,
    version: str,
    review: bool,
    extra_args: list[str],
    dry_run: bool,
    specs_dir: str = "specs",
    session_timeout_s: float = 1800.0,
    idle_timeout_s: float = 300.0,
    config: dict | None = None,
) -> None:
    """
    Run all spec markdown files for a given version sequentially in a containerized workflow and print a summary report.
    
    For each discovered spec file under project_dir/specs_dir/version this function:
    - creates a per-spec git branch,
    - runs the implementation inside a Docker container (non-interactive),
    - optionally runs E2E tests and the review script on the host when review is enabled and the spec did not time out,
    - records per-spec results (status, duration, branch) and prints an aggregated version report.
    
    Parameters:
        project_dir (pathlib.Path): Root of the project containing the specs directory.
        home_dir (pathlib.Path): User home directory used for resolving host mounts and credentials.
        version (str): Version identifier subdirectory under the specs directory to execute.
        review (bool): If True, run E2E tests and the host review script after a successful spec run.
        extra_args (list[str]): Additional arguments forwarded into the container command.
        dry_run (bool): If True, print planned commands and actions but do not execute container, E2E, or review steps.
        specs_dir (str): Name of the specs directory under project_dir (default: "specs").
        session_timeout_s (float): Total allowed runtime in seconds for each spec container; exceeding this marks the spec as `TIMED_OUT`.
        idle_timeout_s (float): Allowed seconds of no output from the container before it is considered idle and is killed, which also marks the spec as `TIMED_OUT`.
        config (dict | None): Optional configuration overrides (project image/workspace, validation and review settings). If omitted, defaults are used.
    
    Side effects:
        - Prints progress and summaries to stdout.
        - Runs git checkout to prepare per-spec branches.
        - Launches Docker containers and may invoke E2E and review commands on the host.
        - When dry_run is True, no external commands are executed and no branches are created.
    """
    specs = _discover_specs(project_dir / specs_dir, version)
    if not specs:
        print(f"[version] no spec files found in {specs_dir}/{version}/")
        return

    print(f"\n[version] {version} - {len(specs)} spec(s) found")
    results: list[SpecResult] = []

    cfg = config or {}
    image = cfg.get("project", {}).get("docker_image") or _DEFAULTS["project"]["docker_image"]
    workspace = cfg.get("project", {}).get("workspace") or _DEFAULTS["project"]["workspace"]

    for spec in specs:
        branch = _spec_branch_name(version, spec.stem)
        print(f"\n[version] -- spec: {spec.name}  branch: {branch} --")

        t0 = time.monotonic()
        if not _checkout_spec_branch(branch, dry_run):
            duration_s = time.monotonic() - t0
            results.append(SpecResult(spec.stem, "FAILED", duration_s, branch))
            continue

        container_cmd = build_docker_command(
            project_dir,
            home_dir,
            extra_args,
            image=image,
            workspace=workspace,
            interactive=False,
        )

        if dry_run:
            print("# container:", " ".join(container_cmd))
            status = "DONE"
        else:
            rc, _last_lines, did_timeout = _run_with_timeout(
                container_cmd, session_timeout_s, idle_timeout_s
            )
            if did_timeout:
                status = "TIMED_OUT"
            elif rc == 0:
                status = "DONE"
            else:
                status = "FAILED"

            if review and status != "TIMED_OUT":
                e2e_cmd = (
                    cfg.get("validation", {}).get("e2e_tests")
                    or _DEFAULTS["validation"]["e2e_tests"]
                )
                subprocess.run(
                    _build_e2e_command(project_dir, e2e_cmd, image, workspace),
                    check=False,
                )
                review_script = (
                    cfg.get("review", {}).get("review_script")
                    or _DEFAULTS["review"]["review_script"]
                )
                rev_cmd = [_PY, review_script, "--spec", spec.as_posix()]
                subprocess.run(rev_cmd, check=False)

        duration_s = time.monotonic() - t0
        results.append(SpecResult(spec.stem, status, duration_s, branch))

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
    """
    Entry point for the CLI: parse arguments, load project configuration, compute resilience timeouts, and dispatch to the appropriate runner (explore, version, or implement).
    
    Parameters:
        argv (list[str] | None): Command-line arguments to parse (defaults to sys.argv[1:] when None).
    """
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
    config = _load_config(project_dir)

    proj = config["project"]
    image = proj["docker_image"]
    workspace = proj["workspace"]
    specs_dir = proj["specs_dir"]

    res = config.get("resilience", _DEFAULTS["resilience"])
    session_timeout_min, extra = _extract_int_flag(extra, "--session-timeout")
    idle_timeout_min, extra = _extract_int_flag(extra, "--idle-timeout")
    session_timeout_s = (session_timeout_min or res["session_timeout_minutes"]) * 60.0
    idle_timeout_s = (idle_timeout_min or res["idle_timeout_minutes"]) * 60.0

    if explore:
        run_explore(extra, dry_run)
        return

    if version:
        run_yolo_version(
            project_dir,
            home_dir,
            version,
            review,
            extra,
            dry_run,
            specs_dir=specs_dir,
            session_timeout_s=session_timeout_s,
            idle_timeout_s=idle_timeout_s,
            config=config,
        )
        return

    run_implement(
        project_dir,
        home_dir,
        spec,
        review,
        extra,
        dry_run,
        image=image,
        workspace=workspace,
        config=config,
    )


if __name__ == "__main__":
    main()
