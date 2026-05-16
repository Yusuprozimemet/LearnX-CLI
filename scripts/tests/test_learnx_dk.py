import pathlib
from unittest.mock import patch

import pytest

from scripts.learnx_dk import (
    EXPLORE_PERMISSIONS,
    SpecResult,
    _build_e2e_command,
    _checkout_spec_branch,
    _discover_specs,
    _load_config,
    _parse,
    _print_version_report,
    _spec_branch_name,
    build_command,
    build_docker_command,
    main,
    run_explore,
    run_implement,
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
    project, home = dirs
    with (
        patch("scripts.learnx_dk.pathlib.Path.cwd", return_value=project),
        patch("scripts.learnx_dk.pathlib.Path.home", return_value=home),
        patch("scripts.learnx_dk.subprocess.run") as mock_run,
    ):
        main(["--dry-run"])
    out = capsys.readouterr().out
    assert "docker" in out  # default is now Docker
    mock_run.assert_not_called()


def test_extra_args_forwarded_to_claude(dirs):
    project, home = dirs
    cmd = build_command(project, home, extra_args=["--model", "opus"])
    claude_idx = cmd.index("claude")
    tail = cmd[claude_idx:]
    assert "--model" in tail
    assert "opus" in tail


# ── Day 22 (v7) tests ────────────────────────────────────────────────────────


def test_load_config_returns_defaults_when_toml_missing(tmp_path):
    config = _load_config(tmp_path)
    assert config["project"]["docker_image"] == "learnx-dev"
    assert config["project"]["workspace"] == "/workspace"
    assert config["review"]["review_script"] == "scripts/run_review.py"


def test_load_config_reads_docker_image_from_toml(tmp_path):
    (tmp_path / "devloop.toml").write_text('[project]\ndocker_image = "custom-image"\n')
    config = _load_config(tmp_path)
    assert config["project"]["docker_image"] == "custom-image"


def test_load_config_merges_missing_keys_with_defaults(tmp_path):
    (tmp_path / "devloop.toml").write_text('[project]\ndocker_image = "custom-image"\n')
    config = _load_config(tmp_path)
    assert config["project"]["workspace"] == "/workspace"


def test_build_e2e_command_uses_config_cmd(dirs):
    project, home = dirs
    cmd = _build_e2e_command(project, e2e_cmd="go test ./...", image="go-dev", workspace="/app")
    assert "go" in cmd
    assert "test" in cmd
    assert "./..." in cmd
    assert "go-dev" in cmd


def test_run_implement_review_dry_run_uses_config_review_script(dirs, capsys):
    project, home = dirs
    config = {
        "validation": {"e2e_tests": "python -m pytest tutor/tests/e2e/ -v"},
        "review": {"review_script": "scripts/custom_review.py"},
    }
    run_implement(project, home, spec=None, review=True, extra_args=[], dry_run=True, config=config)
    out = capsys.readouterr().out
    assert "custom_review.py" in out


def test_build_e2e_command_exits_on_malformed_cmd(dirs):
    project, _ = dirs
    with pytest.raises(SystemExit) as exc:
        _build_e2e_command(project, e2e_cmd="bad 'unbalanced")
    assert exc.value.code == 1


def test_run_implement_partial_config_falls_back_to_defaults(dirs, capsys):
    project, home = dirs
    # config is missing 'review' section entirely
    config = {"validation": {"e2e_tests": "python -m pytest tutor/tests/e2e/ -v"}}
    run_implement(project, home, spec=None, review=True, extra_args=[], dry_run=True, config=config)
    out = capsys.readouterr().out
    assert "run_review.py" in out  # fell back to _DEFAULTS["review"]["review_script"]


def test_build_docker_command_uses_custom_image(dirs):
    project, home = dirs
    cmd = build_docker_command(project, home, extra_args=[], image="my-img", workspace="/app")
    assert "my-img" in cmd
    mounts = [cmd[i + 1] for i, a in enumerate(cmd) if a == "-v"]
    assert any("/app" in m for m in mounts)


def test_run_yolo_version_forwards_image_to_run_implement(tmp_path, dirs, capsys):
    """image/workspace from config must reach run_implement, not be hardcoded."""
    project, home = dirs
    ver_dir = tmp_path / "specs" / "v5"
    ver_dir.mkdir(parents=True)
    (ver_dir / "day1.md").write_text("# day1")

    with (
        patch("scripts.learnx_dk.run_implement") as mock_impl,
        patch("scripts.learnx_dk._checkout_spec_branch", return_value=True),
    ):
        run_yolo_version(
            tmp_path,
            home,
            "v5",
            review=False,
            extra_args=[],
            dry_run=False,
            image="custom-img",
            workspace="/custom",
        )

    mock_impl.assert_called_once()
    call_kwargs = mock_impl.call_args.kwargs
    assert call_kwargs.get("image") == "custom-img"
    assert call_kwargs.get("workspace") == "/custom"


def test_implement_review_dry_run_e2e_uses_custom_image(dirs, capsys):
    """E2E command in --review path must use the same image/workspace as the container."""
    project, home = dirs
    run_implement(
        project,
        home,
        spec=None,
        review=True,
        extra_args=[],
        dry_run=True,
        image="custom-img",
        workspace="/custom",
    )
    out = capsys.readouterr().out
    assert "custom-img" in out
    assert "/custom" in out


# ── Day 20 (v6) tests ────────────────────────────────────────────────────────


def test_default_dry_run_uses_docker(dirs, capsys):
    """No flags — Docker container is the default execution path."""
    project, home = dirs
    with (
        patch("scripts.learnx_dk.pathlib.Path.cwd", return_value=project),
        patch("scripts.learnx_dk.pathlib.Path.home", return_value=home),
        patch("scripts.learnx_dk.subprocess.run") as mock_run,
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
        patch("scripts.learnx_dk.subprocess.run") as mock_run,
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


def test_explore_writes_settings_local_when_claude_dir_absent(tmp_path, monkeypatch):
    """run_explore() must not raise FileNotFoundError on a fresh clone."""
    local = tmp_path / ".claude" / "settings.local.json"
    monkeypatch.setattr("scripts.learnx_dk.SETTINGS_LOCAL", local)
    with patch("scripts.learnx_dk.subprocess.run"):
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


# ── Day 18 (v5) tests ────────────────────────────────────────────────────────


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
    run_yolo_version(tmp_path, home, "v5", review=False, extra_args=[], dry_run=True)
    out = capsys.readouterr().out
    assert "day1.md" in out
    assert "day2.md" in out


# ── Day 19 (v5) tests ────────────────────────────────────────────────────────


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
        patch("scripts.learnx_dk.run_implement") as mock_impl,
    ):
        run_yolo_version(tmp_path, home, "v5", review=False, extra_args=[], dry_run=False)

    mock_impl.assert_not_called()
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
    run_yolo_version(tmp_path, home, "v5", review=False, extra_args=[], dry_run=True)
    out = capsys.readouterr().out
    assert "sandbox/v5-day1" in out
