# Day 3 (v12) — Visual Planner Prompt Upgrade

## Goal

Rewrite `tutor/prompts/visual_v3.txt` with two new slide types (`step_sequence`
and `callout`), sharper assignment rules, and guidance to diversify slide variety.
Update `tutor/generation/segment_planner.py` to add both types to the valid type set
and their validation logic. Add tests for the new type handling.

---

## Done (merge gate)

```powershell
py -m pytest tutor/tests/ -v -k "visual or segment or planner"
py -m ruff check tutor/
py -m ruff format --check tutor/
```

Report: paste gate output. List each acceptance criterion.
Stop: do not merge — wait for human review.

---

## Data boundary

```
Modifies (existing):
  tutor/prompts/visual_v3.txt                ← full rewrite
  tutor/generation/segment_planner.py        ← add 2 types to valid set + tests

Does NOT touch:
  tutor/prompts/visual.txt                   ← unchanged (used by visual_planner.py)
  tutor/generation/visual_planner.py         ← unchanged
  tutor/visual/templates/                    ← already done in Day 2
  tutor/models.py                            ← unchanged (no new dataclass fields)
  tutor/visual/slide_renderer.py             ← unchanged (Day 4)
```

---

## Change 1 — Rewrite `tutor/prompts/visual_v3.txt`

Replace the entire file with the following. Key additions vs the current prompt:
- `step_sequence` and `callout` types with explicit assignment triggers
- Reinforced diversity rule: `definition` must not exceed 35% of all segments
- `callout` takes the role of isolated important statements previously forced into `key_insight`
- Updated output field documentation to match the `step_sequence` usage of `body`

```
You are generating slide content for an audio tutorial video.

Given the dialogue transcript for one teaching unit, group consecutive lines into
visual segments. Each segment covers 1–3 lines that share one idea.

For each segment output a JSON object with these exact fields:
  lines_start  — 0-based index of first line (inclusive)
  lines_end    — 0-based index of last line (inclusive)
  visual_type  — one of the 12 types listed below
  title        — slide header, ≤ 10 words
  body         — main text content (see per-type notes below); null if unused
  code         — code string if relevant, else null
  language     — highlight.js language id (e.g. "java", "python") if code present, else null
  mermaid      — Mermaid diagram string if visual_type is "diagram", else null
  left         — left column/panel label for analogy, comparison, decision_guide; else null
  right        — right column/panel label; else null
  rows         — list of [left_cell, right_cell] pairs for comparison/analogy/decision_guide; else null

Visual types and when to use them:

  hook_question   — ALEX's opening hook lines (always the first segment).
                    body: the hook question text. rows: up to 3 learning objectives
                    as [[objective, ""], ...] (single-column list).

  definition      — ALEX introduces or formally defines a named term or concept.
                    body: the definition text (1–2 sentences). code: short example
                    if the definition is illustrated by code.

  analogy         — ALEX uses "like", "think of", "imagine", "similar to", or
                    "it's as if". body: not used when rows is present.
                    left/right: the two things being compared (real-world vs code).
                    rows: [[real_world_description, code_description]].

  comparison      — ALEX contrasts two named concepts side by side.
                    left/right: the two concept names. rows: property rows
                    [[left_value, right_value], ...] (3–5 rows).

  code_example    — ALEX demonstrates or references a specific code pattern.
                    body: one-line description of what the code shows (optional).
                    code: the code string. language: highlight.js id.

  diagram         — ALEX describes a structural relationship (class hierarchy,
                    data flow, state machine, dependency graph).
                    mermaid: a valid Mermaid diagram string.
                    Use classDiagram for class/interface relationships,
                    flowchart TD for process flows.

  question_prompt — MAYA or SAM lines only. Do NOT mix with ALEX lines.
                    body: "SPEAKER: question text" (e.g. "MAYA: But why not just…").

  decision_guide  — ALEX explains when to choose X over Y using if/when/unless
                    criteria. left: "Use X when". right: "Avoid X when".
                    rows: [[criterion_for, criterion_against], ...].

  key_insight     — ALEX states a rule, principle, or memorable law.
                    body: the complete rule statement (one sentence, max 20 words).
                    Reserve for concise, standalone rules. Use callout for longer
                    important statements.

  memory_hook     — ALEX's closing memory-hook lines (always the last segment).
                    body: the mnemonic or summary phrase ALEX uses.

  step_sequence   — ALEX explains a sequential multi-step process ("first…",
                    "step one…", "then you…", "next…", "finally…").
                    body: steps separated by \n, one step per line (3–6 steps).
                    Each line becomes a numbered circle in the slide.

  callout         — A single important statement that stands alone: a prerequisite,
                    a warning, a key quote, or a tip. Use when the content is too
                    long or complex for key_insight but is a single highlighted point.
                    title: the label ("NOTE", "WARNING", "TIP", "PREREQUISITE", "QUOTE").
                    body: the statement (1–3 sentences).

Assignment rules:
  1. Cover every line — no gaps; lines_end of segment N + 1 == lines_start of N+1.
  2. First segment: hook_question. Last segment: memory_hook.
  3. MAYA or SAM lines alone → question_prompt.
  4. ALEX using "like", "imagine", "think of", "similar to" → analogy.
  5. ALEX contrasting two named things → comparison or decision_guide.
  6. ALEX describing class/flow/dependency structure → diagram (Mermaid required).
  7. ALEX showing or referencing specific code → code_example.
  8. ALEX explaining "first… then… finally…" or numbered steps → step_sequence.
  9. ALEX stating a single short rule (≤ 20 words) → key_insight.
  10. ALEX making a single important point that's longer than a rule → callout.
  11. ALEX introducing a named concept with a formal definition → definition.
  12. Produce 8–15 segments; never fewer than 5.
  13. Diversity rule: definition must not exceed 35% of total segments.
      If you would produce more, merge adjacent definitions or reclassify as
      key_insight, callout, or code_example where appropriate.

Output: a JSON array only. No prose before or after. No markdown code fences.
```

---

## Change 2 — Update `tutor/generation/segment_planner.py`

### 2a — Extend the valid type set

Locate the constant or frozenset that defines valid visual types. It will be named
something like `VALID_VISUAL_TYPES` or defined inline in the validation function.
Add `"step_sequence"` and `"callout"` to it.

Before:
```python
VALID_VISUAL_TYPES = frozenset({
    "hook_question", "definition", "analogy", "comparison",
    "code_example", "diagram", "question_prompt",
    "decision_guide", "key_insight", "memory_hook",
})
```

After:
```python
VALID_VISUAL_TYPES = frozenset({
    "hook_question", "definition", "analogy", "comparison",
    "code_example", "diagram", "question_prompt",
    "decision_guide", "key_insight", "memory_hook",
    "step_sequence", "callout",
})
```

### 2b — Validate `step_sequence` body field

Add validation after the `visual_type` check: when `visual_type == "step_sequence"`,
warn if `body` is None or empty (the template requires newline-separated steps in
`body`), and fall back to `"definition"` for that segment rather than producing a
blank slide.

In the segment validation loop (wherever individual segments are post-processed):

```python
if seg.visual_type == "step_sequence" and not seg.body:
    log.warning(
        "segment %d-%d is step_sequence but body is empty — "
        "falling back to definition",
        seg.lines_start, seg.lines_end,
    )
    seg.visual_type = "definition"
    seg.body = seg.title
```

### 2c — Validate `callout` fields

When `visual_type == "callout"`, validate that both `title` and `body` are present.
If `body` is missing, fall back to `"key_insight"`:

```python
if seg.visual_type == "callout" and not seg.body:
    log.warning(
        "segment %d-%d is callout but body is empty — "
        "falling back to key_insight",
        seg.lines_start, seg.lines_end,
    )
    seg.visual_type = "key_insight"
```

---

## New tests — add to `tutor/tests/test_segment_planner.py`

(Create this test file if it does not exist in `tutor/tests/`.)

```python
from tutor.generation.segment_planner import VALID_VISUAL_TYPES


def test_step_sequence_in_valid_types():
    assert "step_sequence" in VALID_VISUAL_TYPES


def test_callout_in_valid_types():
    assert "callout" in VALID_VISUAL_TYPES


def test_step_sequence_fallback_on_empty_body(monkeypatch, caplog):
    """step_sequence with empty body is reclassified to definition."""
    import logging
    from tutor.generation.segment_planner import _validate_segment
    from tutor.models import SlideSegment

    seg = SlideSegment(
        unit_index=1,
        segment_index=0,
        lines_start=0,
        lines_end=1,
        visual_type="step_sequence",
        title="Steps to deploy",
        body=None,
        code=None,
        language=None,
        mermaid=None,
        left=None,
        right=None,
        rows=None,
    )
    with caplog.at_level(logging.WARNING):
        result = _validate_segment(seg)
    assert result.visual_type == "definition"
    assert "step_sequence" in caplog.text
    assert "body is empty" in caplog.text


def test_callout_fallback_on_empty_body(caplog):
    """callout with empty body is reclassified to key_insight."""
    import logging
    from tutor.generation.segment_planner import _validate_segment
    from tutor.models import SlideSegment

    seg = SlideSegment(
        unit_index=1,
        segment_index=0,
        lines_start=0,
        lines_end=1,
        visual_type="callout",
        title="WARNING",
        body=None,
        code=None,
        language=None,
        mermaid=None,
        left=None,
        right=None,
        rows=None,
    )
    with caplog.at_level(logging.WARNING):
        result = _validate_segment(seg)
    assert result.visual_type == "key_insight"
    assert "callout" in caplog.text


def test_valid_step_sequence_passes_validation():
    """step_sequence with body is accepted without reclassification."""
    from tutor.generation.segment_planner import _validate_segment
    from tutor.models import SlideSegment

    seg = SlideSegment(
        unit_index=1,
        segment_index=0,
        lines_start=0,
        lines_end=2,
        visual_type="step_sequence",
        title="How to deploy",
        body="Open the terminal\nRun the build script\nPush to staging",
        code=None,
        language=None,
        mermaid=None,
        left=None,
        right=None,
        rows=None,
    )
    result = _validate_segment(seg)
    assert result.visual_type == "step_sequence"


def test_valid_callout_passes_validation():
    """callout with title and body is accepted without reclassification."""
    from tutor.generation.segment_planner import _validate_segment
    from tutor.models import SlideSegment

    seg = SlideSegment(
        unit_index=1,
        segment_index=0,
        lines_start=4,
        lines_end=5,
        visual_type="callout",
        title="TIP",
        body="Always run the linter before committing — it catches 80% of review feedback.",
        code=None,
        language=None,
        mermaid=None,
        left=None,
        right=None,
        rows=None,
    )
    result = _validate_segment(seg)
    assert result.visual_type == "callout"
```

Note: if `_validate_segment` does not exist as a named function in
`segment_planner.py`, locate the validation logic and extract it. Keep the
function under 20 lines; the validation loop calls it per segment.

---

## Acceptance criteria

- [ ] `tutor/prompts/visual_v3.txt` contains `step_sequence` in the types list
- [ ] `tutor/prompts/visual_v3.txt` contains `callout` in the types list
- [ ] `visual_v3.txt` includes rule 8 (`step_sequence` for sequential processes)
- [ ] `visual_v3.txt` includes rule 10 (`callout` for single highlighted points)
- [ ] `visual_v3.txt` includes diversity rule 13 (`definition` cap at 35%)
- [ ] `VALID_VISUAL_TYPES` in `segment_planner.py` includes `"step_sequence"`
- [ ] `VALID_VISUAL_TYPES` in `segment_planner.py` includes `"callout"`
- [ ] `step_sequence` with empty `body` → reclassified to `"definition"` with warning logged
- [ ] `callout` with empty `body` → reclassified to `"key_insight"` with warning logged
- [ ] `step_sequence` with valid `body` → passes validation unchanged
- [ ] `callout` with valid `title` and `body` → passes validation unchanged
- [ ] All 5 new tests pass
- [ ] All pre-existing tests still pass
- [ ] ruff clean
