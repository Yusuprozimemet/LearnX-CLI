"""Tests for version runner, spec discovery, resilience flags (Day 18, 19, 24, 25)."""

import sys
from unittest.mock import patch

import pytest

from scripts.learnx_dk import (
    SpecResult,
    _checkout_spec_branch,
    _discover_specs,
    _extract_int_flag,
    _is_rate_limited,
    _print_version_report,
    _run_with_timeout,
    _spec_branch_name,
    main,
    run_yolo_version,
)


# ── Day 18/19 — spec discovery and branch management ─────────────────────────


def test_discover_specs_numeric_sort(tmp_path):
    ver_dir = tmp_path / "specs" / "v5"
    ver_dir.mkdir(parents=True)
    for name in ("day10.md", "day2.md", "day1.md"):
        (ver_dir / name).write_text(f"# {name}")
    result = _discover_specs(tmp_path / "specs", "v5")
    assert [p.name for p in result] == ["day1.md", "day2.md", "day10.md"]


def test_discover_specs_missing_dir_exits(tmp_path):
    with pytest.raises(SystemExit) as exc:
        _discover_specs(tmp_path / "specs", "v99")
    assert exc.value.code == 1


def test_spec_result_fields():
    r = SpecResult(spec_name="day1", status="DONE", duration_s=120.0, branch="sandbox/v5-day1")
    assert r.spec_name == "day1"
    assert r.status == "DONE"
    assert r.duration_s == 120.0
    assert r.branch == "sandbox/v5-day1"


def test_spec_result_retries_defaults_to_zero():
    r = SpecResult("day1", "DONE", 60.0, "sandbox/v5-day1")
    assert r.retries == 0


def test_spec_branch_name():
    assert _spec_branch_name("v5", "day1") == "sandbox/v5-day1"
    assert _spec_branch_name("v5", "day10") == "sandbox/v5-day10"


def test_checkout_spec_branch_dry_run(capsys):
    ok = _checkout_spec_branch("sandbox/v5-day1", dry_run=True)
    out = capsys.readouterr().out
    assert ok is True
    assert "git checkout main" in out
    assert "sandbox/v5-day1" in out


def test_checkout_spec_branch_returns_false_on_git_failure(capsys):
    with patch("scripts.dk.runners.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        ok = _checkout_spec_branch("sandbox/v5-day1", dry_run=False)
    assert ok is False
    assert "error" in capsys.readouterr().out


def test_print_version_report_shows_all_specs(capsys):
    results = [
        SpecResult("day1", "DONE", 60.0, "sandbox/v5-day1"),
        SpecResult("day2", "FAILED", 120.0, "sandbox/v5-day2"),
    ]
    _print_version_report(results, "v5")
    out = capsys.readouterr().out
    assert "day1" in out
    assert "day2" in out
    assert "✓" in out
    assert "✗" in out


def test_run_yolo_version_dry_run_prints_each_spec(tmp_path, dirs, capsys):
    project, home = dirs
    ver_dir = tmp_path / "specs" / "v5"
    ver_dir.mkdir(parents=True)
    (ver_dir / "day1.md").write_text("# day1")
    (ver_dir / "day2.md").write_text("# day2")
    run_yolo_version(tmp_path, home, "v5", review=False, extra_args=[], dry_run=True)
    out = capsys.readouterr().out
    assert "day1.md" in out
    assert "day2.md" in out


def test_run_yolo_version_dry_run_shows_branch_names(tmp_path, dirs, capsys):
    project, home = dirs
    ver_dir = tmp_path / "specs" / "v5"
    ver_dir.mkdir(parents=True)
    (ver_dir / "day1.md").write_text("# day1")
    run_yolo_version(tmp_path, home, "v5", review=False, extra_args=[], dry_run=True)
    out = capsys.readouterr().out
    assert "sandbox/v5-day1" in out


def test_run_yolo_version_records_failed_when_checkout_fails(tmp_path, dirs, capsys):
    project, home = dirs
    ver_dir = tmp_path / "specs" / "v5"
    ver_dir.mkdir(parents=True)
    (ver_dir / "day1.md").write_text("# day1")

    with (
        patch("scripts.dk.runners._checkout_spec_branch", return_value=False),
        patch("scripts.dk.runners._run_with_timeout") as mock_run,
    ):
        run_yolo_version(tmp_path, home, "v5", review=False, extra_args=[], dry_run=False)

    mock_run.assert_not_called()
    out = capsys.readouterr().out
    assert "FAILED" in out


# ── Day 24 — resilience flags ─────────────────────────────────────────────────


def test_extract_int_flag_present():
    val, rest = _extract_int_flag(["--session-timeout", "45", "--dry-run"], "--session-timeout")
    assert val == 45
    assert rest == ["--dry-run"]


def test_extract_int_flag_absent():
    val, rest = _extract_int_flag(["--dry-run"], "--session-timeout")
    assert val is None
    assert rest == ["--dry-run"]


def test_run_with_timeout_kills_on_session_timeout():
    """Process that runs longer than session_timeout_s must be killed (timed_out=True)."""
    cmd = [sys.executable, "-c", "import time; time.sleep(60)"]
    rc, lines, timed_out = _run_with_timeout(cmd, session_timeout_s=2.0, idle_timeout_s=0)
    assert timed_out is True
    assert rc != 0


def test_wait_zero_overrides_config_default(dirs):
    """--wait 0 must pass rate_limit_wait_s=0.0, not fall back to config default."""
    project, home = dirs
    with (
        patch("scripts.learnx_dk.pathlib.Path.cwd", return_value=project),
        patch("scripts.learnx_dk.pathlib.Path.home", return_value=home),
        patch("scripts.learnx_dk.run_yolo_version") as mock_yolo,
    ):
        main(["--version", "v5", "--wait", "0"])
    call_kwargs = mock_yolo.call_args.kwargs
    assert call_kwargs.get("rate_limit_wait_s") == 0.0


# ── Day 25 — rate limit detection ────────────────────────────────────────────


def test_is_rate_limited_matches_pattern():
    lines = ["some output", "Error: rate limit exceeded", "bye"]
    assert _is_rate_limited(lines, ["rate limit exceeded"]) is True


def test_is_rate_limited_case_insensitive():
    lines = ["You've Hit Your Limit for today"]
    assert _is_rate_limited(lines, ["you've hit your limit"]) is True


def test_is_rate_limited_no_match():
    lines = ["all good", "tests passed", "done"]
    assert _is_rate_limited(lines, ["rate limit exceeded"]) is False
