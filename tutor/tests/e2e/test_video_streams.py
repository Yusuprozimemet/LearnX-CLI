"""Video stream verification: audio and video streams both present, durations non-zero."""
import json
import subprocess

import pytest


def ffprobe_streams(path):
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=codec_type,duration,bit_rate",
            "-of", "json", str(path),
        ],
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)["streams"]


def _get_mp4(pipeline_output):
    return pipeline_output / "tutorial.mp4"


def test_video_file_exists(pipeline_output):
    mp4 = _get_mp4(pipeline_output)
    if not mp4.exists():
        pytest.skip("tutorial.mp4 not present — video pipeline not run")
    assert mp4.stat().st_size > 0, "tutorial.mp4 is empty"


def test_video_stream_present(pipeline_output):
    mp4 = _get_mp4(pipeline_output)
    if not mp4.exists():
        pytest.skip("tutorial.mp4 not present — video pipeline not run")
    streams = ffprobe_streams(mp4)
    codec_types = [s.get("codec_type") for s in streams]
    assert "video" in codec_types, f"No video stream found in tutorial.mp4; streams: {codec_types}"


def test_audio_stream_present(pipeline_output):
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
    mp4 = _get_mp4(pipeline_output)
    if not mp4.exists():
        pytest.skip("tutorial.mp4 not present — video pipeline not run")
    streams = ffprobe_streams(mp4)
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    assert audio_streams, "No audio stream found"
    duration = float(audio_streams[0].get("duration", 0))
    assert duration > 0, f"Audio stream has zero duration: {duration}"


def test_audio_stream_not_muted(pipeline_output):
    mp4 = _get_mp4(pipeline_output)
    if not mp4.exists():
        pytest.skip("tutorial.mp4 not present — video pipeline not run")
    streams = ffprobe_streams(mp4)
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    assert audio_streams, "No audio stream found"
    bit_rate = int(audio_streams[0].get("bit_rate", 0))
    assert bit_rate > 0, f"Audio stream bitrate is zero — stream may be silent: {bit_rate}"
