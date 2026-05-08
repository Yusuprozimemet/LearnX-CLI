# Day 1 — The Pipeline Speaks

## What works at the end of this day

```bash
python tutor/tutor.py sample_docs/java-basics.md --inspect
python tutor/tutor.py sample_docs/java-basics.md --dry-run
python tutor/tutor.py sample_docs/java-basics.md --script-only
```

The last command prints a full ALEX:/MAYA: dialogue to the terminal. No audio yet. The tutor AI is working — it reads a Java tutorial, selects concepts, and writes a Socratic dialogue. Audio comes on Day 2.

## Prerequisites

- Python 3.11+
- `GROQ_API_KEY` from console.groq.com (free)
- No other tools required today

## Project setup (do this first)

```bash
mkdir -p tutor/{ingestion,generation,infra,audio,player,qa,prompts,tests}
mkdir -p tutor/sample_docs tutor/.tutor_cache
cd tutor
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install openai groq python-dotenv markdown-it-py
```

Create `tutor/requirements.txt`:
```
openai>=1.0.0
groq>=0.9.0
edge-tts>=6.1.9
pydub>=0.25.1
pygame>=2.5.0
tqdm>=4.66.0
readchar>=4.0.0
python-dotenv>=1.0.0
markdown-it-py>=3.0.0
```

Create `tutor/.env` (never commit this):
```
GROQ_API_KEY=gsk_your_key_here
```

Create `tutor/.env.example`:
```
GROQ_API_KEY=gsk_...
OPENROUTER_API_KEY=sk-or-...
```

## Sample document

Create `tutor/sample_docs/java-basics.md` — this is your test input for all of Day 1 and 2. It must be real content, not lorem ipsum. Paste in any Java tutorial you have. If you don't have one, use this minimal version:

```markdown
# Java Fundamentals

## How the JVM Works

Java source code is compiled by `javac` into bytecode — `.class` files. The JVM
(Java Virtual Machine) loads and executes bytecode. This means Java is
"write once, run anywhere": the same `.class` file runs on any OS that has a JVM.

The JVM uses a JIT (Just-In-Time) compiler to convert hot bytecode paths into
native machine code at runtime. First execution is interpreted; repeated calls
get compiled to native for speed.

Memory is divided into the stack (local variables, method calls) and the heap
(objects). When you write `int x = 5`, x lives on the stack. When you write
`new Object()`, that object lives on the heap.

## Primitive vs Reference Types

Java has 8 primitive types: `int`, `long`, `double`, `float`, `boolean`,
`char`, `byte`, `short`. Primitives live on the stack and hold values directly.

Reference types (everything else) are objects. A variable of a reference type
holds a memory address — a pointer to where the object lives on the heap. The
variable is not the object; it points to the object.

## Pass-by-Value

Java is strictly pass-by-value. When you pass a variable to a method, Java
copies the value of that variable into the parameter. For primitives, this is
the actual number. For reference types, this is the memory address.

This means: reassigning a parameter inside a method does NOT affect the
caller's variable. But mutating the object via the reference (e.g., calling
`list.add()`) DOES affect the caller, because both the original and the copy
point to the same heap object.

## String Equality

Strings in Java are objects. The `==` operator compares references (memory
addresses), not content. Two String variables can hold the same text but be
different objects, so `==` returns `false`.

Use `.equals()` to compare String content:
```java
String a = new String("hello");
String b = new String("hello");
a == b        // false — different objects
a.equals(b)   // true — same content
```

String literals are interned: `"hello" == "hello"` may return `true` due to
the string pool. Do not rely on this. Always use `.equals()`.

## The final Keyword

`final` on a variable means the variable cannot be reassigned. It does NOT
make the object immutable.

```java
final List<String> names = new ArrayList<>();
names = new ArrayList<>();   // compile error — reassignment blocked
names.add("Alice");          // fine — mutation allowed
```

`final` on a method prevents overriding. `final` on a class prevents subclassing.

## Checked vs Unchecked Exceptions

Checked exceptions extend `Exception` directly. The compiler forces you to
either catch them or declare them in the method signature with `throws`.
Example: `IOException`, `SQLException`.

Unchecked exceptions extend `RuntimeException`. The compiler does not require
handling. Example: `NullPointerException`, `IllegalArgumentException`.

The rule: use checked exceptions for recoverable conditions the caller should
handle. Use unchecked for programming errors that should not occur.
```

---

## Files to create today

Build in this exact order. Each file depends on the ones before it.

### 1. `tutor/models.py` (~80 lines)

All dataclasses. No imports from this project. Copy directly from plan.md "Data Models" section. Every field must have a type annotation. Add `from __future__ import annotations` at the top for forward references.

Key point: `DialogueLine.unit_number` starts at 0 for intro lines, 1+ for unit lines, and -1 for outro lines.

### 2. `tutor/constants.py` (~50 lines)

Copy directly from plan.md "Constants" section. Add one additional constant today:

```python
PROMPT_VERSION = "v1"   # bump this when any prompt file changes
MAX_UNITS = 8
MIN_UNITS = 3
DEFAULT_DURATION_MIN = 20
DEFAULT_DIFFICULTY = "beginner"
DEFAULT_FORMAT = "tutor-student"
DEFAULT_SUBJECT = "java"
```

### 3. `tutor/exceptions.py` (~20 lines)

Copy directly from plan.md "Exception Hierarchy" section. Nothing else goes here.

### 4. `tutor/config.py` (~60 lines)

Reads `.env`, returns a typed `Config` dataclass, runs pre-flight checks.

Pre-flight checks to implement today (audio/player checks are Day 2/4):
- Input file exists and ends with `.md` — raise `ConfigError` with fix message
- `GROQ_API_KEY` is set if `provider == "groq"` — raise `ConfigError` with fix message
- Output parent directory is writable (skip if `--script-only` or `--dry-run` or `--inspect`)

Do NOT check for ffmpeg today — that's Day 2.

```python
@dataclass
class Config:
    groq_api_key: str = ""
    openrouter_api_key: str = ""
    default_provider: str = "groq"

def load_config() -> Config:
    load_dotenv()
    return Config(
        groq_api_key=os.getenv("GROQ_API_KEY", ""),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
    )

def preflight(input_path: str, provider: str, mode: str) -> Config:
    config = load_config()
    # run checks, raise ConfigError with actionable messages
    return config
```

### 5. `tutor/infra/__init__.py` (empty)

### 6. `tutor/infra/llm.py` (~150 lines)

This is the most important file today. Get it right.

Public interface:
```python
def chat(messages: list[dict], provider: str = "groq", call_type: str = "dialogue") -> str:
def parse_json_response(raw: str) -> any:
```

`chat()` implementation:
- Build the OpenAI client with the right `base_url` and `api_key` based on `provider`
- Select model from a dict: `MODEL_MAP = {("groq", "curriculum"): "llama-3.3-70b-versatile", ("groq", "dialogue"): "llama-3.1-8b-instant", ...}`
- Call `client.chat.completions.create(model=model, messages=messages, temperature=0.7)`
- On HTTP 429 or timeout: wait 2 seconds, retry once
- On second failure: raise `LLMError`
- Wrap all provider exceptions: `except Exception as e: raise LLMError(str(e)) from e`
- Return `response.choices[0].message.content`

`parse_json_response()` implementation: copy exactly from plan.md "LLM output validation" section. This is critical — free models break JSON regularly.

Groq client setup:
```python
from openai import OpenAI
client = OpenAI(
    api_key=config.groq_api_key,
    base_url="https://api.groq.com/openai/v1"
)
```

OpenRouter client setup:
```python
client = OpenAI(
    api_key=config.openrouter_api_key,
    base_url="https://openrouter.ai/api/v1",
    default_headers={"HTTP-Referer": "http://localhost"}
)
```

Note: `config` must be passed into `chat()` — don't call `load_config()` inside `llm.py`. Pass it from the caller or use dependency injection pattern. Add `config: Config` as a parameter.

### 7. `tutor/ingestion/__init__.py` (empty)

### 8. `tutor/ingestion/doc_analyzer.py` (~80 lines)

```python
def analyze(filepath: str) -> DocProfile:
```

Steps:
1. Read file text
2. `word_count = len(text.split())`
3. `estimated_tokens = int(word_count * 1.3)`
4. `strategy = "A" if estimated_tokens <= STRATEGY_A_TOKEN_LIMIT else "B" if estimated_tokens <= STRATEGY_B_TOKEN_LIMIT else "C"`
5. `section_count = len(re.findall(r'^#{1,3}\s', text, re.MULTILINE))`
6. `has_code_blocks = '```' in text`
7. `language_hint = "java" if '```java' in text.lower() else "general"`

No LLM calls. No side effects.

### 9. `tutor/ingestion/parse_content.py` (~80 lines)

```python
def enrich(chunk: Chunk) -> Chunk:
```

Populates `chunk.has_code` and extracts key terms. Returns the same chunk object (mutates in place is fine since Chunk is a dataclass, not frozen).

- `has_code`: `True` if chunk.text contains ` ``` `
- `key_terms`: list of strings found by `re.findall(r'\*\*(.+?)\*\*|`(.+?)`', chunk.text)`, flattened and deduped

### 10. `tutor/ingestion/chunker.py` (~250 lines)

```python
def chunk(text: str, profile: DocProfile) -> list[Chunk]:
```

Dispatch:
```python
if profile.strategy == "A":
    chunks = _strategy_a(text, profile)
elif profile.strategy == "B":
    chunks = _strategy_b(text, profile)
else:
    chunks = _strategy_c(text, profile)
return _apply_quality_rules(chunks, profile)
```

**`_strategy_a`**: return a single Chunk with the full text. `chunk_id = "full_doc"`.

**`_strategy_b`**: 
- Split on `^##` headings using `re.split(r'\n(?=## )', text)`
- No-headings fallback: if fewer than 2 splits, log WARNING and call `_strategy_c` instead
- For each section, create a Chunk with `chunk_id = slugify(heading)` (`re.sub(r'[^a-z0-9]+', '_', heading.lower())`)
- If a chunk exceeds `MAX_CHUNK_TOKENS`, split further at `###` boundaries
- Carry parent heading: prepend `"## {parent_heading}\n\n"` to H3 sub-chunks

**`_strategy_c`**: sliding window — skip today. Raise `NotImplementedError("Strategy C — implement on Day 3")`. Any doc that triggers it today gets a clear error message.

**`_apply_quality_rules`**:
- Merge chunks under `MIN_CHUNK_TOKENS` into the previous chunk
- Call `parse_content.enrich(chunk)` on every chunk
- Return cleaned list

### 11. `tutor/ingestion/summarizer.py` (~100 lines)

```python
def summarize_all(chunks: list[Chunk], llm_fn, cache_dir: str = SUMMARY_CACHE_DIR) -> list[Chunk]:
```

For each chunk:
1. Compute cache key: `hashlib.md5((chunk.text + PROMPT_VERSION).encode()).hexdigest()`
2. Check `{cache_dir}/{cache_key}.summary.txt`
3. If cache hit: set `chunk.summary = cached_text`; continue
4. Call `llm_fn` with the summarize prompt and chunk text
5. Save result to cache file
6. Set `chunk.summary`

`llm_fn` receives `messages: list[dict]`. Build the messages inside `summarize_all`:
```python
messages = [
    {"role": "system", "content": load_prompt("summarize.txt")},
    {"role": "user", "content": chunk.text}
]
```

For Strategy A chunks, set `chunk.summary = chunk.text[:500]` (no LLM call needed — it's small enough to use directly).

`load_prompt(name: str) -> str`: reads from `prompts/{name}`, relative to this file's directory. Add this helper to a shared location — either `infra/llm.py` or a tiny `prompts.py` utility file.

### 12. `tutor/generation/__init__.py` (empty)

### 13. `tutor/generation/curriculum.py` (~130 lines)

```python
def plan(chunks: list[Chunk], profile: DocProfile, duration_min: int, llm_fn) -> list[TeachingUnit]:
```

Steps:
1. Build summaries string: concatenate `f"[{c.chunk_id}] {c.summary}\n"` for all chunks
2. Load `prompts/curriculum.txt`, inject `{summaries}`, `{duration_min}`, `{difficulty}` (pass `difficulty` as parameter, default `"beginner"`)
3. Call `llm_fn(messages, call_type="curriculum")`
4. Call `parse_json_response(raw)` from `infra/llm.py`
5. Validate: must be a list, each item must have at least `concept`, `source_sections`, `complexity` keys
6. Compute word budgets: `base = (duration_min * WPM - OVERHEAD_WORDS) / sum(u["complexity"] for u in units)`
7. Convert each dict to a `TeachingUnit` dataclass
8. Return list

Error handling: if parsed result is not a list, or has 0 items, raise `LLMError("Curriculum planner returned no units")`.

### 14. `tutor/generation/dialogue.py` (~100 lines)

```python
def generate(unit: TeachingUnit, source_chunks: list[Chunk], fmt: str, llm_fn) -> list[DialogueLine]:
```

Cache check: compute `cache_key = MD5(unit.concept + str(unit.word_budget) + fmt + PROMPT_VERSION)`. Check `.tutor_cache/{cache_key}.dialogue.json`. If exists, load and return.

Build source content: join text of chunks whose `chunk_id` is in `unit.source_sections`.

Build messages:
```python
messages = [
    {"role": "system", "content": load_prompt("dialogue.txt").format(
        format=fmt,
        word_budget=unit.word_budget,
    )},
    {"role": "user", "content": f"Unit: {unit_json}\n\nSource:\n{source_text}"}
]
```

Call `llm_fn(messages, call_type="dialogue")`.

Parse response into `list[DialogueLine]`:
- Split by newline
- For each line, match `r"^(ALEX|MAYA|SAM)\s*[:\-]\s*(.+)"` (case-insensitive)
- Normalise speaker to uppercase
- Set `unit_number = unit.unit`
- Skip non-matching lines silently
- If fewer than 4 DialogueLine objects: raise `LLMError` for retry

Save to cache after successful parse. Return list.

### 15. `tutor/generation/assembler.py` (~150 lines)

```python
def assemble(units: list[TeachingUnit], all_lines: list[list[DialogueLine]], fmt: str, doc_title: str) -> list[DialogueLine]:
```

Pure function. No LLM calls.

1. Build intro lines (2–3 lines, templated):
   ```python
   intro_text = f"Today we're covering {doc_title}. By the end of this session, you'll understand {len(units)} concepts that Java developers regularly get wrong. Let's start with a question."
   DialogueLine(speaker="ALEX", text=intro_text, unit_number=0)
   ```

2. For each unit index `i`, append:
   - `all_lines[i]` (the unit dialogue)
   - If not last unit: a transition line `DialogueLine(speaker="ALEX", text="Now let's look at something related that catches people in a different way.", unit_number=units[i].unit)`

3. Build outro (pull `memory_hook` from all units):
   ```python
   hooks = ". ".join(u.memory_hook for u in units)
   outro_text = f"Before we finish — here are the things worth remembering. {hooks}. Keep those in mind next time you're reading Java code."
   DialogueLine(speaker="ALEX", text=outro_text, unit_number=-1)
   ```

4. Call `sanitizer.apply(line.text)` on every line (import `audio.sanitizer` — this creates a dependency from `generation` to `audio`, which is acceptable since sanitizer has no audio imports)

5. Return flat list

### 16. `tutor/audio/__init__.py` and `tutor/audio/sanitizer.py` (~60 lines)

Needed today because assembler.py calls it. Just the sanitizer — no TTS.

```python
import re
from tutor.constants import CODE_SUBSTITUTIONS

def apply(text: str) -> str:
    for pattern, replacement in CODE_SUBSTITUTIONS:
        text = re.sub(pattern, replacement, text)
    return text
```

Add `CODE_SUBSTITUTIONS` to `constants.py`:
```python
CODE_SUBSTITUTIONS = [
    (r"List<String>", "a List of Strings"),
    (r"HashMap<(\w+),\s*(\w+)>", r"a HashMap from \1 to \2"),
    (r"!=", "not equal to"),
    (r"(?<![=!<>])==(?![=])", "double equals"),
    (r"\.equals\(", "dot equals("),
    (r"@(\w+)", r"\1 annotation"),
    (r"(\w+)\[\]", r"\1 array"),
    (r"NullPointerException", "Null Pointer Exception"),
    (r"StackOverflowError", "Stack Overflow Error"),
    (r"IllegalArgumentException", "Illegal Argument Exception"),
]
```

### 17. `tutor/inspector.py` (~150 lines)

Two public functions:
```python
def report_ingestion(profile: DocProfile, chunks: list[Chunk]) -> None:
def report_curriculum(units: list[TeachingUnit], chunks: list[Chunk], duration_min: int) -> None:
```

`report_ingestion`: prints the ingestion report from plan.md "Ingestion Report" section. Use `print()` — this is a display module.

`report_curriculum`: prints the curriculum + duration breakdown from plan.md "Curriculum + Duration Report" section. Compute estimated time per unit: `unit.word_budget / WPM` seconds.

### 18. `tutor/prompts/` (4 files)

Create these exact files. Copy content from plan.md "Prompts (Key Design)" section.

`tutor/prompts/summarize.txt` — copy from plan.md  
`tutor/prompts/curriculum.txt` — copy from plan.md, but add these template variables that will be filled by curriculum.py:
```
Document title: {doc_title}
Target duration: {duration_min} minutes
Difficulty: {difficulty}
Student level description: {difficulty_context}

Section summaries:
{summaries}

Java concept map for reference:
[paste the Tier 0–6 map from plan.md here]
```

`tutor/prompts/dialogue.txt` — copy from plan.md  
`tutor/prompts/qa.txt` — copy from plan.md (not used until Day 5, but create now)

### 19. `tutor/tutor.py` (~150 lines)

CLI entry point only. No business logic.

```python
import argparse
import asyncio
import sys
from functools import partial

def main():
    parser = argparse.ArgumentParser(prog="tutor")
    subparsers = parser.add_subparsers(dest="command")

    # default command: generate
    gen = parser.add_argument_group("generate")
    parser.add_argument("input", nargs="?")
    parser.add_argument("--output", default="tutorial.mp3")
    parser.add_argument("--provider", default="groq")
    parser.add_argument("--duration", type=int, default=DEFAULT_DURATION_MIN)
    parser.add_argument("--format", default=DEFAULT_FORMAT)
    parser.add_argument("--difficulty", default=DEFAULT_DIFFICULTY)
    parser.add_argument("--units", type=int, default=None)
    parser.add_argument("--subject", default=DEFAULT_SUBJECT)
    parser.add_argument("--topic", default=None)
    parser.add_argument("--play", action="store_true")
    parser.add_argument("--script-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument("--show-summaries", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--debug", action="store_true")

    # play subcommand
    play_sub = subparsers.add_parser("play")
    play_sub.add_argument("audio_file")
    play_sub.add_argument("--provider", default="groq")
    play_sub.add_argument("--no-qa", action="store_true")

    args = parser.parse_args()
    _setup_logging(args)

    try:
        if args.command == "play":
            cmd_play(args)
        else:
            cmd_generate(args)
    except TutorError as e:
        print(f"\n✗ {e}", file=sys.stderr)
        sys.exit(1)

def cmd_generate(args):
    config = preflight(args.input, args.provider, _mode(args))
    llm_fn = partial(llm.chat, provider=args.provider, config=config)

    profile = doc_analyzer.analyze(args.input)
    chunks = chunker.chunk(open(args.input).read(), profile)

    if not args.inspect:  # summarizer needs LLM calls
        chunks = summarizer.summarize_all(chunks, llm_fn)

    if args.inspect:
        inspector.report_ingestion(profile, chunks)
        if args.show_summaries:
            for c in chunks:
                print(f"\n--- {c.chunk_id} ---\n{c.summary}")
        return

    units = curriculum.plan(chunks, profile, args.duration, llm_fn, args.difficulty)
    if args.units:
        units = units[:args.units]

    if args.dry_run:
        inspector.report_curriculum(units, chunks, args.duration)
        return

    all_lines = [dialogue.generate(u, chunks, args.format, llm_fn) for u in units]
    doc_title = Path(args.input).stem.replace("-", " ").replace("_", " ").title()
    script = assembler.assemble(units, all_lines, args.format, doc_title)

    if args.script_only:
        for line in script:
            print(f"{line.speaker}: {line.text}")
        return

    # Day 2: audio generation goes here
    print("Audio generation not yet implemented — use --script-only for now.")
```

## Acceptance criteria

Run these in order. Each must pass before moving to the next.

1. `python tutor/tutor.py --help` — shows usage, no import errors
2. `python tutor/tutor.py sample_docs/java-basics.md --inspect` — prints ingestion report, no errors
3. `python tutor/tutor.py sample_docs/java-basics.md --dry-run` — prints 3–8 units with Java concept names
4. `python tutor/tutor.py sample_docs/java-basics.md --script-only` — prints `ALEX:` / `MAYA:` lines
5. Kill the script-only run halfway, re-run — second run is faster (dialogue cache hit)
6. Open `.tutor_cache/` — see `.summary.txt` and `.dialogue.json` files present

## Gotchas

**Circular imports**: `assembler.py` imports `audio/sanitizer.py`. This is fine because `sanitizer.py` imports only from `constants.py`. If you get a circular import, check that no `audio` module imports from `generation`.

**LLM call volume on first run**: for a medium doc (~20 sections), Day 1 makes roughly: 20 summarize calls + 1 curriculum call + 5–8 dialogue calls = ~27 LLM calls. Groq free tier allows this easily. Each summarize call is fast (~1s on llama-3.1-8b). Total expected time: 2–4 minutes.

**Bad JSON from free models**: the `parse_json_response` function handles most cases. If you still get errors, check the raw LLM response by adding a `log.debug("Raw response: %s", raw)` in `llm.py` and running with `--debug`.

**`--script-only` output quality**: the first run will likely produce imperfect dialogue. The analogy may be weak, the student's wrong answer may not match the misconception exactly. This is normal — prompts are tuned in Day 3. The goal today is that the pipeline runs without errors.

**Windows paths**: use `pathlib.Path` everywhere, not string concatenation. `Path(args.input).stem` not `args.input.split("/")[-1].split(".")[0]`.
