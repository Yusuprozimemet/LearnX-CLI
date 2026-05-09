# Day 14 — Dialogue-Aware Visual Planner

## Goal

Replace the v2 approach of generating 3 slides per unit from metadata with a v3
approach that reads the actual dialogue transcript and produces 8–15 `SlideSegment`
objects per unit. Each segment covers 1–3 consecutive dialogue lines and maps to
one specific visual type.

**The v2 `plan_visuals()` function is kept unchanged.** It still generates the
title card and outro, which are not dialogue-driven. A new module,
`segment_planner.py`, handles per-unit dialogue segmentation and is the only new
file in this day.

---

## Data boundary

```
Reads:
  audio/<session>/tutorial.units.json      ← dialogue lines + unit metadata
  .tutor_cache/<hash>.segments.json        ← per-unit LLM response cache

Writes:
  video/<session>/tutorial.segments.json   ← ordered SlideSegment list per unit
```

No audio files, no MP4 files, no Pillow calls in `segment_planner.py`.

---

## New model — `tutor/models.py`

Add `VALID_VISUAL_TYPES` and `SlideSegment`. `VisualSpec` and all other models are
unchanged.

```python
VALID_VISUAL_TYPES: frozenset[str] = frozenset({
    "hook_question",
    "definition",
    "analogy",
    "comparison",
    "code_example",
    "question_prompt",
    "decision_guide",
    "key_insight",
    "memory_hook",
})

@dataclass
class SlideSegment:
    unit_index:    int
    segment_index: int            # 0-based position within the unit
    lines_start:   int            # 0-based index of first line (inclusive)
    lines_end:     int            # 0-based index of last line (inclusive)
    visual_type:   str            # one of VALID_VISUAL_TYPES
    title:         str            # short slide header (max 10 words)
    body:          str            # main text; use \n to separate bullet items
    code:          str | None = None   # code string — code_example and definition
    left:          str | None = None   # left column/panel label
    right:         str | None = None   # right column/panel label
    rows:          list | None = None  # list[list[str]] — two-column data
    png_path:      str = ""            # filled in by slide compositor (Day 15)
```

### Field usage by visual type

| Type | title | body | code | left | right | rows |
|---|---|---|---|---|---|---|
| hook_question | opening question | "WHAT YOU'LL LEARN:" items (`\n`-sep) | – | – | – | – |
| definition | term name | definition text | optional code | – | – | – |
| analogy | "Think of it this way" | – | – | real-world label | concept label | `[[left_text, right_text]]` |
| comparison | "X vs Y" | – | – | left label | right label | `[[cell, cell], …]` |
| code_example | context phrase | optional description | code string | – | – | – |
| question_prompt | "MAYA asks" or "SAM asks" | question text verbatim | – | – | – | – |
| decision_guide | "When to use each" | – | – | left condition | right condition | `[[criterion, criterion], …]` |
| key_insight | rule phrase (≤ 8 words) | insight text | – | – | – | – |
| memory_hook | "Remember" | memory hook text | – | – | – | – |

For `analogy`, `rows` always has exactly one entry: `[[left_body, right_body]]`.
For `comparison` and `decision_guide`, `rows` has 2–6 entries.

---

## `tutorial.segments.json` — format

Written to `video/<session>/tutorial.segments.json`.

```json
{
  "version": 1,
  "units": {
    "1": [
      {
        "unit_index": 1, "segment_index": 0,
        "lines_start": 0, "lines_end": 1,
        "visual_type": "hook_question",
        "title": "Interface or abstract class — which fits?",
        "body": "Contracts vs blueprints\nWhen to use each\nThe IS-A vs HAS-A rule",
        "code": null, "left": null, "right": null, "rows": null, "png_path": ""
      },
      {
        "unit_index": 1, "segment_index": 1,
        "lines_start": 2, "lines_end": 4,
        "visual_type": "definition",
        "title": "Interface",
        "body": "A contract specifying what a class MUST do, without implementation.",
        "code": "interface Animal { void speak(); }",
        "left": null, "right": null, "rows": null, "png_path": ""
      },
      {
        "unit_index": 1, "segment_index": 2,
        "lines_start": 5, "lines_end": 6,
        "visual_type": "analogy",
        "title": "Think of it this way",
        "body": "", "code": null,
        "left": "Job Description", "right": "Interface",
        "rows": [["Lists duties, says nothing about HOW", "Lists methods, says nothing about HOW"]],
        "png_path": ""
      }
    ],
    "2": [...]
  }
}
```

Keys in `"units"` are unit numbers as strings. The `png_path` field is `""`
in this file — it is populated in memory by the compositor (Day 15) and not
written back to disk.

---

## New module — `tutor/generation/segment_planner.py`

Single responsibility: read dialogue lines per unit → call LLM → return
`dict[int, list[SlideSegment]]`. No drawing, no ffmpeg, no Pillow.

### Public API

```python
def plan_segments(
    units_json_path: Path,
    video_dir: Path,
    llm_fn: Callable,
    no_cache: bool = False,
) -> dict[int, list[SlideSegment]]:
    """
    For each teaching unit, call LLM with its dialogue lines.
    Returns dict keyed by unit_index (int) → list[SlideSegment] in line order.
    Writes tutorial.segments.json to video_dir.
    Skips units with no dialogue lines — logs a warning, does not crash.
    """
```

### Private functions

```python
def _plan_unit_segments(
    unit_index: int,
    unit_concept: str,
    lines: list[DialogueLine],
    llm_fn: Callable,
    cache_file: Path,
) -> list[SlideSegment]:
    """
    Call LLM for one unit. Uses file cache when available.
    Returns _fallback_segments() on any LLM or parse error.
    """

def _parse_segments_response(
    raw: str,
    unit_index: int,
    lines: list[DialogueLine],
) -> list[SlideSegment]:
    """
    Parse the LLM JSON array into SlideSegment objects.
    Validates: visual_type in VALID_VISUAL_TYPES; lines_start/end in bounds;
    required fields present (title, body). Fills gaps and fixes ordering.
    Falls back to _fallback_segments() on unrecoverable parse failure.
    """

def _fill_gaps(
    raw_segments: list[SlideSegment],
    unit_index: int,
    total_lines: int,
) -> list[SlideSegment]:
    """
    Ensure every line 0..total_lines-1 is covered by exactly one segment.
    Insert key_insight segments to fill uncovered ranges.
    Clamp out-of-bound indices to valid range.
    """

def _fallback_segments(
    unit_index: int,
    lines: list[DialogueLine],
) -> list[SlideSegment]:
    """
    Produce minimal valid segments without LLM:
    - First 1-2 ALEX lines → hook_question
    - Middle blocks of 3 lines → key_insight
    - Last 1-2 ALEX lines → memory_hook
    Never returns an empty list.
    """

def _cache_path(unit_index: int, lines: list[DialogueLine]) -> Path:
    """
    MD5 of all dialogue texts + "segments_v1" → .tutor_cache/<hash>.segments.json
    """

def _load_unit_lines(units_json_path: Path) -> dict[int, tuple[str, list[DialogueLine]]]:
    """
    Parse tutorial.units.json.
    Returns dict keyed by unit number → (concept, list[DialogueLine]).
    Only includes teaching units (unit_number >= 1).
    """
```

### Validation rules applied in `_parse_segments_response()`

1. `visual_type` not in `VALID_VISUAL_TYPES` → replace with `key_insight`
2. `lines_start > lines_end` → swap them
3. `lines_start < 0` → clamp to 0
4. `lines_end >= len(lines)` → clamp to `len(lines) - 1`
5. Missing `title` → use `visual_type.replace("_", " ").title()`
6. Missing `body` → empty string (some types legitimately have no body)
7. `rows` present but not a list-of-lists → set to `None`
8. After all corrections, run `_fill_gaps()` to enforce full coverage

---

## LLM call design

### New entries in `llm_config.toml`

```toml
[providers.groq]
segments = "llama-3.3-70b-versatile"

[providers.openrouter]
segments = "google/gemma-3-27b-it:free"

[max_tokens]
segments = 2000
```

Add alongside existing keys — no existing keys are changed.

### Prompt — `tutor/prompts/visual_v2.txt`

```
You are generating slide content for an audio tutorial video.

Given the dialogue transcript for one teaching unit, group consecutive lines
into visual segments. Each segment covers 1–3 lines that share one idea.

For each segment output a JSON object with these exact fields:
  lines_start  — 0-based index of first line (inclusive)
  lines_end    — 0-based index of last line (inclusive)
  visual_type  — one of the types listed below
  title        — slide header, max 10 words
  body         — main text; separate bullet items with \n; max 60 chars per line
  code         — code string if relevant, else null
  left         — left column/panel label for comparison, analogy, decision_guide; else null
  right        — right column/panel label for comparison, analogy, decision_guide; else null
  rows         — list of [left_cell, right_cell] pairs for comparison/analogy/decision_guide; else null

Visual types and when to use them:
  hook_question   — ALEX's opening hook lines (always the first segment)
  definition      — ALEX introduces or explains a named term or concept
  analogy         — ALEX uses "like", "think of", "imagine", or "similar to"
  comparison      — ALEX contrasts two concepts or approaches side by side
  code_example    — ALEX demonstrates or references a specific code pattern
  question_prompt — MAYA or SAM asks a question (their lines only)
  decision_guide  — ALEX explains when to choose X over Y (criteria-based)
  key_insight     — ALEX states a rule, principle, or key fact
  memory_hook     — ALEX's closing memory-hook lines (always the last segment)

Rules:
  1. Cover every line — no gaps; lines_end of segment N + 1 == lines_start of segment N+1
  2. First segment: hook_question; last segment: memory_hook
  3. MAYA or SAM lines alone → question_prompt
  4. ALEX lines with "like", "imagine", "think of" → analogy
  5. ALEX contrasting two things → comparison or decision_guide
  6. Any code mentioned → code_example
  7. Produce 8–15 segments; never fewer than 5

Output: a JSON array only. No prose before or after.
```

### Input (user message)

```json
{
  "unit": 1,
  "concept": "Interface vs Abstract Class",
  "lines": [
    {"index": 0, "speaker": "ALEX", "text": "If both can have abstract methods — why do we need both?"},
    {"index": 1, "speaker": "ALEX", "text": "Today we break that question open."},
    {"index": 2, "speaker": "MAYA", "text": "I always thought they were the same thing."},
    ...
  ]
}
```

### Caching

- Cache key: `MD5(json.dumps(lines_as_dicts, sort_keys=True) + "segments_v1")`
- Cache file: `.tutor_cache/<hash>.segments.json`
- `no_cache=True` deletes matching `.segments.json` cache files before calling the LLM

### Error handling

| Failure | Behaviour |
|---|---|
| LLM raises exception | Log warning; return `_fallback_segments()` |
| LLM returns invalid JSON | Log warning; return `_fallback_segments()` |
| Unknown `visual_type` | Replace with `key_insight`; keep segment |
| Line index out of bounds | Clamp to `[0, len(lines)-1]` |
| Gap between segments | Insert `key_insight` to fill missing lines |
| Unit has 0 lines | Skip unit; log warning |

Never raise from `plan_segments()`. A degraded segment plan is acceptable; a crash
during video generation is not.

---

## File size

`segment_planner.py` is a new file targeting approximately 200 lines.
`models.py` grows by approximately 30 lines (under 200 total).

---

## Acceptance criteria

- [ ] `plan_segments()` returns at least one segment per unit
- [ ] First segment per unit is always `hook_question`
- [ ] Last segment per unit is always `memory_hook`
- [ ] Every dialogue line index 0..N-1 covered by exactly one segment (no gaps)
- [ ] No two segments overlap (`seg[i].lines_end + 1 == seg[i+1].lines_start`)
- [ ] `tutorial.segments.json` written to `video/<session>/`, not `audio/<session>/`
- [ ] LLM failure returns `_fallback_segments()` — no exception raised
- [ ] Unknown `visual_type` in LLM output is replaced, not dropped
- [ ] Cache hit skips the LLM call entirely
- [ ] `no_cache=True` forces LLM call even when cache file exists
- [ ] `segment_planner.py` stays under 400 lines
- [ ] `models.py` stays under 200 lines after adding `SlideSegment`

## Tests — `tutor/tests/generation/test_segment_planner.py`

- `test_plan_segments_returns_dict_keyed_by_unit`
- `test_all_lines_covered` — for every unit: union of (lines_start..lines_end) == 0..N-1
- `test_no_line_covered_twice` — segments do not overlap
- `test_first_segment_is_hook_question`
- `test_last_segment_is_memory_hook`
- `test_invalid_json_from_llm_returns_fallback` — mock LLM returns garbage
- `test_unknown_visual_type_replaced_with_key_insight` — "banana" → key_insight
- `test_out_of_bounds_indices_clamped` — lines_end=999 on a 5-line unit → clamped to 4
- `test_gap_filled_with_key_insight` — LLM skips lines 3-5 → gap filled
- `test_cache_hit_skips_llm_call` — second call with same unit: LLM not called
- `test_no_cache_forces_regeneration` — `no_cache=True` → LLM called again
- `test_segments_json_written_to_video_dir`
- `test_unit_with_zero_lines_skipped_not_crashed`
