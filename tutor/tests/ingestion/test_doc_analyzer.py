import pytest

from tutor.exceptions import IngestionError
from tutor.ingestion.doc_analyzer import analyze


def test_small_doc_strategy_a(tmp_path):
    doc = tmp_path / "small.md"
    doc.write_text("# Title\n\nShort content. " * 20)
    profile = analyze(str(doc))
    assert profile.strategy == "A"


def test_medium_doc_strategy_b(tmp_path):
    doc = tmp_path / "medium.md"
    doc.write_text("# Title\n\nContent word. " * 8_000)
    profile = analyze(str(doc))
    assert profile.strategy == "B"


def test_large_doc_strategy_c(tmp_path):
    doc = tmp_path / "large.md"
    doc.write_text("# Title\n\nContent word. " * 50_000)
    profile = analyze(str(doc))
    assert profile.strategy == "C"


def test_java_language_hint(tmp_path):
    doc = tmp_path / "java.md"
    doc.write_text("# Java\n\n```java\nint x = 5;\n```\n")
    profile = analyze(str(doc))
    assert profile.language_hint == "java"


def test_has_code_blocks_detection(tmp_path):
    doc = tmp_path / "code.md"
    doc.write_text("# Title\n\n```python\nprint('hi')\n```\n")
    profile = analyze(str(doc))
    assert profile.has_code_blocks is True


def test_no_code_blocks(tmp_path):
    doc = tmp_path / "nocode.md"
    doc.write_text("# Title\n\nJust plain text, no code blocks here.")
    profile = analyze(str(doc))
    assert profile.has_code_blocks is False


def test_nonexistent_file_raises():
    with pytest.raises(IngestionError):
        analyze("/nonexistent/path/file.md")
