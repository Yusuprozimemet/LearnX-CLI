import pathlib
import subprocess
from io import StringIO
from unittest.mock import patch

import pytest

from scripts.learnx_dk import build_command, main


@pytest.fixture()
def dirs(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    return project, home


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
    with patch("scripts.learnx_dk.pathlib.Path.cwd", return_value=project), \
         patch("scripts.learnx_dk.pathlib.Path.home", return_value=home), \
         patch("scripts.learnx_dk.subprocess.run") as mock_run:
        main(["--dry-run"])
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
