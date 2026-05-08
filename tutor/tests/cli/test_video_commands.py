"""Tests for tutor/cli/video_commands.py."""
import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tutor.cli.commands import ShellContext
from tutor.cli.video_commands import (
    VIDEO_DIR,
    _assert_audio_ready,
    _confirm_overwrite,
    cmd_video,
    cmd_vsessions,
)


def _ctx(**kwargs) -> ShellContext:
    ctx = ShellContext()
    for k, v in kwargs.items():
        setattr(ctx, k, v)
    return ctx


# ── _assert_audio_ready ──────────────────────────────────────────────────────

def test_cmd_video_missing_units_json(tmp_path):
    """Audio dir exists, tutorial_units has MP3s, but no tutorial.units.json → ValueError."""
    audio_dir = tmp_path / "audio" / "test_session"
    units_dir = audio_dir / "tutorial_units"
    units_dir.mkdir(parents=True)
    (units_dir / "unit_01.mp3").touch()
    # No tutorial.units.json

    with pytest.raises(ValueError, match="tutorial.units.json"):
        _assert_audio_ready(audio_dir)


def test_cmd_video_unknown_session(tmp_path, capsys):
    """Session not in audio/ → prints error, does not crash."""
    with patch("tutor.cli.video_commands.AUDIO_DIR", tmp_path / "audio"):
        ctx = _ctx()
        cmd_video(["nonexistent_session"], ctx)
        out = capsys.readouterr().out
        assert "Error" in out or "not found" in out


def test_assert_audio_ready_no_mp3s(tmp_path):
    """audio dir exists with units.json but no MP3s → ValueError."""
    audio_dir = tmp_path / "audio" / "sess"
    units_dir = audio_dir / "tutorial_units"
    units_dir.mkdir(parents=True)
    (audio_dir / "tutorial.units.json").write_text("[]")

    with pytest.raises(ValueError, match="No MP3"):
        _assert_audio_ready(audio_dir)


# ── session context inference ─────────────────────────────────────────────────

def test_cmd_video_infers_session_from_context(capsys):
    """ctx.current_session set, no arg → uses it (errors out at audio check)."""
    ctx = _ctx(current_session="week2_3")
    with patch("tutor.cli.video_commands.AUDIO_DIR", Path("/nonexistent")):
        cmd_video([], ctx)
    out = capsys.readouterr().out
    # Should attempt to use "week2_3" and fail at audio check, not usage error
    assert "Usage: /video" not in out


def test_cmd_video_no_session_no_context_prints_usage(capsys):
    """No arg and no current_session → prints usage."""
    ctx = _ctx()
    cmd_video([], ctx)
    out = capsys.readouterr().out
    assert "Usage" in out


# ── overwrite prompt ──────────────────────────────────────────────────────────

def test_cmd_video_prompts_before_overwrite(tmp_path, capsys):
    """full_session.mp4 exists → ask before overwriting; 'n' → skip."""
    # Set up a fake complete audio session
    audio_dir = tmp_path / "audio" / "test_sess"
    units_dir = audio_dir / "tutorial_units"
    units_dir.mkdir(parents=True)
    (units_dir / "unit_01.mp3").touch()
    (audio_dir / "tutorial.units.json").write_text("[]")

    # Pre-existing video
    video_dir = tmp_path / "video" / "test_sess"
    video_dir.mkdir(parents=True)
    mp4 = video_dir / "full_session.mp4"
    mp4.touch()

    with patch("tutor.cli.video_commands.AUDIO_DIR", tmp_path / "audio"), \
         patch("tutor.cli.video_commands.VIDEO_DIR", tmp_path / "video"), \
         patch("builtins.input", return_value="n"):
        ctx = _ctx()
        cmd_video(["test_sess"], ctx)

    out = capsys.readouterr().out
    assert "Skipped" in out


def test_confirm_overwrite_yes(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "y")
    assert _confirm_overwrite(Path("dummy.mp4")) is True


def test_confirm_overwrite_no(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "n")
    assert _confirm_overwrite(Path("dummy.mp4")) is False


# ── cmd_vsessions ─────────────────────────────────────────────────────────────

def test_sessions_shows_mp4_badge(tmp_path, capsys):
    """Session dir with full_session.mp4 → '[mp4]' in output."""
    sess = tmp_path / "week2_3"
    sess.mkdir()
    mp4 = sess / "full_session.mp4"
    mp4.write_bytes(b"x" * 1024)   # 1 KB fake MP4

    with patch("tutor.cli.video_commands.VIDEO_DIR", tmp_path):
        cmd_vsessions([], _ctx())

    out = capsys.readouterr().out
    assert "[mp4]" in out
    assert "week2_3" in out


def test_sessions_no_output_when_empty(tmp_path, capsys):
    """No completed videos → dim message."""
    with patch("tutor.cli.video_commands.VIDEO_DIR", tmp_path):
        cmd_vsessions([], _ctx())
    out = capsys.readouterr().out
    assert "[mp4]" not in out


# ── sessions badge in cmd_sessions ───────────────────────────────────────────

def test_sessions_command_shows_mp4_badge(tmp_path, capsys):
    """cmd_sessions shows [mp4] when video/<session>/full_session.mp4 exists."""
    from tutor.cli.commands import cmd_sessions

    audio_dir = tmp_path / "audio"
    sess = audio_dir / "test_sess"
    units_dir = sess / "tutorial_units"
    units_dir.mkdir(parents=True)
    (units_dir / "unit_01.mp3").touch()

    video_dir = tmp_path / "video" / "test_sess"
    video_dir.mkdir(parents=True)
    (video_dir / "full_session.mp4").touch()

    with patch("tutor.cli.commands.AUDIO_DIR", audio_dir), \
         patch("tutor.cli.video_commands.VIDEO_DIR", tmp_path / "video"):
        cmd_sessions([], _ctx())

    out = capsys.readouterr().out
    assert "[mp4]" in out


def test_sessions_no_badge_without_mp4(tmp_path, capsys):
    """cmd_sessions shows no [mp4] when MP4 is absent."""
    from tutor.cli.commands import cmd_sessions

    audio_dir = tmp_path / "audio"
    sess = audio_dir / "test_sess"
    units_dir = sess / "tutorial_units"
    units_dir.mkdir(parents=True)
    (units_dir / "unit_01.mp3").touch()

    with patch("tutor.cli.commands.AUDIO_DIR", audio_dir), \
         patch("tutor.cli.video_commands.VIDEO_DIR", tmp_path / "video"):
        cmd_sessions([], _ctx())

    out = capsys.readouterr().out
    assert "[mp4]" not in out
