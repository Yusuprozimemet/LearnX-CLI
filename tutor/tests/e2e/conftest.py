"""
Shared fixtures for E2E smoke tests.

The pipeline_output fixture runs the full LearnX pipeline once per test session,
with the LLM mocked so no API key is needed. TTS (edge-tts) runs for real.
All E2E test modules depend on this fixture.
"""
import argparse
import json
import os
import pathlib
import tempfile
from unittest.mock import patch

import pytest

FIXTURE_DOC = pathlib.Path("tutor/tests/e2e/fixtures/sample.md")
OUTPUT_DIR = pathlib.Path(tempfile.gettempdir()) / "learnx_e2e_smoke"

CURRICULUM_RESPONSE = json.dumps([
    {
        "concept": "What is a Variable?",
        "complexity": 1,
        "source_sections": ["s01"],
        "key_facts": [
            "A variable is a named container for a value",
            "Variables have a name and hold a value",
            "Variables can store numbers, text, or lists",
        ],
        "common_misconception": "Variables and constants are the same thing",
        "good_analogy": "A labeled box in a warehouse",
        "question_style": "recall",
        "memory_hook": "Variable equals labeled box",
        "word_budget": 200,
        "prerequisite_concepts": [],
        "js_contrast": "",
        "production_relevance": "",
    }
])

DIALOGUE_RESPONSE = "\n".join([
    "ALEX: Welcome to today's lesson on variables in programming.",
    "MAYA: What exactly is a variable?",
    "ALEX: Think of a variable as a labeled box that stores a value you can retrieve later.",
    "MAYA: Like how I would label a container in my kitchen?",
    "ALEX: Exactly. In Python you write age equals 25 to create a variable called age.",
    "MAYA: And then I can use the name age later to get 25 back?",
    "ALEX: That is right. Variables make programs readable and flexible.",
    "MAYA: What types of values can a variable hold?",
    "ALEX: Numbers, text, lists, and almost anything else your program needs.",
    "MAYA: Great, now variables make much more sense to me.",
])

SUMMARIZE_RESPONSE = (
    "A variable is a named container that holds a value in a computer program. "
    "Variables can hold different types of data including numbers, text, and lists."
)


def _mock_llm(messages, call_type="dialogue", **kwargs):  # noqa: ARG001
    """Return fixed LLM responses keyed on call_type, bypassing the real API."""
    if call_type == "summarize":
        return SUMMARIZE_RESPONSE
    if call_type == "curriculum":
        return CURRICULUM_RESPONSE
    return DIALOGUE_RESPONSE


@pytest.fixture(scope="session")
def pipeline_output():
    """Run the full pipeline once for the entire E2E test session.

    LLM responses are mocked; TTS (edge-tts) runs for real and requires
    an internet connection. Output files are written to OUTPUT_DIR.
    """
    from tutor.tutor import cmd_generate

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    args = argparse.Namespace(
        input=str(FIXTURE_DOC),
        output=str(OUTPUT_DIR / "tutorial.mp3"),
        provider="groq",
        duration=5,
        fmt="tutor-student",
        difficulty="beginner",
        units=1,
        subject="general",
        topic=None,
        play=False,
        script_only=False,
        dry_run=False,
        inspect=False,
        show_summaries=False,
        no_cache=False,
        verbose=False,
        debug=False,
        explain=False,
        conversation=False,
    )

    with patch("tutor.infra.llm.chat", side_effect=_mock_llm), \
         patch.dict(os.environ, {"GROQ_API_KEY": "test-key-not-used"}):
        cmd_generate(args)

    return OUTPUT_DIR
