import subprocess
from pathlib import Path

import pytest
from PIL import Image

import tutor.visual.diagram_renderer as dr
from tutor.models import VisualSpec

# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_graphviz_state():
    """Reset module-level graphviz probe cache between tests."""
    dr._graphviz_ready = None
    yield
    dr._graphviz_ready = None


def _make_spec(**kwargs) -> VisualSpec:
    defaults = dict(
        unit_index=1,
        slide_type="unit",
        concept="Test Concept",
        diagram_type="none",
        diagram_spec=None,
        analogy="An interface is like a job description.",
        memory_hook="Interfaces = contract",
    )
    defaults.update(kwargs)
    return VisualSpec(**defaults)


def _fake_run_ok(output_path: Path):
    """Return a fake subprocess.run that creates a black PNG at output_path."""

    def _run(cmd, **kwargs):
        # Find the -o<path> argument and create a minimal PNG there.
        for arg in cmd:
            s = str(arg)
            if s.startswith("-o"):
                Image.new("RGB", (800, 500), "#0d1117").save(s[2:], "PNG")
                break
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    return _run


# ── _apply_dark_theme ───────────────────────────────────────────────────────


def test_dark_theme_injected_when_bgcolor_missing():
    dot = "digraph G { A -> B }"
    result = dr._apply_dark_theme(dot)
    assert 'bgcolor="#0d1117"' in result
    assert "fillcolor" in result


def test_dark_theme_not_injected_when_bgcolor_present():
    dot = 'digraph G { graph [bgcolor="#0d1117"] A -> B }'
    result = dr._apply_dark_theme(dot)
    # Should not duplicate bgcolor
    assert result.count("bgcolor=") == 1


def test_dark_theme_no_brace_returns_unchanged():
    dot = "not a dot string"
    assert dr._apply_dark_theme(dot) == dot


# ── analogy fallback ────────────────────────────────────────────────────────


def test_analogy_fallback_creates_png(tmp_path):
    out = tmp_path / "analogy.png"
    result = dr._render_analogy_fallback("An interface is a job description.", out)
    assert result == out
    assert out.exists()
    img = Image.open(out)
    assert img.size == (800, 260)
    assert img.mode == "RGB"


def test_analogy_fallback_empty_text_does_not_crash(tmp_path):
    out = tmp_path / "empty.png"
    result = dr._render_analogy_fallback("", out)
    assert result is not None
    assert out.exists()


def test_render_diagram_none_type_returns_analogy_png(tmp_path):
    spec = _make_spec(diagram_type="none", analogy="Copy the address, not the house.")
    result = dr.render_diagram(spec, tmp_path)
    assert result is not None
    assert result.exists()
    assert result.suffix == ".png"


# ── code_comparison ─────────────────────────────────────────────────────────


def test_code_comparison_creates_png(tmp_path):
    spec = _make_spec(
        diagram_type="code_comparison",
        diagram_spec={
            "wrong": "if (a == b) {}",
            "right": "if (a.equals(b)) {}",
            "label_wrong": "compares references",
            "label_right": "compares content",
        },
    )
    result = dr.render_diagram(spec, tmp_path)
    assert result is not None
    assert result.exists()
    img = Image.open(result)
    assert img.size == (800, 400)


def test_code_comparison_no_graphviz_subprocess(tmp_path, monkeypatch):
    """code_comparison must not call subprocess at all."""
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: calls.append(a) or None)

    spec = _make_spec(
        diagram_type="code_comparison",
        diagram_spec={"wrong": "x=1", "right": "x.equals(1)", "label_wrong": "", "label_right": ""},
    )
    dr.render_diagram(spec, tmp_path)
    assert calls == [], "subprocess.run should not be called for code_comparison"


def test_code_comparison_bad_spec_falls_back_to_analogy(tmp_path):
    spec = _make_spec(
        diagram_type="code_comparison",
        diagram_spec="not a dict",  # wrong type
    )
    result = dr.render_diagram(spec, tmp_path)
    assert result is not None
    assert result.exists()
    # Should be analogy size, not code_comparison size
    img = Image.open(result)
    assert img.size == (800, 260)


# ── graphviz paths (subprocess mocked) ─────────────────────────────────────


def test_class_diagram_produces_png(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run_ok(tmp_path))
    dr._graphviz_ready = True  # skip the probe

    spec = _make_spec(
        diagram_type="class_diagram",
        diagram_spec="digraph G { rankdir=BT\n Invoice -> Printable [arrowhead=empty] }",
    )
    result = dr.render_diagram(spec, tmp_path)
    assert result is not None
    assert result.exists()


def test_flowchart_produces_png(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run_ok(tmp_path))
    dr._graphviz_ready = True

    spec = _make_spec(
        diagram_type="flowchart",
        diagram_spec='digraph G { rankdir=TB\n A [shape=diamond label="=="]\n A -> B [label="yes"] }',
    )
    result = dr.render_diagram(spec, tmp_path)
    assert result is not None
    assert result.exists()


def test_concept_map_uses_neato_engine(tmp_path, monkeypatch):
    captured = []

    def capturing_run(cmd, **kwargs):
        captured.append(list(cmd))
        _fake_run_ok(tmp_path)(cmd, **kwargs)
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(subprocess, "run", capturing_run)
    dr._graphviz_ready = True

    spec = _make_spec(
        diagram_type="concept_map",
        diagram_spec="graph G { layout=neato\n A -- B [label=includes] }",
    )
    dr.render_diagram(spec, tmp_path)

    # Filter out the probe call; find the render call
    render_calls = [c for c in captured if "-Tpng" in c]
    assert render_calls, "Expected at least one -Tpng call"
    assert "-Kneato" in render_calls[0], f"Expected -Kneato in {render_calls[0]}"


def test_invalid_dot_falls_back_to_analogy(tmp_path, monkeypatch):
    def failing_run(cmd, **kwargs):
        if "-Tpng" in cmd:
            return subprocess.CompletedProcess(cmd, 1, b"", b"syntax error in DOT")
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(subprocess, "run", failing_run)
    dr._graphviz_ready = True

    spec = _make_spec(
        diagram_type="class_diagram",
        diagram_spec="digraph G { this is invalid DOT }",
        analogy="Copy the address, not the house.",
    )
    result = dr.render_diagram(spec, tmp_path)
    assert result is not None
    assert result.exists()
    img = Image.open(result)
    assert img.size == (800, 260)  # analogy fallback dimensions


# ── graphviz missing ────────────────────────────────────────────────────────


def test_graphviz_missing_raises_config_error(tmp_path, monkeypatch):
    from tutor.exceptions import ConfigError

    def not_found(cmd, **kwargs):
        raise FileNotFoundError("dot not found")

    monkeypatch.setattr(subprocess, "run", not_found)
    # Also disable Windows PATH probe by setting platform to non-win32
    monkeypatch.setattr(dr.sys, "platform", "linux")

    spec = _make_spec(
        diagram_type="class_diagram",
        diagram_spec="digraph G { A -> B }",
    )
    with pytest.raises(ConfigError, match="Graphviz not found"):
        dr.render_diagram(spec, tmp_path)


# ── output filename ─────────────────────────────────────────────────────────


def test_output_filename_uses_unit_index(tmp_path):
    spec = _make_spec(unit_index=3, diagram_type="none", analogy="test")
    result = dr.render_diagram(spec, tmp_path)
    assert result.name == "unit_03_diagram.png"
