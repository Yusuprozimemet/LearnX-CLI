"""A/V sync: timing.json per-unit end_ms vs unit MP3 duration drift < 500ms."""

import json

import pytest
from pydub import AudioSegment

from tutor.constants import SILENCE_BREATH_MS, SILENCE_TURN_MS


def test_timing_units_nonempty(pipeline_output):
    """Assert timing.json contains at least one unit entry."""
    timing_path = pipeline_output / "tutorial.timing.json"
    timing = json.loads(timing_path.read_text(encoding="utf-8"))
    assert timing["units"], "timing.json 'units' dict is empty — no timing data captured"


def test_timing_end_matches_audio_duration(pipeline_output):
    """Assert per-unit last end_ms vs unit MP3 duration drift is under 500ms."""
    timing_path = pipeline_output / "tutorial.timing.json"
    timing = json.loads(timing_path.read_text(encoding="utf-8"))
    units_dir = pipeline_output / "tutorial_units"

    for unit_key, entries in timing["units"].items():
        if not entries:
            continue
        last_end_ms = entries[-1]["end_ms"]
        unit_num = int(unit_key)
        unit_mp3 = units_dir / f"unit_{unit_num:02d}.mp3"

        if not unit_mp3.exists():
            pytest.skip(f"Unit MP3 not found: {unit_mp3}")

        audio_duration_ms = len(AudioSegment.from_mp3(str(unit_mp3)))
        drift = abs(last_end_ms - audio_duration_ms)
        assert drift < 500, (
            f"Unit {unit_key}: timing end_ms={last_end_ms}ms vs "
            f"audio duration={audio_duration_ms}ms (drift={drift}ms, threshold=500ms)"
        )


def test_no_timing_gaps(pipeline_output):
    """Assert consecutive timing entries have only BREATH or TURN silence gaps."""
    timing_path = pipeline_output / "tutorial.timing.json"
    timing = json.loads(timing_path.read_text(encoding="utf-8"))

    for unit_key, entries in timing["units"].items():
        for i in range(1, len(entries)):
            prev_speaker = entries[i - 1]["speaker"]
            curr_speaker = entries[i]["speaker"]
            gap = entries[i]["start_ms"] - entries[i - 1]["end_ms"]
            expected = SILENCE_BREATH_MS if prev_speaker == curr_speaker else SILENCE_TURN_MS
            assert gap == expected, (
                f"Unit {unit_key}, entry {i}: gap={gap}ms, "
                f"expected {expected}ms ({prev_speaker}→{curr_speaker})"
            )
