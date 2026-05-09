# v1 — Explain Mode (`--explain`)

## What works at the end of this feature

```
LearnX > /generate week2/2.md --explain
LearnX > /generate week2/2.md --conversation          # explicit; same as current default
LearnX > /generate week2/2.md                         # unchanged — still conversation mode
```

The user can scroll through `week2/2.md` in their editor while LearnX reads it aloud
section by section, top to bottom. Each document heading becomes one audio unit. The
player, `/ask`, `/next`, `/prev`, `/replay`, `/summary`, `/video` — everything — works
exactly as before. No existing behaviour changes.

---

## Why this mode is different from conversation mode

| | Conversation (`--conversation`) | Explain (`--explain`) |
|---|---|---|
| Order | Concept-driven — LLM picks the trickiest ideas | Document-driven — follows heading order |
| Units | 3–8 selected concepts, may skip or reorder sections | One unit per `##` heading, nothing skipped |
| Format | ALEX + MAYA (or ALEX + SAM) dialogue | ALEX monologue only |
| Misconceptions | Central — each unit corrects one wrong belief | Not the focus — primary goal is coverage |
| Use case | Deep understanding of the hard parts | Read-along: scroll and listen in sync |
| LLM calls | summarize → curriculum plan → dialogue (per unit) | narrate (per section) — no curriculum step |

---

## Design decisions

### 1. Flag name: `--explain` / `--conversation`

`--format` already controls `tutor-student` vs `dual-tutor`. A separate orthogonal flag
controls the pipeline mode. The two flags are independent:

```
/generate week2/2.md --explain                         # explain mode, default voice (ALEX)
/generate week2/2.md --conversation                    # current mode, tutor-student
/generate week2/2.md --conversation --format dual-tutor  # current mode, dual-tutor
```

`--conversation` is not required to be typed — the default remains conversation mode
for backward compatibility. Adding `--explain` opts into the new pipeline.

### 2. Units = document sections, in order

The chunker already splits by `##` headings (Strategy B). Explain mode reuses this
directly. Every chunk becomes a unit, in the order they appear in the document. The
curriculum planning step (LLM concept selection) is **skipped entirely** — the document
structure is the curriculum.

For very large documents (Strategy C — sliding window), each window becomes one unit.
For Strategy A (whole document as one chunk), one narration unit is generated.

### 3. Single voice — ALEX monologue

No student character. ALEX speaks directly to the reader as if standing next to them
while they read the page. The tone is calm, clear, and sequential — not dramatic or
tension-building. Think: a teacher reading aloud with pauses to explain each idea.

### 4. New prompt: `narrate.txt`

A separate prompt template, not a modification of `dialogue.txt`. It receives:
- The section heading and raw text
- The word budget (proportional to section length)
- The document title and section position (`section N of M`)

It produces a spoken monologue for ALEX only. Code examples are translated to speech.
The narration references what the reader can *see on the page* ("the table above shows…",
"in this code block…") since the user is reading along.

### 5. Cache namespace is separate

Explain-mode dialogues are cached under a different key from conversation-mode
dialogues, so `--no-cache` on one mode does not invalidate the other.

### 6. Session naming

Explain-mode sessions are stored alongside conversation sessions in `audio/`. The
session directory name gets an `_explain` suffix so they are distinguishable in
`/sessions`:

```
audio/week2_2/           ← conversation session
audio/week2_2_explain/   ← explain session
```

`/sessions` shows both. The `[video]` badge and `/video` command work on explain
sessions the same way.

### 7. Word budget

Explain mode targets approximately **100–150 words per 100 words of source text** (a
spoken version is naturally shorter than the written text). The budget is computed from
the chunk word count, not from the `--duration` flag. `--duration` is ignored in
explain mode (the session length is determined by the document length).

---

## Pipeline changes

### No changes to existing modules

`chunker.py`, `summarizer.py`, `curriculum.py`, `dialogue.py`, `assembler.py`,
`audio_builder.py`, `tts_renderer.py`, `player.py` — all untouched.

### New file: `tutor/generation/narrator.py`

Responsible for the explain-mode pipeline. Replaces the summarize → curriculum → dialogue
chain with a single narrate call per chunk.

```python
def narrate(
    chunk: Chunk,
    section_index: int,
    total_sections: int,
    doc_title: str,
    llm_fn: LLMFn,
    cache_dir: str = SUMMARY_CACHE_DIR,
) -> list[DialogueLine]:
    """Generate a spoken narration for one document section."""
    ...
```

Returns `list[DialogueLine]` with `speaker="ALEX"` only, so the existing TTS renderer
and player work without modification.

Cache key includes `chunk.chunk_id + chunk.text + "explain_v1"`.

### New prompt: `tutor/prompts/narrate.txt`

```
You are ALEX, a calm and clear Java educator reading a tutorial aloud to a student
who is following along on screen.

Document: {doc_title}
Section: {heading} ({section_index} of {total_sections})
Word budget: approximately {word_budget} words

Your job: speak the content of this section aloud in natural English, top to bottom.
Rules:
- Follow the section order exactly. Do not reorder, skip, or jump ahead.
- Translate every code example into spoken English (no symbols).
- Reference what the reader can see: "the table above", "this code block", "the note here".
- Speak to the reader in second person ("you will notice…", "here you see…").
- Keep sentences short. Pause naturally at each concept.
- Do not add content that is not in the section. Do not quiz or correct misconceptions.
- Output only: ALEX: <spoken text>
  One ALEX: line per paragraph or logical block — not one giant line.

Source section:
{section_text}
```

### Changes to `tutor/cli/commands.py`

`_parse_generate_args()` adds `--explain` and `--conversation` flags (both optional,
mutually exclusive, default is conversation):

```python
mode_group = parser.add_mutually_exclusive_group()
mode_group.add_argument("--explain", action="store_true")
mode_group.add_argument("--conversation", action="store_true")
```

`cmd_generate()` reads `args.explain` and routes to the appropriate pipeline.

The session name gets `_explain` suffix when `args.explain` is True.

### Changes to `tutor/generation/assembler.py`

`assemble()` gets an optional `mode: str = "conversation"` parameter. In explain mode,
the intro and outro lines are shorter and do not reference "Java misconceptions" — they
simply say what document is being read and offer a brief closing recap of the sections
covered.

---

## New files

| File | Purpose |
|---|---|
| `tutor/generation/narrator.py` | Narrate pipeline: chunk → LLM → DialogueLine list |
| `tutor/prompts/narrate.txt` | ALEX monologue prompt |
| `tutor/tests/generation/test_narrator.py` | Unit tests for narrator (mocked LLM) |

## Modified files

| File | Change |
|---|---|
| `tutor/cli/commands.py` | Add `--explain` / `--conversation` flags; route to narrator pipeline |
| `tutor/generation/assembler.py` | `mode` parameter for explain-friendly intro/outro |

---

## Tests

`test_narrator.py` must cover:

1. `narrate()` returns only ALEX lines
2. `narrate()` returns at least 2 lines for a non-trivial chunk
3. Cache hit skips the LLM call
4. `--no-cache` flag clears the explain cache (separate from conversation cache)
5. Session directory gets `_explain` suffix

---

## What does NOT change

- `/play`, `/pause`, `/resume`, `/next`, `/prev`, `/replay`, `/ask`, `/summary` — unchanged
- `/video` works on explain sessions (slides from the narration units)
- `--difficulty`, `--format`, `--topic`, `--provider`, `--verbose`, `--debug` — all still
  valid with `--conversation`; ignored or not applicable with `--explain`
- `tutorial.units.json`, `tutorial.script.txt`, `tutorial.chunks.json` — same format
- The player state machine — unchanged

---

## Out of scope for this feature

- Syncing audio timestamps to document scroll position (requires a browser extension or editor plugin)
- Mixed sessions (some units explain, some converse)
- Per-paragraph granularity (unit = heading section is the right granularity for `/next`/`/prev`)
