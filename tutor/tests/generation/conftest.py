"""Shared fixtures and helpers for segment planner tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tutor.models import DialogueLine

N_LINES = 6


def _line(i: int, speaker: str = "ALEX", unit: int = 1) -> DialogueLine:
    return DialogueLine(speaker=speaker, text=f"Line {i}", unit_number=unit)


def _make_lines(n: int = N_LINES, unit: int = 1) -> list[DialogueLine]:
    speakers = ["ALEX", "MAYA", "ALEX", "MAYA", "ALEX", "ALEX"]
    return [_line(i, speakers[i % len(speakers)], unit) for i in range(n)]


def _make_unit_entry(
    unit_num: int = 1, concept: str = "Test Concept", n_lines: int = N_LINES
) -> dict:
    lines = [
        {"speaker": "ALEX" if i % 2 == 0 else "MAYA", "text": f"Line {i}", "unit_number": unit_num}
        for i in range(n_lines)
    ]
    return {
        "unit": unit_num,
        "concept": concept,
        "lines": lines,
        "source_sections": [],
        "complexity": 1,
        "word_budget": 200,
        "key_facts": [],
        "common_misconception": "",
        "good_analogy": "",
        "question_style": "",
        "memory_hook": "",
    }


def _units_json(tmp_path: Path, units: list[dict]) -> Path:
    p = tmp_path / "tutorial.units.json"
    p.write_text(json.dumps(units), encoding="utf-8")
    return p


def _valid_response(lines: list[DialogueLine]) -> str:
    n = len(lines)
    mid_end = max(1, n - 2)
    return json.dumps(
        [
            {
                "lines_start": 0,
                "lines_end": 0,
                "visual_type": "hook_question",
                "title": "Opening",
                "body": None,
                "code": None,
                "language": None,
                "mermaid": None,
                "left": None,
                "right": None,
                "rows": None,
            },
            {
                "lines_start": 1,
                "lines_end": mid_end,
                "visual_type": "key_insight",
                "title": "Key Point",
                "body": None,
                "code": None,
                "language": None,
                "mermaid": None,
                "left": None,
                "right": None,
                "rows": None,
            },
            {
                "lines_start": mid_end + 1,
                "lines_end": n - 1,
                "visual_type": "memory_hook",
                "title": "Remember",
                "body": None,
                "code": None,
                "language": None,
                "mermaid": None,
                "left": None,
                "right": None,
                "rows": None,
            },
        ]
    )


def _fake_llm(lines: list[DialogueLine]):
    def _llm(messages, call_type="segments"):
        return _valid_response(lines)

    return _llm


# ---------------------------------------------------------------------------
# pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def make_lines():
    return _make_lines


@pytest.fixture()
def make_unit_entry():
    return _make_unit_entry


@pytest.fixture()
def units_json_factory():
    return _units_json


@pytest.fixture()
def fake_llm_factory():
    return _fake_llm


@pytest.fixture()
def valid_response_factory():
    return _valid_response
