import subprocess

import pytest

import tutor.visual.video_assembler as va
from tutor.exceptions import VideoError


def test_concat_script_written_correctly(tmp_path):
    entries = [
        (tmp_path / "01_hook.png", 6.31),
        (tmp_path / "01_concept.png", 38.44),
        (tmp_path / "01_memory.png", 9.25),
    ]
    script = tmp_path / "test.concat.txt"
    va._write_concat_script(entries, script)

    content = script.read_text(encoding="utf-8")
    assert "ffconcat version 1.0" in content
    assert "duration 6.310" in content
    assert "duration 38.440" in content
    # Last file appears twice (no duration on second appearance)
    lines = content.strip().splitlines()
    # Path is normalised to forward slashes in the concat script
    expected_path = str(entries[-1][0].resolve()).replace("\\", "/")
    assert lines[-1] == f"file '{expected_path}'"
    assert "duration" not in lines[-1]


def test_ffmpeg_called_with_yuv420p(tmp_path, monkeypatch):
    captured = []

    def mock_run(args, **kwargs):
        captured.append(args)
        return subprocess.CompletedProcess(args, 0, b"", b"")

    monkeypatch.setattr(subprocess, "run", mock_run)

    slides_with_dur = [(tmp_path / "01_hook.png", 5.0)]
    mp3 = tmp_path / "unit_01.mp3"
    mp3.touch()
    output = tmp_path / "unit_01.mp4"

    va._build_unit_video(slides_with_dur, mp3, output)

    assert captured, "subprocess.run was not called"
    assert "-pix_fmt" in captured[0]
    yuv_idx = captured[0].index("-pix_fmt")
    assert captured[0][yuv_idx + 1] == "yuv420p"


def test_run_ffmpeg_raises_on_nonzero_exit(monkeypatch):
    def failing_run(args, **kwargs):
        return subprocess.CompletedProcess(args, 1, b"", b"some error")

    monkeypatch.setattr(subprocess, "run", failing_run)

    with pytest.raises(VideoError, match="ffmpeg failed"):
        va._run_ffmpeg(["ffmpeg", "-version"])


def test_run_ffmpeg_no_error_on_success(monkeypatch):
    monkeypatch.setattr(
        subprocess, "run", lambda args, **kw: subprocess.CompletedProcess(args, 0, b"", b"")
    )
    va._run_ffmpeg(["ffmpeg", "-version"])  # should not raise


def test_output_paths_in_video_dir(tmp_path):
    audio_dir = tmp_path / "audio" / "week2_3" / "tutorial_units"
    audio_dir.mkdir(parents=True)
    video_dir = tmp_path / "video" / "week2_3"
    video_dir.mkdir(parents=True)

    # Verify _write_concat_script output is relative to video_dir, not audio_dir
    entries = [(video_dir / "slides" / "01_hook.png", 5.0)]
    script = video_dir / "unit_01.concat.txt"
    va._write_concat_script(entries, script)

    content = script.read_text()
    # No reference to audio dir in concat script
    assert str(audio_dir) not in content


def test_concat_unit_videos_re_encodes_audio(tmp_path):
    """_concat_unit_videos must NOT use bare -c copy — audio must be re-encoded."""
    import inspect

    from tutor.visual.video_assembler import _concat_unit_videos

    src = inspect.getsource(_concat_unit_videos)
    assert '"-c", "copy"' not in src, (
        "_concat_unit_videos must re-encode audio (use -c:v copy + -c:a aac), "
        "not bare -c copy, to fix timestamp discontinuities after concat"
    )
    assert '"-c:a", "aac"' in src


def test_concat_script_single_entry(tmp_path):
    entries = [(tmp_path / "only_slide.png", 4.0)]
    script = tmp_path / "single.concat.txt"
    va._write_concat_script(entries, script)

    content = script.read_text()
    lines = [ln for ln in content.strip().splitlines() if ln.startswith("file")]
    # Single entry repeated twice
    assert len(lines) == 2
    assert lines[0] == lines[1]
