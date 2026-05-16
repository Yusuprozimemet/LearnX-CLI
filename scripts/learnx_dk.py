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

import os
import pathlib
import sys

# Re-exported for backward compatibility (run_review.py, tests)
from scripts.dk.config import _DEFAULTS, SpecResult, _load_config  # noqa: F401
from scripts.dk.dashboard import DASHBOARD_HTML, DashboardServer, OutputBuffer  # noqa: F401
from scripts.dk.docker import (  # noqa: F401
    EXPLORE_PERMISSIONS,
    IMAGE,
    SETTINGS_LOCAL,
    WORKSPACE,
    _build_e2e_command,
    build_command,
    build_docker_command,
)
from scripts.dk.notifier import Notifier, _build_notify_payload  # noqa: F401
from scripts.dk.process import (  # noqa: F401
    _extract_int_flag,
    _is_rate_limited,
    _run_with_timeout,
)
from scripts.dk.runners import (  # noqa: F401
    _checkout_spec_branch,
    _discover_specs,
    _print_version_report,
    _spec_branch_name,
    run_explore,
    run_implement,
    run_yolo_version,
)


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

    serve = "--serve" in extra
    extra = [a for a in extra if a != "--serve"]
    port_override, extra = _extract_int_flag(extra, "--port")
    dash_cfg = config.get("dashboard", _DEFAULTS["dashboard"])
    _raw_env = os.environ.get("LEARNX_DASHBOARD_PORT", "")
    try:
        env_port: int | None = int(_raw_env) if _raw_env else None
    except ValueError:
        env_port = None
    port = (
        port_override
        if port_override is not None
        else (env_port if env_port is not None else dash_cfg["default_port"])
    )

    if serve and not version:
        print("[dashboard] --serve is only used with --version; ignoring", flush=True)

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
            serve=serve,
            port=port,
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
