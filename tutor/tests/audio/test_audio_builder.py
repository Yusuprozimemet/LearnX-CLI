import json
from pathlib import Path
from unittest.mock import patch

from pydub import AudioSegment

from tutor.audio.audio_builder import _assemble
from tutor.constants import SILENCE_BREATH_MS, SILENCE_TURN_MS
from tutor.models import DialogueLine, RenderedSegment

# ── helpers ───────────────────────────────────────────────────────────────────

CLIP_MS = 1000  # fake MP3 duration returned by the mock


def _line(unit: int, speaker: str, text: str = "test line") -> DialogueLine:
    return DialogueLine(speaker=speaker, text=text, unit_number=unit)


def _seg(line: DialogueLine) -> RenderedSegment:
    return RenderedSegment(line=line, audio_path="dummy.mp3", duration_ms=CLIP_MS)


def _run_assemble(tmp_path: Path, segments: list[RenderedSegment]) -> dict:
    """Run _assemble() with mocked I/O; return parsed timing JSON."""
    out_path = tmp_path / "tutorial.mp3"
    units_dir = tmp_path / "units"
    units_dir.mkdir()

    with (
        patch(
            "tutor.audio.audio_builder.AudioSegment.from_mp3",
            return_value=AudioSegment.silent(duration=CLIP_MS),
        ),
        patch.object(AudioSegment, "export"),
    ):
        _assemble(segments, str(out_path), str(units_dir))

    return json.loads((tmp_path / "tutorial.timing.json").read_text())


# ── tests ─────────────────────────────────────────────────────────────────────


def test_timing_file_written_after_build(tmp_path):
    segs = [_seg(_line(1, "ALEX")), _seg(_line(1, "MAYA"))]
    _run_assemble(tmp_path, segs)
    assert (tmp_path / "tutorial.timing.json").exists()


def test_timing_version_field_is_1(tmp_path):
    segs = [_seg(_line(1, "ALEX")), _seg(_line(1, "MAYA"))]
    data = _run_assemble(tmp_path, segs)
    assert data["version"] == 1


def test_timing_keys_are_string_integers(tmp_path):
    segs = [_seg(_line(1, "ALEX")), _seg(_line(2, "ALEX"))]
    data = _run_assemble(tmp_path, segs)
    keys = set(data["units"].keys())
    assert "1" in keys
    assert "2" in keys
    assert not any("unit_" in k for k in keys)


def test_timing_keys_match_teaching_units(tmp_path):
    segs = [
        _seg(_line(0, "ALEX")),  # intro — excluded
        _seg(_line(1, "ALEX")),
        _seg(_line(1, "MAYA")),
        _seg(_line(2, "ALEX")),
        _seg(_line(-1, "ALEX")),  # outro — excluded
    ]
    data = _run_assemble(tmp_path, segs)
    units = data["units"]
    assert "1" in units
    assert "2" in units
    assert "0" not in units
    assert "-1" not in units


def test_timing_offsets_no_gaps_no_overlaps(tmp_path):
    segs = [
        _seg(_line(1, "ALEX", "First line")),
        _seg(_line(1, "MAYA", "Second line")),
        _seg(_line(1, "ALEX", "Third line")),
    ]
    data = _run_assemble(tmp_path, segs)
    entries = data["units"]["1"]
    for i in range(len(entries) - 1):
        cur, nxt = entries[i], entries[i + 1]
        gap = SILENCE_BREATH_MS if cur["speaker"] == nxt["speaker"] else SILENCE_TURN_MS
        assert nxt["start_ms"] == cur["end_ms"] + gap


def test_timing_duration_matches_pydub_len(tmp_path):
    segs = [_seg(_line(1, "ALEX")), _seg(_line(1, "MAYA"))]
    data = _run_assemble(tmp_path, segs)
    for entry in data["units"]["1"]:
        assert entry["end_ms"] - entry["start_ms"] == CLIP_MS


def test_intro_and_outro_excluded_from_timing(tmp_path):
    segs = [_seg(_line(0, "ALEX")), _seg(_line(-1, "ALEX"))]
    data = _run_assemble(tmp_path, segs)
    assert data["units"] == {}
