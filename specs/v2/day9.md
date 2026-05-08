# Day 9 — Diagram Rendering

## Goal

Take the `diagram_type` + `diagram_spec` from each `VisualSpec` and produce a PNG
image. All diagrams use the same dark-theme colour palette as the slide background.
Output goes to `video/<session>/slides/`.

---

## Data boundary

```
Reads:   VisualSpec (in memory, passed as argument)
Writes:  video/<session>/slides/unit_01_diagram.png
                              ...unit_N_diagram.png
```

No audio files, no MP4 files, no units JSON are touched in this module.

---

## Graphviz detection

Graphviz must be installed and in PATH. Use the same probe-and-inject pattern as
ffmpeg detection in `tutor/config.py`:

```python
def _check_graphviz() -> None:
    try:
        subprocess.run(["dot", "-V"], stdout=DEVNULL, stderr=DEVNULL, check=True)
        return
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    if sys.platform == "win32":
        candidates = [
            Path("C:/Program Files/Graphviz/bin/dot.exe"),
            *Path("C:/Program Files/Graphviz").glob("*/bin/dot.exe"),
            Path("C:/Graphviz/bin/dot.exe"),
        ]
        for c in candidates:
            if c.exists():
                os.environ["PATH"] = str(c.parent) + os.pathsep + os.environ["PATH"]
                return

    raise ConfigError(
        "Graphviz not found.\n"
        "  Install: winget install graphviz\n"
        "  Then restart your terminal or re-run."
    )
```

Call `_check_graphviz()` at the top of `render_diagram()`, not at import time —
graphviz is only needed during video generation, never during audio generation.

---

## Colour palette — dark theme

All graphviz diagrams must integrate with the slide background:

```dot
graph [bgcolor="#0d1117" fontname="Consolas,monospace" fontcolor="#e6edf3"]
node  [style=filled fillcolor="#161b22" color="#30363d"
       fontcolor="#e6edf3" fontname="Consolas,monospace" fontsize=14]
edge  [color="#8b949e" fontcolor="#8b949e" fontname="Consolas,monospace" fontsize=11]
```

**Accent colours by node role:**

| Role | `fillcolor` | `color` (border) |
|---|---|---|
| Interface / contract | `#0d2a4a` | `#00b4d8` |
| Abstract class | `#1a2a1a` | `#3fb950` |
| Concrete class | `#161b22` | `#30363d` |
| Decision (diamond) | `#2a1a0d` | `#e3b341` |
| Correct / good | `#0d2a1a` | `#3fb950` |
| Wrong / bad | `#2a0d0d` | `#f85149` |
| Start / end (oval) | `#1a1a2e` | `#00b4d8` |

---

## Type 1 — `class_diagram`

**Layout engine:** `dot` (hierarchical)
**rankdir:** `BT` (subclass → parent, standard UML direction)

Conventions:
- Interfaces: dashed border (`style="dashed"`) + blue border + `«interface»` prefix
- Abstract classes: normal border + green border + `«abstract»` prefix
- Inheritance arrow: `arrowhead=empty`
- Implementation arrow: `arrowhead=empty style=dashed`

Target size: `graph [size="8,5" dpi=100]` → ~800×500px output.

---

## Type 2 — `flowchart`

**Layout engine:** `dot`
**rankdir:** `TB`

Conventions:
- Start/end: `shape=oval`, blue border
- Decision: `shape=diamond`, amber border + amber fill
- Process: `shape=box`
- Edge labels: max 3 words

---

## Type 3 — `concept_map`

**Layout engine:** `neato` (force-directed — better for non-hierarchical graphs)

Conventions:
- All nodes: `shape=box style="filled,rounded"`
- Edge labels describe relationship (verb phrase, max 3 words)
- Central concept node: `fontsize=18`, cyan border

---

## Type 4 — `code_comparison`

Rendered entirely by Pillow — **no graphviz involved**.

Layout: two equal columns side by side, separated by a vertical divider.

| Property | Value |
|---|---|
| Canvas size | 800 × 400px |
| Background | `#161b22` |
| Left header (wrong) | `#f85149` (red), 18px bold |
| Right header (correct) | `#3fb950` (green), 18px bold |
| Code text | `#e6edf3`, 16px monospace |
| Comment text | `#8b949e`, 16px monospace |
| Divider | `#30363d`, 1px vertical |
| Corner radius | 12px |

Input from `diagram_spec`:
```json
{
  "wrong":       "String a = \"hello\";\nif (a == b) { }",
  "right":       "String a = \"hello\";\nif (a.equals(b)) { }",
  "label_wrong": "compares references",
  "label_right": "compares content"
}
```

---

## Type 5 — `analogy_fallback`

Used when `diagram_type == "none"` or any render step fails.

| Property | Value |
|---|---|
| Canvas size | 800 × 260px |
| Background | `#161b22` with 8px left border stripe in `#00b4d8` |
| Opening quote `"` | `#00b4d8`, 80px |
| Analogy text | italic, 28px, `#e6edf3`, centred, max 3 lines |
| Attribution | `— analogy`, `#8b949e`, 18px, bottom-right |

---

## Module — `tutor/visual/diagram_renderer.py`

Single file, under 400 lines. All 5 renderer types fit because:
- graphviz types share `_render_graphviz()` (one function, 3 callers)
- Pillow types are small (~80 and ~50 lines)

```python
def render_diagram(spec: VisualSpec, output_dir: Path) -> Path | None:
    """Dispatch to the correct renderer. Returns PNG path or None on failure."""

def _render_graphviz(dot_source: str, output_path: Path, engine: str = "dot") -> Path:
    """Write DOT to temp file, invoke dot/neato, return PNG path."""

def _render_code_comparison(spec_dict: dict, output_path: Path) -> Path:
    """Pillow two-column layout. No graphviz needed."""

def _render_analogy_fallback(analogy: str, output_path: Path) -> Path:
    """Pillow quote block. Used on failure or diagram_type=none."""

def _check_graphviz() -> None:
    """Probe dot binary; inject PATH on Windows if found in known locations."""

def _apply_dark_theme(dot_source: str) -> str:
    """Inject dark-theme graph/node/edge defaults if bgcolor= not present."""
```

**Output filenames:**
```
video/<session>/slides/unit_01_diagram.png
video/<session>/slides/unit_02_diagram.png
...
```

---

## Acceptance criteria

- [ ] `class_diagram` renders with correct node shapes and dark background
- [ ] `flowchart` renders with diamond decisions and oval start/end
- [ ] `concept_map` uses `neato` engine (non-hierarchical)
- [ ] `code_comparison` renders two columns with red/green headers, no graphviz call
- [ ] `analogy_fallback` renders when diagram_type is none or on any graphviz error
- [ ] All output PNGs are 800px wide
- [ ] Dark background (`#0d1117` or `#161b22`) visible in all outputs
- [ ] Output written to `video/<session>/slides/`, not `audio/<session>/slides/`
- [ ] graphviz not installed → raises `ConfigError` with install instructions
- [ ] Invalid DOT string → logs warning, returns analogy_fallback PNG

## Tests — `tutor/tests/visual/test_diagram_renderer.py`

- `test_class_diagram_produces_png` — mock graphviz subprocess, assert PNG created
- `test_flowchart_produces_png`
- `test_concept_map_uses_neato_engine` — assert `-Kneato` in subprocess args
- `test_code_comparison_no_graphviz_needed` — renders without calling subprocess
- `test_analogy_fallback_on_invalid_dot` — bad DOT string → fallback PNG returned
- `test_dark_theme_injected_when_missing` — DOT without bgcolor gets it added
- `test_graphviz_missing_raises_config_error` — monkeypatch dot to not exist
