# Day 6 — Dual-Tutor Format + Completion

## What works at the end of this day

The entire pipeline is feature-complete per the MVP checklist in `plan.md`.

```bash
# Dual-tutor format works
python tutor/tutor.py sample_docs/java-basics.md --format dual-tutor --output dual.mp3

# --topic forces a specific concept
python tutor/tutor.py sample_docs/java-basics.md --topic concurrency --dry-run

# All generate flags work together
python tutor/tutor.py sample_docs/java-basics.md \
    --format dual-tutor --difficulty intermediate --duration 25 --units 6 \
    --topic "HashMap internals" --output session.mp3 --play

# Full test suite passes
cd tutor && python -m pytest tests/ -v
```

All items in the MVP verification checklist in `plan.md` are checked off. The system is ready for real use.

---

## Day 6 is different from Days 1–5

Days 1–5 each added a new layer. Day 6 is a **completion sprint**: no new packages, no new infrastructure. It wires the dual-tutor format, finishes the remaining tests, runs a code quality audit, and does a full end-to-end verification. Many of the changes today are small — one or two lines in existing files — but the acceptance criteria require running the full system and confirming every item manually.

---

## Part 1 — Dual-Tutor Format

### 1a. `tutor/audio/tts_renderer.py` — add SAM voice (modify existing)

On Day 2, SAM was mapped to ALEX's voice as a placeholder:
```python
# was:
"SAM": VOICE_TUTOR,   # SAM voice overridden on Day 6
```

Update:
```python
# becomes:
"SAM": VOICE_COTUTOR,
```

`VOICE_COTUTOR = "en-US-SaraNeural"` is already in `constants.py`. Also add `RATE_COTUTOR` to the rate map:
```python
RATE_MAP: dict[str, str] = {
    "ALEX": RATE_TUTOR,
    "MAYA": RATE_STUDENT,
    "SAM": RATE_COTUTOR,
}
```

---

### 1b. `tutor/generation/dialogue.py` — validate speaker set for format (modify existing)

After parsing dialogue lines, verify the correct speakers appear:

```python
def _validate_speakers(lines: list[DialogueLine], fmt: str) -> None:
    speakers = {line.speaker for line in lines}
    if fmt == "tutor-student":
        if "ALEX" not in speakers:
            raise LLMError("tutor-student dialogue missing ALEX lines")
        if "SAM" in speakers:
            raise LLMError("tutor-student dialogue contains SAM — wrong format")
    elif fmt == "dual-tutor":
        if "MAYA" in speakers:
            raise LLMError("dual-tutor dialogue contains MAYA — wrong format")
        expected = {"ALEX", "SAM"}
        if not expected.issubset(speakers):
            raise LLMError(f"dual-tutor dialogue missing speakers: {expected - speakers}")
```

Call `_validate_speakers(lines, fmt)` before caching and returning. If validation raises `LLMError`, it will be caught by the existing retry logic in `dialogue.py`.

---

### 1c. `tutor/prompts/dialogue.txt` — confirm dual-tutor instructions

Open `prompts/dialogue.txt` and verify the dual-tutor beat structure is described clearly. The prompt already has the structure from Day 1, but confirm these two things:
1. The 8-beat `dual-tutor` structure is present (see plan.md "Format 2: dual-tutor")
2. The instruction `"Output only labeled lines: ALEX: ... / MAYA: ... / SAM: ..."` correctly mentions SAM

If the prompt file is missing the dual-tutor beat structure, add it now. The dual-tutor beats from plan.md:

```
For dual-tutor format, use this 8-beat structure:
1. ALEX: State the concept and the standard rule
2. SAM: Probe — "but what about..." or "what I see people miss is..."
3. ALEX: Clarify or add nuance
4. SAM: Voice the beginner doubt — "so if I understand right..."
5. ALEX: Confirm + sharpen
6. SAM: Practical question — "when would you actually reach for this?"
7. ALEX: Answer with real-world context
8. SAM: Memory hook (SAM delivers it, feels more natural as a peer takeaway)
```

---

### 1d. Manual dual-tutor verification

After making the above changes:

```bash
python tutor/tutor.py sample_docs/java-basics.md --format dual-tutor --script-only
```

Check the output:
- Only `ALEX:` and `SAM:` lines (no `MAYA:`)
- SAM raises questions and probes; ALEX explains
- SAM delivers the memory hook at the end of each unit

Then:
```bash
python tutor/tutor.py sample_docs/java-basics.md --format dual-tutor --output dual-test.mp3
```

Listen to the output — confirm SAM's voice is audibly different from ALEX's.

---

## Part 2 — `--topic` Flag

### 2a. `tutor/generation/curriculum.py` — inject `--topic` (modify existing)

The `plan()` function needs a `topic: str | None = None` parameter.

If `topic` is set, prepend this line to the curriculum prompt before the section summaries:

```python
if topic:
    topic_instruction = (
        f'IMPORTANT: You must include a unit that covers the topic "{topic}". '
        "If the source document does not mention it, create a unit that acknowledges "
        "it is out of scope but explains why it matters in relation to what was covered."
    )
    prompt = topic_instruction + "\n\n" + prompt
```

Update `tutor.py` to pass `args.topic`:
```python
units = curriculum.plan(chunks, profile, args.duration, llm_fn, args.difficulty, args.topic)
```

---

## Part 3 — Tests

### 3a. `tutor/tests/ingestion/test_doc_analyzer.py` (~50 lines)

```python
import pytest
import os
from tutor.ingestion.doc_analyzer import analyze
from tutor.constants import STRATEGY_A_TOKEN_LIMIT, STRATEGY_B_TOKEN_LIMIT


def test_small_doc_strategy_a(tmp_path):
    doc = tmp_path / "small.md"
    doc.write_text("# Title\n\nShort content. " * 20)
    profile = analyze(str(doc))
    assert profile.strategy == "A"


def test_medium_doc_strategy_b(tmp_path):
    doc = tmp_path / "medium.md"
    # ~8000 words → ~10400 tokens → Strategy B
    doc.write_text("# Title\n\nContent word. " * 8_000)
    profile = analyze(str(doc))
    assert profile.strategy == "B"


def test_large_doc_strategy_c(tmp_path):
    doc = tmp_path / "large.md"
    # ~50000 words → ~65000 tokens → Strategy C
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
    with pytest.raises(Exception):
        analyze("/nonexistent/path/file.md")
```

---

### 3b. `tutor/tests/generation/test_curriculum.py` (~70 lines)

Tests use a fake `llm_fn` — no real LLM calls.

```python
import json
import pytest
from tutor.generation.curriculum import plan
from tutor.models import DocProfile, Chunk


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


GOOD_RESPONSE = json.dumps([
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
])


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
    # Unit 0 has complexity 3, Unit 1 has complexity 2
    # So unit 0 word budget should be 1.5× unit 1's
    ratio = units[0].word_budget / units[1].word_budget
    assert 1.4 <= ratio <= 1.6
```

---

## Part 4 — Code Quality Audit

Before calling Day 6 done, audit every file against the plan.md quality standards.

**Audit checklist (run through every file in `tutor/`):**

```
For each file:
  [ ] Line count ≤ 400 (run: wc -l <file> or check in editor)
  [ ] No function over 40 lines
  [ ] No bare except: clauses
  [ ] No print() calls outside tutor.py, inspector.py, player_display.py
  [ ] No os.environ reads outside config.py
  [ ] No magic numbers — all literals in constants.py
  [ ] All function signatures have type hints
  [ ] No comments explaining WHAT the code does (only WHY)
```

Common issues to fix on Day 6:

**`audio_builder.py`**: `_unit_duration_s()` likely calls pydub on every redraw (10 Hz). Move duration calculation to `_load_unit()` and cache in `self._current_unit_duration_s: int`.

**`tutor.py`**: check that `cmd_generate()` is under 40 lines. If not, extract `_run_inspect()`, `_run_dry_run()`, `_run_script_only()`, `_run_audio()` as private functions.

**`chunker.py`**: verify `_strategy_c` is under 40 lines. The sliding window logic is prone to growing large.

**`summarizer.py`**: check that Strategy A chunks skip the LLM call (return early with `chunk.text[:500]` as summary).

---

## Part 5 — End-to-End Verification

Work through every item in the MVP verification checklist from `plan.md`:

```
[ ] --inspect runs on sample_docs/java-basics.md with no errors
[ ] --dry-run shows 3–8 units with sensible Java concept names
[ ] --dry-run shows a duration estimate close to --duration target
[ ] --script-only produces ALEX:/MAYA: lines — no symbol leakage
[ ] Generated .mp3 plays in a media player without errors
[ ] Audio contains two distinct voices
[ ] The tutor asks a question, student answers incorrectly, tutor corrects — in every unit
[ ] The outro reads back memory hooks from all units
[ ] Re-running on the same file uses cached summaries (check .tutor_cache/)
[ ] Killing process mid-generation and re-running resumes from last completed unit
```

**Dual-tutor specific:**
```
[ ] --format dual-tutor --script-only shows only ALEX: and SAM: lines
[ ] --format dual-tutor --output dual.mp3 plays with two distinct voices (not MAYA's)
[ ] SAM delivers the memory hook at the end of each unit in dual-tutor
```

**Player:**
```
[ ] --play generates then immediately enters player
[ ] All keyboard commands work: space, n, b, r, s, ?, q
[ ] ? pauses audio and shows question prompt
[ ] Answer prints with source citation
[ ] tutorial.session.json created and updated after each question
[ ] --no-qa disables ? key
```

**Robustness:**
```
[ ] --provider openrouter works (requires OPENROUTER_API_KEY)
[ ] --difficulty intermediate changes word budgets vs --difficulty beginner
[ ] --no-cache clears cache and regenerates
[ ] --topic "concurrency" forces a concurrency unit in --dry-run output
[ ] Doc with no ## headings falls back to Strategy C with a warning
```

---

## Acceptance criteria

1. All items in the end-to-end verification checklist above are checked off

2. `cd tutor && python -m pytest tests/ -v` — all tests pass with no warnings

3. No file in `tutor/` exceeds 400 lines (verify with `wc -l tutor/**/*.py`)

4. `python tutor/tutor.py sample_docs/java-basics.md --format dual-tutor --play` — generates audio with ALEX + SAM voices and player launches

5. `python tutor/tutor.py sample_docs/java-basics.md --topic "HashMap internals" --dry-run` — curriculum plan includes a unit about HashMap

6. All test files run: `tests/audio/test_sanitizer.py`, `tests/ingestion/test_chunker.py`, `tests/ingestion/test_doc_analyzer.py`, `tests/generation/test_assembler.py`, `tests/generation/test_curriculum.py`, `tests/player/test_player_states.py`

---

## Gotchas

**SAM voice sounds similar to ALEX on some systems**: `en-US-GuyNeural` and `en-US-SaraNeural` are distinct voices from Microsoft. If they sound similar in your playback, confirm edge-tts is actually using both. Add a debug log: `log.debug("TTS: speaker=%s voice=%s rate=%s", line.speaker, voice, rate)` in `render_segment()` and run with `--debug`.

**Dual-tutor cache collision**: the dialogue cache key includes `fmt`. Changing from `tutor-student` to `dual-tutor` on the same unit will produce a different cache key, so a new LLM call is made. This is correct. Verify by checking `.tutor_cache/` — you should see separate `.dialogue.json` files for the two formats.

**Dialogue validator rejects valid SAM lines**: the regex in `_parse_dialogue_line()` looks for `ALEX|MAYA|SAM`. Confirm `SAM` is in the pattern. On Day 1, `SAM` may have been listed but not tested. Run `--format dual-tutor --script-only` and confirm SAM lines parse correctly.

**`test_curriculum.py` word budget ratio**: the test asserts `1.4 <= ratio <= 1.6` for complexity 3 vs complexity 2 (expected ratio 1.5). If difficulty multiplier is applied, the ratio might shift. The test uses no difficulty argument, so the default `"beginner"` (×1.3 multiplier) is applied uniformly to both units — the ratio remains 3:2 = 1.5. If this test fails, check that the multiplier is applied after the ratio is computed, not before.

**`wc -l` on Windows**: use `(Get-Content tutor/audio/audio_builder.py).Count` in PowerShell, or check line counts in your editor. The `wc` command is not available by default on Windows without Git Bash or WSL.

**`plan.md` says Phase 2 adds `--subject spring`**: do not implement this. Add a stub: if `args.subject` is not `"java"` or `"general"`, print a warning and proceed with `"general"`. This prevents a crash without building Phase 2.
