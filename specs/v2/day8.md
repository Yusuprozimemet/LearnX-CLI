# Day 8 — Visual Spec Generation

## Goal

For each teaching unit, call an LLM to produce a structured visual specification —
the content of every slide, the diagram type, and the data needed to render it.
Store the result in `video/<session>/tutorial.visuals.json`.

**The existing audio pipeline is not modified.** Visual planning is triggered only
by the `/video` shell command or `--video` flag, not automatically during audio
generation.

---

## Data boundary

```
audio/<session>/                 ← written by audio pipeline (untouched)
  tutorial.units.json            ← input: teaching unit metadata
  tutorial_units/unit_*.mp3      ← input: rendered audio per unit

video/<session>/                 ← written by visual pipeline (new)
  tutorial.visuals.json          ← output: one VisualSpec per unit
  slides/                        ← written by Days 9–10
  *.mp4, subtitles.srt           ← written by Day 11
```

`visual_planner.py` reads `audio/<session>/tutorial.units.json` and writes
`video/<session>/tutorial.visuals.json`. It creates `video/<session>/` if it
does not exist.

---

## What the visual spec must contain

Each unit produces one `VisualSpec` object. The full session is a list of them,
one per unit, plus a title card entry and an outro entry.

### `VisualSpec` dataclass — `tutor/models.py`

Add to the existing `models.py` (no other models are modified):

```python
@dataclass
class VisualSpec:
    unit_index: int
    slide_type: str            # "title_card" | "unit" | "outro"
    concept: str = ""
    hook_question: str = ""
    key_points: list[str] = field(default_factory=list)
    code_snippet: str | None = None
    diagram_type: str = "none"
    diagram_spec: object = None   # str (DOT) | dict | None
    memory_hook: str = ""
    analogy: str = ""
    # title_card fields
    title: str = ""
    subtitle: str = ""
    doc_source: str = ""
    # outro fields
    memory_hooks: list[str] = field(default_factory=list)
    session_stats: str = ""
```

### JSON schema — `tutorial.visuals.json`

```json
[
  {
    "unit_index": 0,
    "slide_type": "title_card",
    "title": "Java Interfaces and Abstract Classes",
    "subtitle": "4 units · ~26 minutes",
    "doc_source": "week2/3.md"
  },
  {
    "unit_index": 1,
    "slide_type": "unit",
    "concept": "Interface vs Abstract Class",
    "hook_question": "If both can have abstract methods — why do we need both?",
    "key_points": [
      "Interface: pure contract — no state, no constructor",
      "Abstract class: partial blueprint — can hold fields and methods",
      "Java allows multiple interface implementation; only one abstract class"
    ],
    "code_snippet": "interface Printable {\n    void print();\n}",
    "diagram_type": "class_diagram",
    "diagram_spec": "digraph G {\n  rankdir=BT\n  ...\n}",
    "memory_hook": "Interfaces = Can-Do contract.  Abstract = Is-A blueprint.",
    "analogy": "An interface is a job description. An abstract class is a half-built house."
  },
  {
    "unit_index": 5,
    "slide_type": "outro",
    "memory_hooks": [
      "Interfaces = Can-Do contract",
      "Pass-by-value: primitives copy, references copy the arrow"
    ],
    "session_stats": "4 units · 26 min · 0 Q&A"
  }
]
```

### `diagram_type` values

| Value | When to use |
|---|---|
| `class_diagram` | Inheritance, interfaces, type hierarchy |
| `flowchart` | Decisions, loops, exception handling, control flow |
| `code_comparison` | Wrong vs correct pattern, before vs after |
| `concept_map` | Multiple related ideas with labelled edges |
| `none` | Pure factual unit with no meaningful diagram |

---

## LLM call design

### New entries in `llm_config.toml`

```toml
[providers.groq]
visual = "llama-3.3-70b-versatile"   # 70b needed for reliable DOT output

[providers.openrouter]
visual = "google/gemma-3-27b-it:free"

[max_tokens]
visual = 1200

[limits]
max_visual_source_tokens = 800   # trimmed unit context sent to visual LLM
```

Add these alongside the existing keys — no existing keys are changed.

### Prompt — `tutor/prompts/visual.txt`

```
You are generating slide content for a Java audio tutorial.

Given the unit metadata below, produce a JSON object with these exact fields:
  hook_question    — one sharp question ALEX opens with (max 15 words)
  key_points       — list of 3 to 5 bullet strings (max 12 words each, plain English)
  code_snippet     — short Java code string if relevant, else null
  diagram_type     — one of: class_diagram | flowchart | code_comparison | concept_map | none
  diagram_spec     — valid DOT string for class_diagram/flowchart/concept_map,
                     OR {"wrong":"...","right":"...","label_wrong":"...","label_right":"..."}
                     for code_comparison, OR null if diagram_type is none
  memory_hook      — the memory_hook field restated as a punchy sentence (max 10 words)

RULES for DOT output:
- Use rankdir=BT for class diagrams, rankdir=TB for flowcharts
- Node labels must be plain text only — no HTML, no quotes inside labels
- All edge labels max 4 words
- Maximum 6 nodes total
- Use shape=box for classes/concepts, shape=diamond for decisions

Output only the JSON object. No prose before or after.
```

### Input to LLM (user message)

```json
{
  "concept": "...",
  "key_facts": [...],
  "common_misconception": "...",
  "good_analogy": "...",
  "memory_hook": "...",
  "word_budget": 400,
  "difficulty": "beginner"
}
```

---

## Module — `tutor/generation/visual_planner.py`

Responsible for: reading units JSON → calling LLM → writing VisualSpec list.
No rendering, no ffmpeg, no Pillow. Data only.

```python
def plan_visuals(
    units_json_path: Path,
    doc_title: str,
    session: str,
    llm_fn: Callable,
    difficulty: str,
    video_dir: Path,
    no_cache: bool = False,
) -> list[VisualSpec]:
    """
    Read units from units_json_path, generate one VisualSpec per unit via LLM.
    Returns ordered list: [title_card, unit_1, ..., unit_N, outro].
    Writes tutorial.visuals.json to video_dir.
    """

def _plan_unit(unit: TeachingUnit, llm_fn, difficulty, cache_file: Path) -> VisualSpec:
    """Call LLM for one unit. Uses cache if available."""

def _build_title_card(doc_title: str, units: list[TeachingUnit], doc_source: str) -> VisualSpec:
def _build_outro(units: list[TeachingUnit]) -> VisualSpec:
def _parse_visual_response(raw: str, unit: TeachingUnit) -> VisualSpec:
def _fallback_spec(unit: TeachingUnit) -> VisualSpec:
```

### Caching

Cache key: `MD5(concept + str(key_facts) + difficulty + "visual_v1")`
Cache file: `.tutor_cache/<hash>.visual.json`
`no_cache=True` deletes matching `.visual.json` cache files before generating.

### Error handling

If the LLM returns invalid JSON or invalid DOT:
1. Log a warning.
2. Set `diagram_type = "none"` and `diagram_spec = None`.
3. Keep all other fields from whatever was parseable.
4. Never raise — a missing diagram is acceptable; a crash is not.

---

## `VideoError` — `tutor/exceptions.py`

Add alongside the existing error classes (no existing classes are changed):

```python
class VideoError(TutorError):
    """Raised when any step of the video pipeline fails."""
```

---

## Acceptance criteria

- [ ] `plan_visuals()` returns one `VisualSpec` per unit plus title_card and outro
- [ ] `tutorial.visuals.json` written to `video/<session>/`, not `audio/<session>/`
- [ ] Existing audio pipeline (`tutor/tutor.py`, `tutor/cli/commands.py`) is not modified
- [ ] Each spec has valid `diagram_type` from the allowed set
- [ ] LLM failure on any unit produces a fallback spec, not a crash
- [ ] Cache hit skips LLM call
- [ ] `no_cache=True` clears `.visual.json` cache files
- [ ] `VisualSpec` added to `tutor/models.py`, `VideoError` added to `tutor/exceptions.py`

## Tests — `tutor/tests/generation/test_visual_planner.py`

- `test_plan_visuals_returns_title_and_outro` — verify first/last slide_type
- `test_unit_spec_has_required_fields` — all required keys present
- `test_invalid_llm_json_returns_fallback` — mock LLM returns garbage → no crash
- `test_invalid_dot_returns_none_diagram` — bad DOT → diagram_type=none
- `test_cache_hit_skips_llm_call` — second call with same unit uses cache
- `test_no_cache_flag_regenerates` — no_cache=True → LLM called again
- `test_output_written_to_video_dir` — assert path is video/<session>/tutorial.visuals.json
