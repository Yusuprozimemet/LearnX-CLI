"""Tests for Docker command building and config loading (Day 2, Day 22)."""

from unittest.mock import patch

import pytest

from scripts.devloop import (
    _build_e2e_command,
    _load_config,
    build_command,
    build_docker_command,
    run_implement,
    run_yolo_version,
)

# ── Day 2 — Docker command building ──────────────────────────────────────────


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


def test_extra_args_forwarded_to_claude(dirs):
    project, home = dirs
    cmd = build_command(project, home, extra_args=["--model", "opus"])
    claude_idx = cmd.index("claude")
    tail = cmd[claude_idx:]
    assert "--model" in tail
    assert "opus" in tail


def test_build_docker_command_uses_custom_image(dirs):
    project, home = dirs
    cmd = build_docker_command(project, home, extra_args=[], image="my-img", workspace="/app")
    assert "my-img" in cmd
    mounts = [cmd[i + 1] for i, a in enumerate(cmd) if a == "-v"]
    assert any("/app" in m for m in mounts)


def test_build_docker_command_omits_it_when_not_interactive(dirs):
    project, home = dirs
    cmd = build_docker_command(project, home, extra_args=[], interactive=False)
    assert "-it" not in cmd
    assert "-i" not in cmd


def test_build_docker_command_includes_it_by_default(dirs):
    project, home = dirs
    cmd = build_docker_command(project, home, extra_args=[])
    assert "-it" in cmd


# ── Day 22 — Config loading and E2E command ───────────────────────────────────


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


def test_build_e2e_command_exits_on_malformed_cmd(dirs):
    project, _ = dirs
    with pytest.raises(SystemExit) as exc:
        _build_e2e_command(project, e2e_cmd="bad 'unbalanced")
    assert exc.value.code == 1


def test_run_implement_review_dry_run_uses_config_review_script(dirs, capsys):
    project, home = dirs
    config = {
        "validation": {"e2e_tests": "python -m pytest tutor/tests/e2e/ -v"},
        "review": {"review_script": "scripts/custom_review.py"},
    }
    run_implement(project, home, spec=None, review=True, extra_args=[], dry_run=True, config=config)
    out = capsys.readouterr().out
    assert "custom_review.py" in out


def test_run_implement_partial_config_falls_back_to_defaults(dirs, capsys):
    project, home = dirs
    config = {"validation": {"e2e_tests": "python -m pytest tutor/tests/e2e/ -v"}}
    run_implement(project, home, spec=None, review=True, extra_args=[], dry_run=True, config=config)
    out = capsys.readouterr().out
    assert "run_review.py" in out


def test_implement_review_dry_run_e2e_uses_custom_image(dirs, capsys):
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


def test_run_yolo_version_uses_image_from_config(tmp_path, dirs, capsys):
    project, home = dirs
    ver_dir = tmp_path / "specs" / "v5"
    ver_dir.mkdir(parents=True)
    (ver_dir / "day1.md").write_text("# day1")

    config = {"project": {"docker_image": "custom-img", "workspace": "/custom"}}
    with patch("scripts.dk.runners._checkout_spec_branch", return_value=True):
        run_yolo_version(
            tmp_path, home, "v5", review=False, extra_args=[], dry_run=True, config=config
        )

    out = capsys.readouterr().out
    assert "custom-img" in out
    assert "/custom" in out
