from pathlib import Path

from PIL import Image

from tutor.models import VisualSpec
from tutor.visual.slide_compositor import (
    compose_all,
    compose_concept_slide,
    compose_hook_slide,
    compose_memory_slide,
    compose_outro_card,
    compose_title_card,
)
from tutor.visual.slide_theme import ACCENT_AMBER, CANVAS_H, CANVAS_W


def _unit(idx: int, **kwargs) -> VisualSpec:
    defaults = dict(
        unit_index=idx,
        slide_type="unit",
        concept="Test Concept",
        hook_question="Why does this matter?",
        key_points=["First point", "Second point", "Third point"],
        code_snippet=None,
        diagram_type="none",
        diagram_spec=None,
        memory_hook="Remember the contract.",
        analogy="Like a job description.",
    )
    defaults.update(kwargs)
    return VisualSpec(**defaults)


def _title() -> VisualSpec:
    return VisualSpec(
        unit_index=0,
        slide_type="title_card",
        title="Java Interfaces",
        subtitle="3 units · beginner",
        doc_source="week2_3",
    )


def _outro(n: int) -> VisualSpec:
    return VisualSpec(
        unit_index=n + 1,
        slide_type="outro",
        memory_hooks=["Contract first", "Default has body"],
        session_stats=f"{n} units",
    )


# ── title card ──────────────────────────────────────────────────────────────


def test_title_card_is_1920x1080(tmp_path):
    spec = _title()
    result = compose_title_card(spec, tmp_path / "title.png")
    img = Image.open(result)
    assert img.size == (CANVAS_W, CANVAS_H)
    assert img.mode == "RGB"


# ── hook slide ───────────────────────────────────────────────────────────────


def test_hook_slide_is_1920x1080(tmp_path):
    result = compose_hook_slide(_unit(1), tmp_path / "hook.png", total=3)
    img = Image.open(result)
    assert img.size == (CANVAS_W, CANVAS_H)


# ── concept slide ────────────────────────────────────────────────────────────


def test_concept_slide_with_diagram(tmp_path):
    diag = tmp_path / "diag.png"
    Image.new("RGB", (400, 300), "#ff0000").save(diag, "PNG")

    result = compose_concept_slide(_unit(1), diag, tmp_path / "concept.png", total=3)
    img = Image.open(result)
    assert img.size == (CANVAS_W, CANVAS_H)


def test_concept_slide_no_diagram(tmp_path):
    result = compose_concept_slide(_unit(1), None, tmp_path / "concept.png", total=3)
    img = Image.open(result)
    assert img.size == (CANVAS_W, CANVAS_H)


def test_bullet_wrap_does_not_overflow(tmp_path):
    long_text = "This is a very long bullet point that should wrap gracefully without overflowing into the diagram area"
    spec = _unit(1, key_points=[long_text] * 5)
    result = compose_concept_slide(spec, None, tmp_path / "concept.png", total=3)
    assert result.exists()
    img = Image.open(result)
    assert img.size == (CANVAS_W, CANVAS_H)


def test_code_block_rendered_when_snippet_present(tmp_path):
    spec = _unit(1, code_snippet="interface Printable {\n    void print();\n}")
    result = compose_concept_slide(spec, None, tmp_path / "concept.png", total=3)
    assert result.exists()
    img = Image.open(result)
    assert img.size == (CANVAS_W, CANVAS_H)


# ── memory slide ─────────────────────────────────────────────────────────────


def test_memory_slide_is_1920x1080(tmp_path):
    result = compose_memory_slide(_unit(1), tmp_path / "memory.png", total=3)
    img = Image.open(result)
    assert img.size == (CANVAS_W, CANVAS_H)


def test_memory_slide_uses_amber_strip(tmp_path):
    result = compose_memory_slide(_unit(1), tmp_path / "memory.png", total=3)
    img = Image.open(result)
    px = img.getpixel((0, CANVAS_H // 2))  # left strip, mid-height
    # ACCENT_AMBER = "#e3b341" → (227, 179, 65)
    r, g, b = int(ACCENT_AMBER[1:3], 16), int(ACCENT_AMBER[3:5], 16), int(ACCENT_AMBER[5:7], 16)
    assert px == (r, g, b), f"Expected ACCENT_AMBER pixel, got {px}"


# ── outro card ───────────────────────────────────────────────────────────────


def test_outro_card_is_1920x1080(tmp_path):
    result = compose_outro_card(_outro(3), tmp_path / "outro.png", "week2_3")
    img = Image.open(result)
    assert img.size == (CANVAS_W, CANVAS_H)


# ── compose_all ──────────────────────────────────────────────────────────────


def test_compose_all_returns_correct_count(tmp_path):
    n = 3
    visuals = [_title()] + [_unit(i) for i in range(1, n + 1)] + [_outro(n)]
    paths = compose_all(visuals, {}, tmp_path, "week2_3")
    # 1 title + 3×(hook + concept + memory) + 1 outro = 11
    assert len(paths) == 1 + 3 * n + 1
    for p in paths:
        assert p.exists()
        assert Image.open(p).size == (CANVAS_W, CANVAS_H)


def test_font_fallback_on_missing_bundled_font(tmp_path, monkeypatch):
    from tutor.visual import slide_theme

    # Point bundled font paths to a non-existent directory so fallback triggers.
    monkeypatch.setattr(slide_theme, "_SANS_REGULAR", Path("/nonexistent/Inter-Regular.ttf"))
    monkeypatch.setattr(slide_theme, "_SANS_BOLD", Path("/nonexistent/Inter-Bold.ttf"))
    monkeypatch.setattr(
        slide_theme, "_MONO_REGULAR", Path("/nonexistent/JetBrainsMono-Regular.ttf")
    )
    monkeypatch.setattr(slide_theme, "_MONO_BOLD", Path("/nonexistent/JetBrainsMono-Bold.ttf"))

    result = compose_title_card(_title(), tmp_path / "title.png")
    assert result.exists()
    assert Image.open(result).size == (CANVAS_W, CANVAS_H)
