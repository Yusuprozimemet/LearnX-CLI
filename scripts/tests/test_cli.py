"""Tests for CLI parsing, explore mode, and implement runner (Day 18, 20)."""

import pathlib
from unittest.mock import patch

import pytest

from scripts.learnx_dk import (
    EXPLORE_PERMISSIONS,
    _parse,
    main,
    run_explore,
    run_implement,
)


# ── Day 20 — default path and dry-run output ─────────────────────────────────


def test_dry_run_prints_command_no_subprocess(dirs, capsys):
    project, home = dirs
    with (
        patch("scripts.learnx_dk.pathlib.Path.cwd", return_value=project),
        patch("scripts.learnx_dk.pathlib.Path.home", return_value=home),
        patch("scripts.dk.runners.subprocess.run") as mock_run,
    ):
        main(["--dry-run"])
    out = capsys.readouterr().out
    assert "docker" in out
    mock_run.assert_not_called()


def test_default_dry_run_uses_docker(dirs, capsys):
    project, home = dirs
    with (
        patch("scripts.learnx_dk.pathlib.Path.cwd", return_value=project),
        patch("scripts.learnx_dk.pathlib.Path.home", return_value=home),
        patch("scripts.dk.runners.subprocess.run") as mock_run,
    ):
        main(["--dry-run"])
    out = capsys.readouterr().out
    assert "docker" in out
    mock_run.assert_not_called()


def test_default_dry_run_prints_docker_command(dirs, capsys):
    project, home = dirs
    with (
        patch("scripts.learnx_dk.pathlib.Path.cwd", return_value=project),
        patch("scripts.learnx_dk.pathlib.Path.home", return_value=home),
        patch("scripts.dk.runners.subprocess.run") as mock_run,
    ):
        main(["--dry-run"])
    out = capsys.readouterr().out
    assert "docker" in out
    mock_run.assert_not_called()


def test_implement_dry_run_has_skip_permissions(dirs, capsys):
    project, home = dirs
    run_implement(project, home, spec=None, review=False, extra_args=[], dry_run=True)
    out = capsys.readouterr().out
    assert "--dangerously-skip-permissions" in out


def test_implement_review_dry_run_shows_three_steps(dirs, capsys):
    project, home = dirs
    run_implement(project, home, spec=None, review=True, extra_args=[], dry_run=True)
    out = capsys.readouterr().out
    assert "Step 1" in out
    assert "Step 2" in out
    assert "Step 3" in out


def test_implement_review_dry_run_with_spec(dirs, capsys):
    project, home = dirs
    spec = pathlib.Path("specs/v5/day1.md")
    run_implement(project, home, spec=spec, review=True, extra_args=[], dry_run=True)
    out = capsys.readouterr().out
    assert "--spec" in out
    assert "day1.md" in out


# ── Explore mode ─────────────────────────────────────────────────────────────


def test_explore_writes_settings_local_when_claude_dir_absent(tmp_path, monkeypatch):
    """run_explore() must not raise FileNotFoundError on a fresh clone."""
    local = tmp_path / ".claude" / "settings.local.json"
    monkeypatch.setattr("scripts.dk.runners.SETTINGS_LOCAL", local)
    with patch("scripts.dk.runners.subprocess.run"):
        run_explore([], dry_run=False)
    assert not local.exists()  # cleaned up on exit


def test_explore_dry_run_runs_on_host(capsys):
    """--explore outputs a host claude command, not docker."""
    run_explore([], dry_run=True)
    out = capsys.readouterr().out
    assert "docker" not in out
    assert "claude" in out


def test_explore_dry_run_shows_settings_local(capsys):
    """--explore writes and deletes settings.local.json."""
    run_explore([], dry_run=True)
    out = capsys.readouterr().out
    assert "settings.local.json" in out


def test_explore_permissions_allow_only_reads():
    """Explore mode must not allow Edit or Write."""
    allows = EXPLORE_PERMISSIONS["permissions"]["allow"]
    assert not any("Edit" in rule for rule in allows)
    assert not any("Write" in rule for rule in allows)


# ── Day 18 — CLI parsing ──────────────────────────────────────────────────────


def test_parse_version_flag():
    _, _, _, _, version, _ = _parse(["--version", "v5"])
    assert version == "v5"


def test_parse_version_equals_form():
    _, _, _, _, version, _ = _parse(["--version=v5"])
    assert version == "v5"


def test_version_and_spec_mutually_exclusive():
    with pytest.raises(SystemExit) as exc:
        _parse(["--version", "v5", "--spec", "specs/v5/day1.md"])
    assert exc.value.code == 1


def test_explore_and_review_mutually_exclusive():
    with pytest.raises(SystemExit) as exc:
        _parse(["--explore", "--review"])
    assert exc.value.code == 1


def test_explore_and_version_mutually_exclusive():
    with pytest.raises(SystemExit) as exc:
        _parse(["--explore", "--version", "v5"])
    assert exc.value.code == 1
