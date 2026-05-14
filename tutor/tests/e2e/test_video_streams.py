"""Video stream verification: audio and video streams both present, durations non-zero."""

import json
import subprocess

import pytest


def _to_float(value, default: float = 0.0) -> float:
    """Return float(value) or default when value is non-numeric (e.g. 'N/A')."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value, default: int = 0) -> int:
    """Return int(value) or default when value is non-numeric (e.g. 'N/A')."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def ffprobe_streams(path):
    """Run ffprobe on path and return the list of stream dicts."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,duration,bit_rate",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        pytest.fail(f"ffprobe failed (rc={result.returncode}): {result.stderr.strip()}")
    return json.loads(result.stdout)["streams"]


def _get_mp4(pipeline_output):
    """Return the expected tutorial.mp4 path inside pipeline_output."""
    return pipeline_output / "tutorial.mp4"


def test_video_file_exists(pipeline_output):
    """Assert tutorial.mp4 exists and has non-zero size; skip if absent."""
    mp4 = _get_mp4(pipeline_output)
    if not mp4.exists():
        pytest.skip("tutorial.mp4 not present — video pipeline not run")
    assert mp4.stat().st_size > 0, "tutorial.mp4 is empty"


def test_video_stream_present(pipeline_output):
    """Assert tutorial.mp4 contains at least one video stream."""
    mp4 = _get_mp4(pipeline_output)
    if not mp4.exists():
        pytest.skip("tutorial.mp4 not present — video pipeline not run")
    streams = ffprobe_streams(mp4)
    codec_types = [s.get("codec_type") for s in streams]
    assert "video" in codec_types, f"No video stream found in tutorial.mp4; streams: {codec_types}"


def test_audio_stream_present(pipeline_output):
    """Assert tutorial.mp4 contains an audio stream — catches the silent-video bug."""
    mp4 = _get_mp4(pipeline_output)
    if not mp4.exists():
        pytest.skip("tutorial.mp4 not present — video pipeline not run")
    streams = ffprobe_streams(mp4)
    codec_types = [s.get("codec_type") for s in streams]
    assert "audio" in codec_types, (
        f"No audio stream found in tutorial.mp4 — this is the silent-video bug; "
        f"streams: {codec_types}"
    )


def test_audio_stream_duration_nonzero(pipeline_output):
    """Assert the audio stream duration is greater than zero."""
    mp4 = _get_mp4(pipeline_output)
    if not mp4.exists():
        pytest.skip("tutorial.mp4 not present — video pipeline not run")
    streams = ffprobe_streams(mp4)
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    assert audio_streams, "No audio stream found"
    duration = _to_float(audio_streams[0].get("duration"))
    assert duration > 0, f"Audio stream has zero duration: {duration}"


def test_audio_stream_not_muted(pipeline_output):
    """Assert audio stream bitrate is non-zero, ruling out a muted stream."""
    mp4 = _get_mp4(pipeline_output)
    if not mp4.exists():
        pytest.skip("tutorial.mp4 not present — video pipeline not run")
    streams = ffprobe_streams(mp4)
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    assert audio_streams, "No audio stream found"
    bit_rate = _to_int(audio_streams[0].get("bit_rate"))
    assert bit_rate > 0, f"Audio stream bitrate is zero — stream may be silent: {bit_rate}"
