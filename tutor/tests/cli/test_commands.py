import json

import pytest

from tutor.cli.commands import _format_duration, _read_meta


def test_read_meta_returns_empty_on_missing_file(tmp_path):
    result = _read_meta(tmp_path / "nonexistent.meta.json")
    assert result == {}


def test_read_meta_returns_empty_on_invalid_json(tmp_path):
    bad = tmp_path / "bad.meta.json"
    bad.write_text("not json", encoding="utf-8")
    result = _read_meta(bad)
    assert result == {}


def test_read_meta_returns_dict_on_valid_file(tmp_path):
    meta_file = tmp_path / "tutorial.meta.json"
    data = {"source_file": "week2/3.md", "generated_at": "2026-05-09T14:32:11", "total_duration_s": 1574.3}
    meta_file.write_text(json.dumps(data), encoding="utf-8")
    result = _read_meta(meta_file)
    assert result["source_file"] == "week2/3.md"
    assert result["total_duration_s"] == 1574.3


def test_format_duration_zero_returns_blank():
    assert _format_duration(0) == ""


def test_format_duration_negative_returns_blank():
    assert _format_duration(-5) == ""


def test_format_duration_correct_formatting():
    assert _format_duration(3674.0) == "61:14"


def test_format_duration_simple():
    assert _format_duration(90) == "1:30"


def test_sessions_output_handles_missing_meta(tmp_path, capsys):
    from pathlib import Path
    from unittest.mock import patch

    from tutor.cli.commands import AUDIO_DIR, cmd_sessions

    session_dir = tmp_path / "test_session"
    (session_dir / "tutorial_units").mkdir(parents=True)

    with (
        patch.object(Path, "exists", return_value=True),
        patch("tutor.cli.commands.AUDIO_DIR", tmp_path),
        patch("tutor.cli.video_commands.VIDEO_DIR", tmp_path / "video"),
    ):
        from tutor.cli.commands import ShellContext

        ctx = ShellContext()
        cmd_sessions([], ctx)

    captured = capsys.readouterr()
    assert "test_session" in captured.out
