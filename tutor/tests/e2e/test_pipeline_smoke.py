"""Smoke test: full pipeline runs without crash and produces expected output files."""

import json


def test_pipeline_exits_zero(pipeline_output):
    """Assert the pipeline ran successfully and created the output directory."""
    assert pipeline_output.exists(), f"Output directory not created: {pipeline_output}"


def test_mp3_exists_and_nonempty(pipeline_output):
    """Assert tutorial.mp3 exists and has non-zero size."""
    mp3 = pipeline_output / "tutorial.mp3"
    assert mp3.exists(), f"tutorial.mp3 not found in {pipeline_output}"
    assert mp3.stat().st_size > 0, "tutorial.mp3 is empty"


def test_timing_json_exists(pipeline_output):
    """Assert tutorial.timing.json was written to the output directory."""
    timing = pipeline_output / "tutorial.timing.json"
    assert timing.exists(), f"tutorial.timing.json not found in {pipeline_output}"


def test_timing_json_is_valid(pipeline_output):
    """Assert tutorial.timing.json is valid JSON with 'version' and 'units' keys."""
    timing_path = pipeline_output / "tutorial.timing.json"
    data = json.loads(timing_path.read_text(encoding="utf-8"))
    assert "version" in data, "timing.json missing 'version' key"
    assert "units" in data, "timing.json missing 'units' key"


def test_unit_mp3s_exist(pipeline_output):
    """Assert at least one unit_*.mp3 file exists in tutorial_units/."""
    units_dir = pipeline_output / "tutorial_units"
    assert units_dir.exists(), f"tutorial_units/ directory not found in {pipeline_output}"
    unit_files = list(units_dir.glob("unit_*.mp3"))
    assert len(unit_files) >= 1, f"No unit_*.mp3 files found in {units_dir}"
