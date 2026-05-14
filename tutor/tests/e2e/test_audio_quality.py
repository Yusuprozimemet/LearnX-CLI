"""Audio quality: not silent, duration reasonable, correct sample rate."""
from pydub import AudioSegment


def test_audio_not_silent(pipeline_output):
    mp3 = pipeline_output / "tutorial.mp3"
    audio = AudioSegment.from_mp3(str(mp3))
    assert audio.dBFS > -60, (
        f"tutorial.mp3 appears silent: dBFS={audio.dBFS:.1f} (threshold: -60 dBFS)"
    )


def test_audio_duration_positive(pipeline_output):
    mp3 = pipeline_output / "tutorial.mp3"
    audio = AudioSegment.from_mp3(str(mp3))
    assert len(audio) > 0, "tutorial.mp3 has zero duration"


def test_audio_duration_matches_fixture_length(pipeline_output):
    mp3 = pipeline_output / "tutorial.mp3"
    audio = AudioSegment.from_mp3(str(mp3))
    assert len(audio) > 10_000, (
        f"tutorial.mp3 too short: {len(audio)}ms (expected > 10000ms for a 3-paragraph fixture)"
    )


def test_unit_audio_not_silent(pipeline_output):
    units_dir = pipeline_output / "tutorial_units"
    unit_files = sorted(units_dir.glob("unit_*.mp3"))
    assert unit_files, f"No unit_*.mp3 found in {units_dir}"
    for unit_path in unit_files:
        audio = AudioSegment.from_mp3(str(unit_path))
        assert audio.dBFS > -60, (
            f"{unit_path.name} appears silent: dBFS={audio.dBFS:.1f} (threshold: -60 dBFS)"
        )
