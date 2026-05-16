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

import atexit
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
import urllib.parse
import urllib.request
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
    "notify": {
        "webhook_url": None,
        "telegram_token_env": None,
        "telegram_chat_id_env": None,
        "script": None,
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


# kept for backwards-compatibility with tests and run_review.py
def build_command(
    project_dir: pathlib.Path,
    home_dir: pathlib.Path,
    extra_args: list[str],
    image: str = IMAGE,
    workspace: str = WORKSPACE,
    interactive: bool = True,
) -> list[str]:
    return build_docker_command(project_dir, home_dir, extra_args, image, workspace, interactive)


def _extract_int_flag(args: list[str], flag: str) -> tuple[int | None, list[str]]:
    """Pop --flag N from args. Return (int_value_or_None, remaining_args)."""
    if flag not in args:
        return None, args
    idx = args.index(flag)
    try:
        val = int(args[idx + 1])
        return val, args[:idx] + args[idx + 2 :]
    except (IndexError, ValueError):
        return None, args


def _is_rate_limited(last_lines: list[str], patterns: list[str]) -> bool:
    """Return True if any pattern appears (case-insensitive) in the last output lines."""
    text = "\n".join(last_lines).lower()
    return any(p.lower() in text for p in patterns)


def _run_with_timeout(
    cmd: list[str],
    session_timeout_s: float,
    idle_timeout_s: float,
) -> tuple[int, list[str], bool]:
    """Run cmd non-interactively with output streaming and two kill triggers.

    Returns:
        returncode   — process exit code (-9 or similar if killed)
        last_lines   — last 200 stdout+stderr lines (for rate-limit detection)
        timed_out    — True if killed by session or idle timeout
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
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = raw.decode(errors="replace").rstrip()
            print(line, flush=True)
            ring.append(line)
            if len(ring) > 200:
                ring.pop(0)
            last_output_at[0] = time.monotonic()

    def _watchdog() -> None:
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


def _build_notify_payload(
    version: str,
    results: list["SpecResult"],
    status: str,
    start_time: float,
    config: dict,
) -> dict:
    done = sum(1 for r in results if r.status == "DONE")
    failed = sum(1 for r in results if r.status == "FAILED")
    timed_out = sum(1 for r in results if r.status == "TIMED_OUT")
    duration_minutes = int((time.monotonic() - start_time) / 60)
    return {
        "project": config.get("project", {}).get("name", "LearnX"),
        "version": version,
        "status": status,
        "specs_total": len(results),
        "specs_ready": done,
        "specs_failed": failed,
        "specs_timed_out": timed_out,
        "duration_minutes": duration_minutes,
        "branch_summary": [
            {"spec": r.spec_name, "status": r.status, "branch": r.branch} for r in results
        ],
    }


class Notifier:
    """Best-effort multi-channel notifier. Never raises; logs failures to stdout."""

    def __init__(self, config: dict) -> None:
        notify = config.get("notify", {})
        self._webhook_url: str | None = notify.get("webhook_url")
        self._tg_token_env: str | None = notify.get("telegram_token_env")
        self._tg_chat_env: str | None = notify.get("telegram_chat_id_env")
        self._script: str | None = notify.get("script")

    def enabled(self) -> bool:
        """True if at least one channel is fully configured."""
        telegram_ready = bool(self._tg_token_env and self._tg_chat_env)
        return bool(self._webhook_url or telegram_ready or self._script)

    def send(self, payload: dict) -> None:
        """Fire all configured channels. Exceptions are caught and logged."""
        if self._webhook_url:
            self._send_webhook(payload)
        if self._tg_token_env and self._tg_chat_env:
            self._send_telegram(payload)
        if self._script:
            self._send_script(payload)

    # ── channels ──────────────────────────────────────────────────────────────

    def _send_webhook(self, payload: dict) -> None:
        try:
            data = json.dumps(payload).encode()
            req = urllib.request.Request(
                self._webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=10)
            print("[notify] webhook sent", flush=True)
        except Exception as exc:
            print(f"[notify] webhook failed: {exc}", flush=True)

    def _send_telegram(self, payload: dict) -> None:
        try:
            token = os.environ.get(self._tg_token_env or "", "")
            chat_id = os.environ.get(self._tg_chat_env or "", "")
            if not token or not chat_id:
                print(
                    f"[notify] telegram: env vars "
                    f"{self._tg_token_env!r} / {self._tg_chat_env!r} not set",
                    flush=True,
                )
                return
            text = self._format_telegram(payload)
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
            urllib.request.urlopen(url, data=data, timeout=10)
            print("[notify] telegram sent", flush=True)
        except Exception as exc:
            print(f"[notify] telegram failed: {exc}", flush=True)

    def _send_script(self, payload: dict) -> None:
        try:
            data = json.dumps(payload).encode()
            subprocess.run(
                [self._script],
                input=data,
                timeout=30,
                check=False,
            )
            print(f"[notify] script {self._script!r} called", flush=True)
        except Exception as exc:
            print(f"[notify] script failed: {exc}", flush=True)

    # ── formatting ────────────────────────────────────────────────────────────

    def _format_telegram(self, payload: dict) -> str:
        project = payload.get("project", "LearnX")
        version = payload.get("version", "?")
        total = payload.get("specs_total", 0)
        done = payload.get("specs_ready", 0)
        failed = payload.get("specs_failed", 0)
        timed_out = payload.get("specs_timed_out", 0)
        mins = payload.get("duration_minutes", 0)
        h, m = divmod(mins, 60)
        duration = f"{h}h{m:02d}m" if h else f"{m}m"

        if failed == 0 and timed_out == 0:
            icon, headline = "✓", f"{project} {version} complete"
        else:
            icon, headline = "✗", f"{project} {version} — NEEDS ATTENTION"

        parts = [f"{done}/{total} specs done"]
        if failed:
            parts.append(f"{failed} failed")
        if timed_out:
            parts.append(f"{timed_out} timed out")
        parts.append(duration)
        return f"{icon} {headline}\n{' · '.join(parts)}"


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
        retry_note = (
            f"  ({r.retries} rate-limit retr{'y' if r.retries == 1 else 'ies'})"
            if r.retries > 0
            else ""
        )
        print(f"  {r.spec_name:<12}  {icon} {r.status:<10}  {mins} min{retry_note}")
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
    rate_limit_wait_s: float = 120.0,
    max_retries: int = 1,
    config: dict | None = None,
) -> None:
    specs = _discover_specs(project_dir / specs_dir, version)
    if not specs:
        print(f"[version] no spec files found in {specs_dir}/{version}/")
        return

    print(f"\n[version] {version} - {len(specs)} spec(s) found")
    start_time = time.monotonic()
    results: list[SpecResult] = []

    cfg = config or {}
    image = cfg.get("project", {}).get("docker_image") or _DEFAULTS["project"]["docker_image"]
    workspace = cfg.get("project", {}).get("workspace") or _DEFAULTS["project"]["workspace"]
    rate_limit_patterns = (
        cfg.get("resilience", {}).get("rate_limit_patterns")
        or _DEFAULTS["resilience"]["rate_limit_patterns"]
    )

    notifier = Notifier(cfg)
    _notified = [False]

    def _atexit_handler() -> None:
        if _notified[0] or not notifier.enabled():
            return
        payload = _build_notify_payload(version, results, "aborted", start_time, cfg)
        notifier.send(payload)

    atexit.register(_atexit_handler)

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

        attempt = 0
        status = "FAILED"

        while True:
            if dry_run:
                print(f"# [dry-run] container: {' '.join(container_cmd)}")
                status = "DONE"
                break

            rc, last_lines, did_timeout = _run_with_timeout(
                container_cmd, session_timeout_s, idle_timeout_s
            )

            if did_timeout:
                status = "TIMED_OUT"
                break

            if rc == 0:
                status = "DONE"
                break

            if (
                rate_limit_wait_s > 0
                and attempt < max_retries
                and _is_rate_limited(last_lines, rate_limit_patterns)
            ):
                attempt += 1
                print(
                    f"\n[resilience] rate limit detected — "
                    f"waiting {rate_limit_wait_s / 60:.0f} min "
                    f"(retry {attempt}/{max_retries})",
                    flush=True,
                )
                time.sleep(rate_limit_wait_s)
                continue

            status = "FAILED"
            break

        if review and status not in ("TIMED_OUT", "FAILED"):
            e2e_cmd = (
                cfg.get("validation", {}).get("e2e_tests") or _DEFAULTS["validation"]["e2e_tests"]
            )
            subprocess.run(
                _build_e2e_command(project_dir, e2e_cmd, image, workspace),
                check=False,
            )
            review_script = (
                cfg.get("review", {}).get("review_script") or _DEFAULTS["review"]["review_script"]
            )
            rev_cmd = [_PY, review_script, "--spec", spec.as_posix()]
            subprocess.run(rev_cmd, check=False)

        duration_s = time.monotonic() - t0
        results.append(SpecResult(spec.stem, status, duration_s, branch, retries=attempt))

    _print_version_report(results, version)

    if notifier.enabled():
        payload = _build_notify_payload(version, results, "completed", start_time, cfg)
        notifier.send(payload)
        _notified[0] = True


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
    config = _load_config(project_dir)

    proj = config["project"]
    image = proj["docker_image"]
    workspace = proj["workspace"]
    specs_dir = proj["specs_dir"]

    res = config.get("resilience", _DEFAULTS["resilience"])
    session_timeout_min, extra = _extract_int_flag(extra, "--session-timeout")
    idle_timeout_min, extra = _extract_int_flag(extra, "--idle-timeout")
    wait_min, extra = _extract_int_flag(extra, "--wait")
    session_timeout_s = (
        res["session_timeout_minutes"] if session_timeout_min is None else session_timeout_min
    ) * 60.0
    idle_timeout_s = (
        res["idle_timeout_minutes"] if idle_timeout_min is None else idle_timeout_min
    ) * 60.0
    rate_limit_wait_s = (res["rate_limit_wait_minutes"] if wait_min is None else wait_min) * 60.0

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
            rate_limit_wait_s=rate_limit_wait_s,
            max_retries=res["max_retries_per_spec"],
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

    notifier = Notifier(config)
    if notifier.enabled() and not dry_run:
        notifier.send(
            {
                "project": proj["name"],
                "spec": spec.stem if spec else "interactive",
                "status": "completed",
            }
        )


if __name__ == "__main__":
    main()
