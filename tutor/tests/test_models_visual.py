"""
Tests for PR additions in tutor/models.py (VisualSpec) and tutor/exceptions.py (VideoError).
"""
import dataclasses

import pytest

from tutor.exceptions import (
    ConfigError,
    LLMError,
    TutorError,
    VideoError,
)
from tutor.models import VisualSpec


# ── VideoError ────────────────────────────────────────────────────────────────

def test_video_error_is_tutor_error():
    assert issubclass(VideoError, TutorError)


def test_video_error_can_be_raised_and_caught():
    with pytest.raises(VideoError):
        raise VideoError("pipeline failed")


def test_video_error_caught_as_tutor_error():
    with pytest.raises(TutorError):
        raise VideoError("wrapped")


def test_video_error_message_preserved():
    try:
        raise VideoError("step 3 failed")
    except VideoError as exc:
        assert "step 3 failed" in str(exc)


def test_video_error_not_same_as_config_error():
    assert VideoError is not ConfigError
    assert not issubclass(VideoError, ConfigError)


def test_video_error_not_same_as_llm_error():
    assert VideoError is not LLMError
    assert not issubclass(VideoError, LLMError)


# ── VisualSpec — defaults ─────────────────────────────────────────────────────

def test_visual_spec_minimal_construction():
    spec = VisualSpec(unit_index=1, slide_type="unit")
    assert spec.unit_index == 1
    assert spec.slide_type == "unit"


def test_visual_spec_default_diagram_type_is_none():
    spec = VisualSpec(unit_index=1, slide_type="unit")
    assert spec.diagram_type == "none"


def test_visual_spec_default_diagram_spec_is_none():
    spec = VisualSpec(unit_index=1, slide_type="unit")
    assert spec.diagram_spec is None


def test_visual_spec_default_key_points_is_empty_list():
    spec = VisualSpec(unit_index=1, slide_type="unit")
    assert spec.key_points == []
    assert isinstance(spec.key_points, list)


def test_visual_spec_default_memory_hooks_is_empty_list():
    spec = VisualSpec(unit_index=0, slide_type="outro")
    assert spec.memory_hooks == []
    assert isinstance(spec.memory_hooks, list)


def test_visual_spec_default_string_fields_are_empty():
    spec = VisualSpec(unit_index=1, slide_type="unit")
    assert spec.concept == ""
    assert spec.hook_question == ""
    assert spec.memory_hook == ""
    assert spec.analogy == ""
    assert spec.code_snippet is None
    assert spec.title == ""
    assert spec.subtitle == ""
    assert spec.doc_source == ""
    assert spec.session_stats == ""


def test_visual_spec_title_card_fields():
    spec = VisualSpec(
        unit_index=0,
        slide_type="title_card",
        title="Java Basics",
        subtitle="5 units · beginner",
        doc_source="week1_1",
    )
    assert spec.title == "Java Basics"
    assert spec.subtitle == "5 units · beginner"
    assert spec.doc_source == "week1_1"


def test_visual_spec_unit_fields():
    spec = VisualSpec(
        unit_index=3,
        slide_type="unit",
        concept="Pass-by-Value",
        hook_question="What really happens?",
        key_points=["fact1", "fact2"],
        code_snippet="int x = 5;",
        diagram_type="flowchart",
        diagram_spec="digraph G { A -> B }",
        memory_hook="Copy the address",
        analogy="Like copying an address",
    )
    assert spec.concept == "Pass-by-Value"
    assert spec.hook_question == "What really happens?"
    assert spec.key_points == ["fact1", "fact2"]
    assert spec.code_snippet == "int x = 5;"
    assert spec.diagram_type == "flowchart"
    assert spec.diagram_spec == "digraph G { A -> B }"
    assert spec.memory_hook == "Copy the address"
    assert spec.analogy == "Like copying an address"


def test_visual_spec_outro_fields():
    spec = VisualSpec(
        unit_index=5,
        slide_type="outro",
        memory_hooks=["Hook A", "Hook B"],
        session_stats="4 units",
    )
    assert spec.memory_hooks == ["Hook A", "Hook B"]
    assert spec.session_stats == "4 units"


def test_visual_spec_is_dataclass():
    assert dataclasses.is_dataclass(VisualSpec)


def test_visual_spec_mutable_list_fields_independent():
    """Each VisualSpec should have its own list instances, not share them."""
    a = VisualSpec(unit_index=1, slide_type="unit")
    b = VisualSpec(unit_index=2, slide_type="unit")
    a.key_points.append("fact")
    assert b.key_points == [], "Shared mutable default detected"


def test_visual_spec_asdict_roundtrip():
    """dataclasses.asdict / reconstruct should preserve all fields."""
    original = VisualSpec(
        unit_index=2,
        slide_type="unit",
        concept="Concept",
        key_points=["a", "b"],
        diagram_type="flowchart",
        diagram_spec="digraph G { A -> B }",
        memory_hook="remember",
        analogy="like something",
    )
    d = dataclasses.asdict(original)
    reconstructed = VisualSpec(**d)
    assert reconstructed == original


def test_visual_spec_code_comparison_diagram_spec():
    """diagram_spec can be a dict for code_comparison type."""
    spec = VisualSpec(
        unit_index=1,
        slide_type="unit",
        diagram_type="code_comparison",
        diagram_spec={"wrong": "a == b", "right": "a.equals(b)",
                      "label_wrong": "ref check", "label_right": "content check"},
    )
    assert isinstance(spec.diagram_spec, dict)
    assert "wrong" in spec.diagram_spec