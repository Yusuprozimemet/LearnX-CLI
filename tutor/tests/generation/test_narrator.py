"""Tests for tutor/generation/narrator.py."""

from unittest.mock import MagicMock, patch

from tutor.generation.narrator import (
    NARRATE_VERSION,
    _chunk_to_unit,
    _parse_narration,
    narrate_all,
)
from tutor.models import Chunk


def _make_chunk(
    chunk_id: str = "sec_001",
    heading: str = "What is Inheritance?",
    text: str = "Inheritance lets one class extend another.",
) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        breadcrumb=heading,
        heading=heading,
        level=2,
        token_count=len(text.split()),
        text=text,
        has_code=False,
    )


# ── _parse_narration ──────────────────────────────────────────────────────────


def test_parse_narration_extracts_alex_lines():
    raw = "ALEX: This section covers inheritance.\nALEX: Use extends to create a subclass."
    lines = _parse_narration(raw, unit_number=1)
    assert len(lines) == 2
    assert all(ln.speaker == "ALEX" for ln in lines)
    assert lines[0].text == "This section covers inheritance."


def test_parse_narration_skips_non_alex_lines():
    raw = "ALEX: Hello.\nSome random text.\nMAYA: Should be ignored.\nALEX: End."
    lines = _parse_narration(raw, unit_number=1)
    assert len(lines) == 2
    assert lines[1].text == "End."


def test_parse_narration_sets_unit_number():
    raw = "ALEX: Content here."
    lines = _parse_narration(raw, unit_number=3)
    assert lines[0].unit_number == 3


def test_parse_narration_empty_input_returns_empty():
    assert _parse_narration("", unit_number=1) == []


def test_parse_narration_handles_dash_separator():
    raw = "ALEX - This also works."
    lines = _parse_narration(raw, unit_number=1)
    assert len(lines) == 1
    assert lines[0].text == "This also works."


# ── _chunk_to_unit ────────────────────────────────────────────────────────────


def test_chunk_to_unit_concept_is_heading():
    chunk = _make_chunk(heading="The extends Keyword")
    unit = _chunk_to_unit(chunk, unit_index=2)
    assert unit.concept == "The extends Keyword"


def test_chunk_to_unit_source_sections_contains_chunk_id():
    chunk = _make_chunk(chunk_id="sec_003")
    unit = _chunk_to_unit(chunk, unit_index=3)
    assert "sec_003" in unit.source_sections


def test_chunk_to_unit_complexity_is_one():
    chunk = _make_chunk()
    unit = _chunk_to_unit(chunk, unit_index=1)
    assert unit.complexity == 1


def test_chunk_to_unit_word_budget_proportional_to_source():
    long_text = " ".join(["word"] * 200)
    chunk = _make_chunk(text=long_text)
    unit = _chunk_to_unit(chunk, unit_index=1)
    assert unit.word_budget >= 200


def test_chunk_to_unit_falls_back_to_section_number_when_no_heading():
    chunk = _make_chunk(heading="")
    unit = _chunk_to_unit(chunk, unit_index=5)
    assert "5" in unit.concept


# ── narrate_all ───────────────────────────────────────────────────────────────


def _fake_llm(response: str) -> MagicMock:
    mock = MagicMock(return_value=response)
    return mock


def test_narrate_all_returns_one_unit_per_chunk(tmp_path):
    chunks = [_make_chunk(chunk_id=f"sec_{i:03d}", heading=f"Section {i}") for i in range(3)]
    llm_fn = _fake_llm("ALEX: This section explains the concept.\nALEX: Here is a detail.")

    with patch("tutor.generation.narrator.SUMMARY_CACHE_DIR", str(tmp_path)):
        units, all_lines = narrate_all(chunks, "Inheritance", llm_fn, cache_dir=str(tmp_path))

    assert len(units) == 3
    assert len(all_lines) == 3


def test_narrate_all_units_only_have_alex_lines(tmp_path):
    chunks = [_make_chunk()]
    llm_fn = _fake_llm("ALEX: Only ALEX speaks.\nALEX: And again.")

    with patch("tutor.generation.narrator.SUMMARY_CACHE_DIR", str(tmp_path)):
        _, all_lines = narrate_all(chunks, "Doc", llm_fn, cache_dir=str(tmp_path))

    for lines in all_lines:
        assert all(ln.speaker == "ALEX" for ln in lines)


def test_narrate_all_uses_cache_on_second_call(tmp_path):
    chunks = [_make_chunk()]
    llm_fn = _fake_llm("ALEX: First call.")

    with patch("tutor.generation.narrator.SUMMARY_CACHE_DIR", str(tmp_path)):
        narrate_all(chunks, "Doc", llm_fn, cache_dir=str(tmp_path))
        narrate_all(chunks, "Doc", llm_fn, cache_dir=str(tmp_path))

    assert llm_fn.call_count == 1


def test_narrate_all_cache_files_use_narrate_suffix(tmp_path):
    chunks = [_make_chunk()]
    llm_fn = _fake_llm("ALEX: Cached content.")

    with patch("tutor.generation.narrator.SUMMARY_CACHE_DIR", str(tmp_path)):
        narrate_all(chunks, "Doc", llm_fn, cache_dir=str(tmp_path))

    cache_files = list(tmp_path.glob("*.narrate.json"))
    assert len(cache_files) == 1


def test_narrate_all_does_not_share_cache_with_dialogue(tmp_path):
    """Narrate cache keys must differ from dialogue cache keys for same chunk."""
    import hashlib

    chunk = _make_chunk()
    narrate_key = hashlib.md5((chunk.chunk_id + chunk.text + NARRATE_VERSION).encode()).hexdigest()

    # Simulate a dialogue cache file with the same chunk content
    from tutor.constants import PROMPT_VERSION

    dialogue_key = hashlib.md5(
        (chunk.heading + str(400) + "tutor-student" + "beginner" + PROMPT_VERSION).encode()
    ).hexdigest()

    assert narrate_key != dialogue_key
