import pathlib
from unittest.mock import patch

import pytest

from scripts.learnx_dk import (
    ASSISTED_PERMISSIONS,
    SpecResult,
    _checkout_spec_branch,
    _discover_specs,
    _parse,
    _print_version_report,
    _spec_branch_name,
    build_command,
    main,
    run_assisted,
    run_container,
    run_supervised,
    run_yolo,
    run_yolo_version,
)


@pytest.fixture()
def dirs(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    return project, home


# ── Day 2 tests (unchanged) ──────────────────────────────────────────────────


def test_command_contains_skip_permissions(dirs):
    project, home = dirs
    cmd = build_command(project, home, extra_args=[])
    assert "--dangerously-skip-permissions" in cmd


def test_command_mounts_project_as_workspace(dirs):
    project, home = dirs
    cmd = build_command(project, home, extra_args=[])
    mounts = [cmd[i + 1] for i, a in enumerate(cmd) if a == "-v"]
    assert any(m.endswith(":/workspace") for m in mounts)


def test_command_mounts_claude_dir_readonly(dirs):
    project, home = dirs
    claude_dir = home / ".claude"
    claude_dir.mkdir()
    cmd = build_command(project, home, extra_args=[])
    mounts = [cmd[i + 1] for i, a in enumerate(cmd) if a == "-v"]
    assert any(":ro" in m and ".claude" in m for m in mounts)


def test_command_omits_gitconfig_when_absent(dirs):
    project, home = dirs
    cmd = build_command(project, home, extra_args=[])
    mounts = [cmd[i + 1] for i, a in enumerate(cmd) if a == "-v"]
    assert not any(".gitconfig" in m for m in mounts)


def test_command_omits_claude_mount_when_absent(dirs):
    project, home = dirs
    cmd = build_command(project, home, extra_args=[])
    mounts = [cmd[i + 1] for i, a in enumerate(cmd) if a == "-v"]
    assert not any(".claude" in m for m in mounts)


def test_dry_run_prints_command_no_subprocess(dirs, capsys):
    # Default mode is supervised — dry-run prints the host claude command, not docker.
    project, home = dirs
    with (
        patch("scripts.learnx_dk.pathlib.Path.cwd", return_value=project),
        patch("scripts.learnx_dk.pathlib.Path.home", return_value=home),
        patch("scripts.learnx_dk.subprocess.run") as mock_run,
    ):
        main(["--dry-run"])
    out = capsys.readouterr().out
    assert "claude" in out
    mock_run.assert_not_called()


def test_container_dry_run_prints_docker_command(dirs, capsys):
    project, home = dirs
    with (
        patch("scripts.learnx_dk.pathlib.Path.cwd", return_value=project),
        patch("scripts.learnx_dk.pathlib.Path.home", return_value=home),
        patch("scripts.learnx_dk.subprocess.run") as mock_run,
    ):
        main(["--mode", "container", "--dry-run"])
    out = capsys.readouterr().out
    assert "docker" in out
    mock_run.assert_not_called()


def test_extra_args_forwarded_to_claude(dirs):
    project, home = dirs
    cmd = build_command(project, home, extra_args=["--model", "opus"])
    claude_idx = cmd.index("claude")
    tail = cmd[claude_idx:]
    assert "--model" in tail
    assert "opus" in tail


# ── Day 2b tests ─────────────────────────────────────────────────────────────


def test_default_mode_is_supervised(dirs, capsys):
    project, home = dirs
    with (
        patch("scripts.learnx_dk.pathlib.Path.cwd", return_value=project),
        patch("scripts.learnx_dk.pathlib.Path.home", return_value=home),
        patch("scripts.learnx_dk.subprocess.run"),
    ):
        main(["--dry-run"])
    out = capsys.readouterr().out
    assert "claude" in out
    assert "docker" not in out


def test_supervised_dry_run_no_docker(capsys):
    assert _parse(["--mode", "supervised"])[0] == "supervised"
    run_supervised([], dry_run=True)
    out = capsys.readouterr().out
    assert out.strip() == "claude"


def test_assisted_dry_run_shows_settings_write(capsys):
    run_assisted([], dry_run=True)
    out = capsys.readouterr().out
    assert "settings.local.json" in out


def test_assisted_writes_and_deletes_settings_local(tmp_path, monkeypatch):
    local = tmp_path / "settings.local.json"
    monkeypatch.setattr("scripts.learnx_dk.SETTINGS_LOCAL", local)
    with patch("scripts.learnx_dk.subprocess.run"):
        run_assisted([], dry_run=False)
    assert not local.exists()


def test_assisted_cleans_up_on_exception(tmp_path, monkeypatch):
    local = tmp_path / "settings.local.json"
    monkeypatch.setattr("scripts.learnx_dk.SETTINGS_LOCAL", local)
    with patch("scripts.learnx_dk.subprocess.run", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError):
            run_assisted([], dry_run=False)
    assert not local.exists()


def test_assisted_permissions_have_no_deny():
    assert "deny" not in ASSISTED_PERMISSIONS.get("permissions", {})


def test_assisted_permissions_allow_git_commit():
    allows = ASSISTED_PERMISSIONS["permissions"]["allow"]
    assert any("git commit" in rule for rule in allows)


def test_container_dry_run_has_skip_permissions(dirs, capsys):
    project, home = dirs
    run_container(project, home, extra_args=[], dry_run=True)
    out = capsys.readouterr().out
    assert "--dangerously-skip-permissions" in out


def test_yolo_dry_run_shows_three_steps(dirs, capsys):
    project, home = dirs
    run_yolo(project, home, spec_path=None, extra_args=[], dry_run=True)
    out = capsys.readouterr().out
    assert "Step 1" in out
    assert "Step 2" in out
    assert "Step 3" in out


def test_yolo_dry_run_with_spec(dirs, capsys):
    project, home = dirs
    spec = pathlib.Path("specs/v3/day13.md")
    run_yolo(project, home, spec_path=spec, extra_args=[], dry_run=True)
    out = capsys.readouterr().out
    assert "--spec" in out
    assert "day13.md" in out


def test_unknown_mode_exits_1():
    with pytest.raises(SystemExit) as exc:
        main(["--mode", "invalid"])
    assert exc.value.code == 1


def test_parse_mode_long_form():
    mode, _, _, _, _ = _parse(["--mode=container"])
    assert mode == "container"


# ── Day 18 (v5) tests ─────────────────────────────────────────────────────────


def test_parse_version_flag():
    _, _, _, version, _ = _parse(["--mode", "yolo", "--version", "v5"])
    assert version == "v5"


def test_version_normalizes_mode_to_yolo():
    mode, _, _, version, _ = _parse(["--mode", "supervised", "--version", "v5"])
    assert version == "v5"
    assert mode == "yolo"


def test_version_without_mode_normalizes_to_yolo():
    mode, _, _, version, _ = _parse(["--version", "v5"])
    assert version == "v5"
    assert mode == "yolo"


def test_parse_version_equals_form():
    _, _, _, version, _ = _parse(["--version=v5"])
    assert version == "v5"


def test_version_and_spec_mutually_exclusive():
    with pytest.raises(SystemExit) as exc:
        _parse(["--version", "v5", "--spec", "specs/v5/day18.md"])
    assert exc.value.code == 1


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


def test_run_yolo_version_dry_run_prints_each_spec(tmp_path, dirs, capsys):
    project, home = dirs
    ver_dir = tmp_path / "specs" / "v5"
    ver_dir.mkdir(parents=True)
    (ver_dir / "day1.md").write_text("# day1")
    (ver_dir / "day2.md").write_text("# day2")
    run_yolo_version(tmp_path, home, "v5", extra_args=[], dry_run=True)
    out = capsys.readouterr().out
    assert "day1.md" in out
    assert "day2.md" in out


# ── Day 19 (v5) tests ─────────────────────────────────────────────────────────


def test_spec_result_fields():
    r = SpecResult(spec_name="day1", status="DONE", duration_s=120.0, branch="sandbox/v5-day1")
    assert r.spec_name == "day1"
    assert r.status == "DONE"
    assert r.duration_s == 120.0
    assert r.branch == "sandbox/v5-day1"


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
    with patch("scripts.learnx_dk.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        ok = _checkout_spec_branch("sandbox/v5-day1", dry_run=False)
    assert ok is False
    assert "error" in capsys.readouterr().out


def test_run_yolo_version_records_failed_when_checkout_fails(tmp_path, dirs, capsys):
    project, home = dirs
    ver_dir = tmp_path / "specs" / "v5"
    ver_dir.mkdir(parents=True)
    (ver_dir / "day1.md").write_text("# day1")

    with (
        patch("scripts.learnx_dk._checkout_spec_branch", return_value=False),
        patch("scripts.learnx_dk.run_yolo") as mock_yolo,
    ):
        run_yolo_version(tmp_path, home, "v5", extra_args=[], dry_run=False)

    mock_yolo.assert_not_called()
    out = capsys.readouterr().out
    assert "FAILED" in out


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


def test_run_yolo_version_dry_run_shows_branch_names(tmp_path, dirs, capsys):
    project, home = dirs
    ver_dir = tmp_path / "specs" / "v5"
    ver_dir.mkdir(parents=True)
    (ver_dir / "day1.md").write_text("# day1")
    run_yolo_version(tmp_path, home, "v5", extra_args=[], dry_run=True)
    out = capsys.readouterr().out
    assert "sandbox/v5-day1" in out
