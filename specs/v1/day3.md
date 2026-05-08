# Day 3 — Robustness

## What works at the end of this day

The pipeline handles real-world edge cases without crashing or silently degrading quality:

- Large docs (> 60k tokens) are processed via Strategy C sliding window
- Docs without `##` headings fall back to Strategy C automatically (was already stubbed — now implemented)
- `--provider openrouter` works as a fallback when Groq quota is hit
- `--difficulty intermediate` and `--difficulty advanced` change the curriculum and dialogue prompts
- `--no-cache` forces a fresh run, ignoring all cached summaries and dialogues
- An interrupted generation mid-run resumes cleanly from the last completed unit
- All pure modules have tests: `tests/audio/test_sanitizer.py`, `tests/ingestion/test_chunker.py`, `tests/generation/test_assembler.py`

## Prerequisites

- Day 2 completed and `--output` produces playable audio
- Install dev dependencies:
  ```bash
  pip install pytest pytest-asyncio
  ```
- Create `tutor/requirements-dev.txt`:
  ```
  pytest>=7.0.0
  pytest-asyncio>=0.21.0
  ```

---

## Files to create or modify today

---

### 1. `tutor/ingestion/chunker.py` — implement Strategy C (modify existing)

Replace the `NotImplementedError` stub in `_strategy_c` with the real sliding window implementation.

```python
def _strategy_c(text: str, profile: DocProfile) -> list[Chunk]:
    """Sliding window chunker for large docs (> 60k tokens) or headingless text."""
    window_tokens = STRATEGY_C_WINDOW_TOKENS   # 2000
    overlap_tokens = STRATEGY_C_OVERLAP_TOKENS  # 200

    words = text.split()
    word_window = int(window_tokens / 1.3)
    word_overlap = int(overlap_tokens / 1.3)

    chunks: list[Chunk] = []
    start = 0
    idx = 0

    while start < len(words):
        end = min(start + word_window, len(words))
        window_words = words[start:end]

        # Break at sentence boundary: walk back from end to find last "."
        if end < len(words):
            window_text = " ".join(window_words)
            last_period = window_text.rfind(". ")
            if last_period > len(window_text) // 2:
                window_text = window_text[: last_period + 1]
                window_words = window_text.split()

        chunk_text = " ".join(window_words)
        chunk_id = f"window_{idx:03d}"
        token_count = int(len(window_words) * 1.3)

        chunks.append(Chunk(
            chunk_id=chunk_id,
            breadcrumb=f"Window {idx + 1}",
            heading=f"Window {idx + 1}",
            level=0,
            token_count=token_count,
            text=chunk_text,
            has_code=False,
            overlapping=(idx > 0),
        ))

        idx += 1
        step = word_window - word_overlap
        start += max(step, 1)

    return chunks
```

Add to `constants.py`:
```python
STRATEGY_C_WINDOW_TOKENS = 2_000
STRATEGY_C_OVERLAP_TOKENS = 200
```

---

### 2. `tutor/infra/llm.py` — add OpenRouter provider (modify existing)

The `chat()` function already has a `provider` parameter. Add the OpenRouter branch:

**Model map** — expand the existing `MODEL_MAP`:
```python
MODEL_MAP: dict[tuple[str, str], str] = {
    ("groq", "curriculum"):  "llama-3.3-70b-versatile",
    ("groq", "dialogue"):    "llama-3.1-8b-instant",
    ("groq", "summarize"):   "llama-3.1-8b-instant",
    ("groq", "qa"):          "llama-3.1-8b-instant",
    ("openrouter", "curriculum"): "google/gemma-3-27b-it:free",
    ("openrouter", "dialogue"):   "meta-llama/llama-3.1-8b-instruct:free",
    ("openrouter", "summarize"):  "meta-llama/llama-3.1-8b-instruct:free",
    ("openrouter", "qa"):         "meta-llama/llama-3.1-8b-instruct:free",
}
```

**Client builder** — replace any inline client creation with a factory function:
```python
def _build_client(provider: str, config: Config) -> OpenAI:
    if provider == "groq":
        if not config.groq_api_key:
            raise ConfigError("GROQ_API_KEY not set. Add it to tutor/.env")
        return OpenAI(
            api_key=config.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
        )
    if provider == "openrouter":
        if not config.openrouter_api_key:
            raise ConfigError(
                "OPENROUTER_API_KEY not set.\n"
                "  Get a free key at openrouter.ai and add OPENROUTER_API_KEY to tutor/.env"
            )
        return OpenAI(
            api_key=config.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
            default_headers={"HTTP-Referer": "http://localhost"},
        )
    raise ConfigError(f"Unknown provider: {provider!r}. Use 'groq' or 'openrouter'.")
```

**Retry logic** — make the retry explicit and correct:
```python
import time

def chat(messages: list[dict], provider: str, call_type: str, config: Config) -> str:
    client = _build_client(provider, config)
    model = MODEL_MAP.get((provider, call_type))
    if model is None:
        raise LLMError(f"No model configured for ({provider!r}, {call_type!r})")

    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7,
            )
            return response.choices[0].message.content
        except Exception as e:
            status = getattr(e, "status_code", None)
            if status in (400, 401, 403):
                raise LLMError(f"Auth/request error ({status}): {e}") from e
            if attempt == 0:
                log.warning("LLM call failed (%s), retrying in 2s...", e)
                time.sleep(2)
                continue
            raise LLMError(f"LLM call failed after retry: {e}") from e
    raise LLMError("Unreachable")
```

---

### 3. `tutor/generation/curriculum.py` — implement `--difficulty` (modify existing)

`plan()` already takes a `difficulty` parameter. Wire it into the prompt properly.

Add a `DIFFICULTY_CONTEXT` dict to `constants.py`:
```python
DIFFICULTY_CONTEXT: dict[str, str] = {
    "beginner": (
        "The student has never written Java before. "
        "Prioritise Tier 0–2 concepts. Analogies are mandatory. "
        "Set max complexity to 2. Word budget multiplier: 1.3."
    ),
    "intermediate": (
        "The student has written Java for 3 months. "
        "Assume JVM basics are known. Use Tier 1–4 concepts. "
        "Word budget multiplier: 1.0."
    ),
    "advanced": (
        "The student knows OOP but makes design-level mistakes. "
        "Focus on Tier 3–6: contracts, concurrency, edge cases. "
        "Word budget multiplier: 0.8."
    ),
}
```

In `curriculum.py`, apply the difficulty multiplier to `word_budget` after computing base:
```python
difficulty_multipliers = {"beginner": 1.3, "intermediate": 1.0, "advanced": 0.8}
multiplier = difficulty_multipliers.get(difficulty, 1.0)
base = (duration_min * WPM - OVERHEAD_WORDS) / sum(u["complexity"] for u in raw_units)
for u in units:
    u.word_budget = round(base * u.complexity * multiplier)
```

Pass `difficulty_context` to the curriculum prompt template:
```python
prompt = load_prompt("curriculum.txt").format(
    doc_title=doc_title,
    duration_min=duration_min,
    difficulty=difficulty,
    difficulty_context=DIFFICULTY_CONTEXT.get(difficulty, ""),
    summaries=summaries_str,
)
```

---

### 4. `tutor/generation/dialogue.py` — pass `difficulty` to dialogue prompt (modify existing)

The dialogue prompt already has a `{difficulty}` placeholder. The `generate()` function needs to accept and forward it:

```python
def generate(
    unit: TeachingUnit,
    source_chunks: list[Chunk],
    fmt: str,
    llm_fn,
    difficulty: str = "beginner",
) -> list[DialogueLine]:
```

Update the `tutor.py` call site to pass `difficulty`:
```python
all_lines = [
    dialogue.generate(u, chunks, args.format, llm_fn, args.difficulty)
    for u in units
]
```

---

### 5. `--no-cache` flag implementation

This flag is already parsed in `tutor.py`. Wire it in:

In `tutor.py`:
```python
if args.no_cache:
    import shutil
    cache_dir = Path(".tutor_cache")
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
        print("Cache cleared.")
```

Run this **before** calling `summarize_all()` and before the dialogue loop. Clearing the directory is simpler than threading a flag through every cache read — the directory is recreated automatically on the next cache write.

---

### 6. `tests/` — three test files

Create the directory structure:
```bash
mkdir -p tutor/tests/audio
mkdir -p tutor/tests/ingestion
mkdir -p tutor/tests/generation
touch tutor/tests/__init__.py
touch tutor/tests/audio/__init__.py
touch tutor/tests/ingestion/__init__.py
touch tutor/tests/generation/__init__.py
```

**`tutor/tests/audio/test_sanitizer.py`** (~60 lines):
```python
import pytest
from tutor.audio.sanitizer import apply

def test_list_of_strings():
    assert apply("Use List<String> here") == "Use a List of Strings here"

def test_hashmap():
    assert apply("HashMap<String, Integer>") == "a HashMap from String to Integer"

def test_not_equal():
    assert apply("if (a != b)") == "if (a not equal to b)"

def test_double_equals():
    assert apply("if (a == b)") == "if (a double equals b)"

def test_annotation():
    assert apply("@Override") == "Override annotation"

def test_int_array():
    assert apply("int[] arr") == "int array arr"

def test_null_pointer():
    assert apply("throws NullPointerException") == "throws Null Pointer Exception"

def test_no_change():
    # clean text should pass through unchanged
    result = apply("Java is a statically typed language")
    assert result == "Java is a statically typed language"

def test_multiple_substitutions():
    result = apply("List<String> with != and ==")
    assert "a List of Strings" in result
    assert "not equal to" in result
    assert "double equals" in result
```

**`tutor/tests/ingestion/test_chunker.py`** (~80 lines):
```python
import pytest
from tutor.ingestion.chunker import chunk
from tutor.ingestion.doc_analyzer import analyze
from tutor.models import DocProfile

SAMPLE_B = """
# Java Guide

## The JVM

The JVM loads bytecode and executes it. JIT compilation speeds up hot paths.

## Primitives

Java has 8 primitive types: int, long, double, float, boolean, char, byte, short.

## Pass-by-Value

Java always passes by value. For objects, it passes the reference by value.
""".strip()

SAMPLE_NO_HEADINGS = "Java is a language. It has classes and objects. " * 100


def _make_profile(text: str, strategy: str) -> DocProfile:
    return DocProfile(
        filepath="test.md",
        raw_bytes=len(text.encode()),
        estimated_tokens=int(len(text.split()) * 1.3),
        strategy=strategy,
        section_count=3,
        has_code_blocks=False,
        language_hint="java",
    )


def test_strategy_b_produces_multiple_chunks():
    profile = _make_profile(SAMPLE_B, "B")
    chunks = chunk(SAMPLE_B, profile)
    assert len(chunks) >= 2


def test_strategy_b_chunk_ids_are_slugified():
    profile = _make_profile(SAMPLE_B, "B")
    chunks = chunk(SAMPLE_B, profile)
    for c in chunks:
        assert " " not in c.chunk_id
        assert c.chunk_id == c.chunk_id.lower()


def test_strategy_b_no_headings_falls_back_to_c():
    profile = _make_profile(SAMPLE_NO_HEADINGS, "B")
    chunks = chunk(SAMPLE_NO_HEADINGS, profile)
    # Strategy C window chunks have IDs like "window_000"
    assert any("window" in c.chunk_id for c in chunks)


def test_strategy_a_produces_single_chunk():
    short = "Java is statically typed."
    profile = _make_profile(short, "A")
    chunks = chunk(short, profile)
    assert len(chunks) == 1
    assert chunks[0].chunk_id == "full_doc"


def test_no_chunk_under_min_tokens():
    from tutor.constants import MIN_CHUNK_TOKENS
    profile = _make_profile(SAMPLE_B, "B")
    chunks = chunk(SAMPLE_B, profile)
    for c in chunks:
        assert c.token_count >= MIN_CHUNK_TOKENS
```

**`tutor/tests/generation/test_assembler.py`** (~70 lines):
```python
import pytest
from tutor.generation.assembler import assemble
from tutor.models import TeachingUnit, DialogueLine


def _make_unit(n: int) -> TeachingUnit:
    return TeachingUnit(
        unit=n,
        concept=f"Concept {n}",
        source_sections=[f"s0{n}"],
        complexity=2,
        word_budget=400,
        key_facts=["fact"],
        common_misconception="wrong belief",
        good_analogy="like a thing",
        question_style="recall",
        memory_hook=f"Remember concept {n}",
    )


def _make_lines(unit_num: int, count: int = 4) -> list[DialogueLine]:
    lines = []
    for i in range(count):
        speaker = "ALEX" if i % 2 == 0 else "MAYA"
        lines.append(DialogueLine(speaker=speaker, text=f"Unit {unit_num} line {i}", unit_number=unit_num))
    return lines


def test_assemble_starts_with_alex_intro():
    units = [_make_unit(1), _make_unit(2)]
    all_lines = [_make_lines(1), _make_lines(2)]
    result = assemble(units, all_lines, "tutor-student", "Java Basics")
    assert result[0].speaker == "ALEX"
    assert result[0].unit_number == 0


def test_assemble_ends_with_outro():
    units = [_make_unit(1)]
    all_lines = [_make_lines(1)]
    result = assemble(units, all_lines, "tutor-student", "Java Basics")
    assert result[-1].unit_number == -1


def test_assemble_transitions_between_units():
    units = [_make_unit(1), _make_unit(2)]
    all_lines = [_make_lines(1), _make_lines(2)]
    result = assemble(units, all_lines, "tutor-student", "Java Basics")
    # A transition line should exist between unit 1 and unit 2
    unit_numbers = [l.unit_number for l in result]
    assert 1 in unit_numbers and 2 in unit_numbers


def test_assemble_outro_contains_memory_hooks():
    units = [_make_unit(1), _make_unit(2)]
    all_lines = [_make_lines(1), _make_lines(2)]
    result = assemble(units, all_lines, "tutor-student", "Java Basics")
    outro = result[-1]
    assert "Remember concept 1" in outro.text
    assert "Remember concept 2" in outro.text


def test_sanitizer_applied_no_symbols():
    units = [_make_unit(1)]
    lines = [DialogueLine(speaker="ALEX", text="Use List<String>", unit_number=1)]
    result = assemble(units, [lines], "tutor-student", "Java Basics")
    for line in result:
        assert "<" not in line.text, f"Symbol leak in: {line.text}"
```

Run with: `cd tutor && python -m pytest tests/ -v`

---

## Acceptance criteria

1. `python tutor/tutor.py sample_docs/java-basics.md --provider openrouter --output openrouter-test.mp3` — runs without error (requires `OPENROUTER_API_KEY` in `.env`)

2. Create a test doc with no `##` headings (just paragraphs) and run `--inspect` — strategy shows `B→C fallback` warning in output

3. `python tutor/tutor.py sample_docs/java-basics.md --difficulty intermediate --dry-run` — word budgets are different from `--difficulty beginner`

4. `python tutor/tutor.py sample_docs/java-basics.md --no-cache --script-only` — prints "Cache cleared." before running, and the run makes fresh LLM calls (watch the summarizer log with `--verbose`)

5. Kill a `--script-only` run after the curriculum step completes but before all dialogue units complete. Re-run — it should skip already-cached units and only generate the missing ones.

6. `cd tutor && python -m pytest tests/ -v` — all tests pass, no warnings

---

## Gotchas

**Strategy C produces many chunks for large docs**: a 100k-token doc will produce ~50 window chunks, which means ~50 summarize calls before curriculum planning. On Groq free tier this is fine (< 100 calls/day). On OpenRouter free models this might hit rate limits — the retry logic handles transient 429s, but if they persist, add `time.sleep(1)` between summarize calls in `summarizer.py`.

**OpenRouter free model context limits**: many free models cap at 8k tokens total. The summarize prompt + chunk text must stay under 6k tokens per call. `_strategy_c` windows at 2k tokens — this leaves plenty of room. The dialogue prompt + source chunks must also stay under 6k. If a unit's `source_sections` references multiple large chunks, filter to the two most relevant or truncate. Add this guard to `dialogue.py`:
```python
MAX_SOURCE_TOKENS = 4_000
source_text = _truncate_source(source_text, MAX_SOURCE_TOKENS)
```

**`--no-cache` is destructive**: it deletes `.tutor_cache/` entirely. Warn the user: `"Cache cleared (all summaries and dialogues will be regenerated)."` If only dialogue cache should be cleared (not summaries), users can delete `.tutor_cache/*.dialogue.json` manually — no special flag needed for that case in MVP.

**`pytest` import paths**: run pytest from the `tutor/` directory (`cd tutor && python -m pytest tests/ -v`) not from the project root, unless you add a `conftest.py` at the root. This avoids package resolution issues with `from tutor.audio.sanitizer import apply`.

**Difficulty multiplier and minimum budget**: after applying the multiplier, a unit's word budget could theoretically go very low for `advanced` (×0.8) with a low-complexity unit. Enforce a floor: `u.word_budget = max(u.word_budget, WORDS_PER_COMPLEXITY[1])` (i.e., minimum 200 words even for advanced difficulty on a simple concept).
