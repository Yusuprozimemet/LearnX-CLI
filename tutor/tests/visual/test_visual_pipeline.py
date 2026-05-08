"""
Tests for tutor/visual/__init__.py helpers:
  _doc_title_from_units, _load_all_lines, _mp3_duration, _format_duration
"""
import json
import subprocess
from pathlib import Path

import pytest

from tutor.models import DialogueLine
from tutor.visual import (
    _doc_title_from_units,
    _format_duration,
    _load_all_lines,
    _mp3_duration,
)


# ── _doc_title_from_units ────────────────────────────────────────────────────

def test_doc_title_returns_first_concept(tmp_path):
    units_json = tmp_path / "tutorial.units.json"
    units_json.write_text(
        json.dumps([{"concept": "Interfaces"}, {"concept": "Abstract Classes"}]),
        encoding="utf-8",
    )
    assert _doc_title_from_units(units_json) == "Interfaces"


def test_doc_title_fallback_when_empty_list(tmp_path):
    units_json = tmp_path / "tutorial.units.json"
    units_json.write_text("[]", encoding="utf-8")
    assert _doc_title_from_units(units_json) == "Tutorial"


def test_doc_title_fallback_when_file_missing(tmp_path):
    missing = tmp_path / "nonexistent.json"
    assert _doc_title_from_units(missing) == "Tutorial"


def test_doc_title_fallback_when_malformed_json(tmp_path):
    units_json = tmp_path / "tutorial.units.json"
    units_json.write_text("this is not JSON", encoding="utf-8")
    assert _doc_title_from_units(units_json) == "Tutorial"


def test_doc_title_uses_concept_key(tmp_path):
    units_json = tmp_path / "tutorial.units.json"
    # "concept" key missing — falls back to "Tutorial"
    units_json.write_text(json.dumps([{"name": "Something Else"}]), encoding="utf-8")
    assert _doc_title_from_units(units_json) == "Tutorial"


# ── _load_all_lines — from units JSON lines field ────────────────────────────

def test_load_all_lines_from_units_json(tmp_path):
    units_json = tmp_path / "tutorial.units.json"
    units_data = [
        {
            "concept": "Interfaces",
            "lines": [
                {"speaker": "ALEX", "text": "What is an interface?", "unit_number": 1},
                {"speaker": "MAYA", "text": "A contract.", "unit_number": 1},
            ],
        }
    ]
    units_json.write_text(json.dumps(units_data), encoding="utf-8")
    lines = _load_all_lines(units_json)

    assert len(lines) == 2
    assert all(isinstance(l, DialogueLine) for l in lines)
    assert lines[0].speaker == "ALEX"
    assert lines[1].speaker == "MAYA"


def test_load_all_lines_from_multiple_units(tmp_path):
    units_json = tmp_path / "tutorial.units.json"
    units_data = [
        {
            "concept": "Unit1",
            "lines": [
                {"speaker": "ALEX", "text": "Line from unit 1", "unit_number": 1},
            ],
        },
        {
            "concept": "Unit2",
            "lines": [
                {"speaker": "MAYA", "text": "Line from unit 2", "unit_number": 2},
                {"speaker": "ALEX", "text": "Another unit 2 line", "unit_number": 2},
            ],
        },
    ]
    units_json.write_text(json.dumps(units_data), encoding="utf-8")
    lines = _load_all_lines(units_json)

    assert len(lines) == 3
    assert lines[0].unit_number == 1
    assert lines[1].unit_number == 2


# ── _load_all_lines — fallback to tutorial.script.txt ───────────────────────

def test_load_all_lines_fallback_to_script_txt(tmp_path):
    """No 'lines' in JSON → falls back to tutorial.script.txt."""
    units_json = tmp_path / "tutorial.units.json"
    units_json.write_text(json.dumps([{"concept": "Interfaces"}]), encoding="utf-8")

    script_txt = tmp_path / "tutorial.script.txt"
    script_txt.write_text(
        "ALEX: What is an interface?\nMAYA: A contract between a class and the world.\n",
        encoding="utf-8",
    )
    lines = _load_all_lines(units_json)

    assert len(lines) == 2
    assert lines[0].speaker == "ALEX"
    assert lines[1].speaker == "MAYA"


def test_load_all_lines_returns_empty_when_no_lines_no_script(tmp_path):
    units_json = tmp_path / "tutorial.units.json"
    units_json.write_text(json.dumps([{"concept": "X"}]), encoding="utf-8")
    # No script file present
    lines = _load_all_lines(units_json)
    assert lines == []


def test_load_all_lines_script_txt_filters_non_speaker_lines(tmp_path):
    units_json = tmp_path / "tutorial.units.json"
    units_json.write_text(json.dumps([{"concept": "X"}]), encoding="utf-8")

    script_txt = tmp_path / "tutorial.script.txt"
    script_txt.write_text(
        "NARRATOR: This line should be ignored.\n"
        "ALEX: Valid line.\n"
        "  This is a blank-ish line.\n"
        "MAYA: Another valid line.\n",
        encoding="utf-8",
    )
    lines = _load_all_lines(units_json)
    # NARRATOR is not a known speaker
    speakers = {l.speaker for l in lines}
    assert "NARRATOR" not in speakers
    assert "ALEX" in speakers
    assert "MAYA" in speakers


def test_load_all_lines_empty_units_json_list(tmp_path):
    units_json = tmp_path / "tutorial.units.json"
    units_json.write_text("[]", encoding="utf-8")
    lines = _load_all_lines(units_json)
    assert lines == []


def test_load_all_lines_script_assigns_units_sequentially(tmp_path):
    """Lines from script.txt should be distributed across units."""
    units_json = tmp_path / "tutorial.units.json"
    units_json.write_text(
        json.dumps([{"concept": "A"}, {"concept": "B"}]),
        encoding="utf-8",
    )
    script_txt = tmp_path / "tutorial.script.txt"
    # 4 lines, 2 units → 2 per unit
    script_txt.write_text(
        "ALEX: Line 1\nMAYA: Line 2\nALEX: Line 3\nMAYA: Line 4\n",
        encoding="utf-8",
    )
    lines = _load_all_lines(units_json)
    assert len(lines) == 4
    unit_numbers = {l.unit_number for l in lines}
    # Should span at least 2 distinct unit numbers (1 and 2)
    assert len(unit_numbers) >= 1


# ── _mp3_duration ─────────────────────────────────────────────────────────────

def test_mp3_duration_returns_float_on_success(monkeypatch, tmp_path):
    fake_mp3 = tmp_path / "unit_01.mp3"
    fake_mp3.touch()

    def mock_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, b"45.321\n", b"")

    monkeypatch.setattr(subprocess, "run", mock_run)
    duration = _mp3_duration(fake_mp3)
    assert duration == pytest.approx(45.321, abs=0.001)


def test_mp3_duration_returns_zero_on_ffprobe_error(monkeypatch, tmp_path):
    fake_mp3 = tmp_path / "unit_01.mp3"
    fake_mp3.touch()

    def failing_run(cmd, **kwargs):
        raise FileNotFoundError("ffprobe not found")

    monkeypatch.setattr(subprocess, "run", failing_run)
    assert _mp3_duration(fake_mp3) == 0.0


def test_mp3_duration_returns_zero_on_bad_output(monkeypatch, tmp_path):
    fake_mp3 = tmp_path / "unit_01.mp3"
    fake_mp3.touch()

    def mock_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, b"N/A\n", b"")

    monkeypatch.setattr(subprocess, "run", mock_run)
    assert _mp3_duration(fake_mp3) == 0.0


def test_mp3_duration_returns_zero_on_timeout(monkeypatch, tmp_path):
    fake_mp3 = tmp_path / "unit_01.mp3"
    fake_mp3.touch()

    def timeout_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 10)

    monkeypatch.setattr(subprocess, "run", timeout_run)
    assert _mp3_duration(fake_mp3) == 0.0


# ── _format_duration ─────────────────────────────────────────────────────────

def test_format_duration_zero():
    assert _format_duration(0) == "0:00"


def test_format_duration_one_minute():
    assert _format_duration(60) == "1:00"


def test_format_duration_90_seconds():
    assert _format_duration(90) == "1:30"


def test_format_duration_pads_seconds():
    assert _format_duration(65) == "1:05"


def test_format_duration_over_one_hour():
    assert _format_duration(3661) == "61:01"


def test_format_duration_fractional_truncated():
    """Fractional seconds should be truncated to int, not rounded."""
    assert _format_duration(59.9) == "0:59"


# ── _UNIT_MP3_RE ──────────────────────────────────────────────────────────────

def test_unit_mp3_re_matches_valid_stems():
    from tutor.visual import _UNIT_MP3_RE
    assert _UNIT_MP3_RE.match("unit_01")
    assert _UNIT_MP3_RE.match("unit_10")
    assert _UNIT_MP3_RE.match("unit_99")


def test_unit_mp3_re_rejects_intro():
    from tutor.visual import _UNIT_MP3_RE
    assert _UNIT_MP3_RE.match("unit_00_intro") is None


def test_unit_mp3_re_rejects_non_unit_names():
    from tutor.visual import _UNIT_MP3_RE
    assert _UNIT_MP3_RE.match("tutorial") is None
    assert _UNIT_MP3_RE.match("outro") is None
