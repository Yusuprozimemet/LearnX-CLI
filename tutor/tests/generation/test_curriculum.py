import json

import pytest

from tutor.generation.curriculum import plan
from tutor.models import Chunk, DocProfile


def _make_profile() -> DocProfile:
    return DocProfile(
        filepath="test.md",
        raw_bytes=10_000,
        estimated_tokens=5_000,
        strategy="B",
        section_count=5,
        has_code_blocks=True,
        language_hint="java",
    )


def _make_chunks() -> list[Chunk]:
    return [
        Chunk(
            chunk_id=f"s0{i}",
            breadcrumb=f"Section {i}",
            heading=f"Section {i}",
            level=2,
            token_count=500,
            text=f"Content about concept {i}. " * 50,
            has_code=True,
            summary=f"This section covers concept {i} with a practical example.",
        )
        for i in range(1, 5)
    ]


GOOD_RESPONSE = json.dumps(
    [
        {
            "concept": "Pass-by-Value",
            "source_sections": ["s01"],
            "complexity": 3,
            "key_facts": ["Java passes references by value"],
            "common_misconception": "Thinks Java passes objects by reference",
            "good_analogy": "Copying an address, not a house",
            "question_style": "predict",
            "memory_hook": "Copy the address, not the house",
            "prerequisite_concepts": [],
        },
        {
            "concept": "String Equality",
            "source_sections": ["s02"],
            "complexity": 2,
            "key_facts": ["Use .equals() not =="],
            "common_misconception": "Thinks == compares content",
            "good_analogy": "Two identical keys from different locksmiths",
            "question_style": "error-spot",
            "memory_hook": "Reference check, not content check",
            "prerequisite_concepts": [],
        },
    ]
)


def fake_llm(messages, call_type="dialogue"):
    return GOOD_RESPONSE


def test_plan_returns_teaching_units():
    from tutor.models import TeachingUnit

    units = plan(_make_chunks(), _make_profile(), 20, fake_llm)
    assert len(units) == 2
    assert all(isinstance(u, TeachingUnit) for u in units)


def test_plan_computes_word_budgets():
    units = plan(_make_chunks(), _make_profile(), 20, fake_llm)
    for u in units:
        assert u.word_budget > 0


def test_plan_raises_on_empty_response():
    from tutor.exceptions import LLMError

    def empty_llm(messages, call_type="dialogue"):
        return "[]"

    with pytest.raises(LLMError):
        plan(_make_chunks(), _make_profile(), 20, empty_llm)


def test_plan_raises_on_bad_json():
    from tutor.exceptions import LLMError

    def bad_llm(messages, call_type="dialogue"):
        return "not json at all"

    with pytest.raises(LLMError):
        plan(_make_chunks(), _make_profile(), 20, bad_llm)


def test_word_budget_proportional_to_complexity():
    units = plan(_make_chunks(), _make_profile(), 20, fake_llm)
    # Unit 0 has complexity 3, Unit 1 has complexity 2 → ratio should be 3:2 = 1.5
    ratio = units[0].word_budget / units[1].word_budget
    assert 1.4 <= ratio <= 1.6
