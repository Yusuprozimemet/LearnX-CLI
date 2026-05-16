import atexit
import json
import pathlib
import re
import subprocess
import sys
import time

from scripts.dk.config import _DEFAULTS, SpecResult
from scripts.dk.dashboard import DashboardServer, OutputBuffer
from scripts.dk.docker import (
    EXPLORE_PERMISSIONS,
    IMAGE,
    SETTINGS_LOCAL,
    WORKSPACE,
    _build_e2e_command,
    build_docker_command,
)
from scripts.dk.notifier import Notifier, _build_notify_payload
from scripts.dk.process import _is_rate_limited, _run_with_timeout

_PY = sys.executable


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
    serve: bool = False,
    port: int = 8080,
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
        if _notified[0] or dry_run or not notifier.enabled():
            return
        payload = _build_notify_payload(version, results, "aborted", start_time, cfg)
        notifier.send(payload)

    atexit.register(_atexit_handler)

    buf = OutputBuffer()
    dashboard = DashboardServer(buf, port=port) if serve else None
    if dashboard:
        dashboard.start()

    try:
        for spec in specs:
            if dashboard:
                dashboard.update(results, current_spec=spec.stem)

            branch = _spec_branch_name(version, spec.stem)
            print(f"\n[version] -- spec: {spec.name}  branch: {branch} --")

            t0 = time.monotonic()
            if not _checkout_spec_branch(branch, dry_run):
                duration_s = time.monotonic() - t0
                results.append(SpecResult(spec.stem, "FAILED", duration_s, branch))
                if dashboard:
                    dashboard.update(results, current_spec="")
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
                    container_cmd,
                    session_timeout_s,
                    idle_timeout_s,
                    output_buffer=buf,
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
            results.append(SpecResult(spec.stem, status, duration_s, branch, retries=attempt))

            if dashboard:
                dashboard.update(results, current_spec="")

        _print_version_report(results, version)

        if notifier.enabled() and not dry_run:
            payload = _build_notify_payload(version, results, "completed", start_time, cfg)
            notifier.send(payload)
            _notified[0] = True

    finally:
        if dashboard:
            dashboard.stop()
