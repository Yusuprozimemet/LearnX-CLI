# Tutor AI — Implementation Plan

## Goal

A CLI tool that reads Java/backend tutorial `.md` files and produces an educational audio session — a Socratic tutor-student dialogue that builds genuine understanding, not an overview. Designed specifically for Java learners: uses code-grounded analogies, catches the misconceptions Java beginners actually make, and keeps the student actively recalling rather than passively listening.

**Early development uses only free services:** Groq (free tier) and OpenRouter (free models) for LLM inference, `edge-tts` for audio. No paid APIs until the pipeline is validated end-to-end.

---

## MVP Scope

The plan describes the full system. The MVP is a strict subset. Do not build Phase 2 features during MVP. Do not build the player before the generator is proven.

### MVP: what must work

```
python tutor/tutor.py <input.md> --inspect          → ingestion report, no LLM calls
python tutor/tutor.py <input.md> --dry-run          → curriculum plan printed to terminal
python tutor/tutor.py <input.md> --script-only      → full dialogue script printed
python tutor/tutor.py <input.md> --output out.mp3   → audio file generated and playable
```

That is the entire MVP. One command, one `.md` file, one `.mp3` output.

### MVP: what is explicitly deferred

- `--play` flag and `player/` package — deferred until generation is validated
- Q&A engine (`qa/`) — deferred until player works
- `dual-tutor` format — deferred; implement `tutor-student` only
- `--difficulty` flag — deferred to post-MVP (see below)
- `--subject` flag beyond `java` — deferred
- `--topic` force-include flag — deferred
- OpenRouter provider — deferred until Groq is working; keep the abstraction but don't test both

### Build order for MVP

```
Step 0  Pre-flight checks (fast, no LLM)
Step 1  Foundation: models, constants, exceptions, config
Step 2  infra/llm.py (Groq only first)
Step 3  ingestion/ (pure functions, no LLM) → verify with --inspect
Step 4  generation/curriculum.py → verify with --dry-run
Step 5  generation/dialogue.py + assembler.py → verify with --script-only
Step 6  audio/ → verify with --output
Step 7  player/ + qa/ → add interactivity
Step 8  OpenRouter fallback, dual-tutor, difficulty, topic flags
```

Stop at Step 6. Test the audio. Listen to it. Only then continue.

### MVP verification checklist

Before calling MVP done, verify each item manually:

- [ ] `--inspect` runs on `sample_docs/java-basics.md` with no errors
- [ ] `--dry-run` shows 3–8 units with sensible Java concept names
- [ ] `--dry-run` shows a duration estimate close to `--duration` target
- [ ] `--script-only` produces labelled `ALEX:` / `MAYA:` lines — no symbol leakage
- [ ] Generated `.mp3` plays in a media player without errors
- [ ] Audio contains two distinct voices
- [ ] The tutor asks a question, the student answers incorrectly, the tutor corrects — in every unit
- [ ] The outro reads back the memory hooks from all units
- [ ] Re-running on the same file uses cached summaries (check `.tutor_cache/`)
- [ ] Killing the process mid-generation and re-running resumes from the last completed unit

---

## What Makes This Different from NotebookLM

| NotebookLM | This tutor |
|---|---|
| Two hosts give an overview | Tutor asks, student answers |
| Listener is passive | Forces recall and reasoning |
| Covers breadth | Drills depth per concept |
| Summary of what the doc says | Builds a mental model from scratch |
| One-shot audio | Re-run at different difficulty |

---

## Teaching Philosophy for Java / Backend

The tutor is not a narrator. It is a patient but no-nonsense senior engineer who:

1. **Anchors abstractions in code reality** — never explains `interface` without showing what calling code looks like; never explains the heap without asking "so where does a local `int` live?"
2. **Surfaces the "why" before the "what"** — explains *why* Java is statically typed before listing syntax rules; explains *why* `ArrayList` and `LinkedList` exist before asking which to use
3. **Uses the confusion students actually have**, not invented wrong answers:
   - Thinking `==` compares String content
   - Assuming constructors are inherited
   - Believing `final` makes an object immutable
   - Confusing method overloading with overriding
   - Not understanding that interfaces can have default methods since Java 8
4. **Uses grounded analogies** that map cleanly to backend/Java reality:
   - JVM = a universal translator that converts bytecode to machine instructions at runtime
   - Garbage collector = a janitor who only cleans up rooms nobody has a key to anymore
   - Interface = a contract (job description); class = the actual employee
   - `synchronized` = a bathroom with one lock — only one thread can be inside
   - Stack vs. heap = sticky notes on your desk (stack) vs. a shared whiteboard (heap)
5. **Varies the question style** across units so the student cannot coast:
   - "What is X?" (recall)
   - "What's wrong with this code?" (error spotting)
   - "Which would you choose and why?" (judgment)
   - "Predict the output" (trace execution)
   - "How would you explain this to a junior?" (teach-back)

---

## Architecture

```
.md file(s)  [Java tutorial docs]
    │
    ▼
[1] Document Analyzer       (doc_analyzer.py)
    │   profile doc: token count, section map, size class
    │   choose ingestion strategy: full / section / chunked
    ▼
[2] Chunker                 (chunker.py)
    │   split doc into labelled chunks based on strategy
    │   each chunk carries: heading path, token count, raw text
    ▼
[3] Summarizer              (summarizer.py)
    │   LLM call per section → 80-word summary
    │   used by curriculum planner (always fits in context)
    │   original chunks retained for dialogue generation
    ▼
[4] Curriculum Planner      (curriculum.py)
    │   input: all section summaries + doc profile + duration target
    │   identify teaching units, assign complexity scores
    │   compute word budget per unit
    │   each unit references source_sections[] by chunk ID
    ▼
[5] Dialogue Generator      (dialogue.py)
    │   input: unit JSON (incl. word_budget) + source chunks
    │   format: tutor-student OR dual-tutor (--format flag)
    │   output: labelled script lines within word budget
    ▼
[6] Script Assembler        (assembler.py)
    │   join unit scripts with intro, transitions, outro
    │   compute estimated audio duration
    │   emit final script file (optional --script-only)
    ▼
[7] TTS Renderer            (tts.py — edge-tts)
    │   async batch: render all segments in parallel
    │   insert natural pauses (turn / unit / session boundaries)
    │   show progress bar during generation
    │   save: tutorial.mp3 (full) + units/ (per-unit files)
    ▼
[8] Audio Output
    │   tutorial.mp3              full session audio
    │   tutorial_units/
    │     unit_01_intro.mp3
    │     unit_02_jvm.mp3         one file per teaching unit
    │     ...
    │   tutorial.script.txt       full dialogue script
    │   tutorial.units.json       curriculum + timing offsets
    │
    ├── (non-interactive) done
    │
    └── --play flag
        ▼
[9] Interactive Player      (player.py)
    │   plays unit files sequentially via pygame
    │   live status bar: unit name, position, commands
    │   state machine: PLAYING ↔ PAUSED ↔ ASKING
    │   background thread: audio  |  main thread: input
    ▼
[10] Q&A Engine             (qa.py)
    │   student types a question while audio is paused
    │   context: current unit chunks + session Q&A history
    │   LLM call → text answer (no audio generated)
    │   saves to tutorial.session.json
    ▼
[11] Session Log            tutorial.session.json
     all questions + answers from this listening session

    │ (parallel output)
    ▼
[12] Ingestion + Duration Report   (--inspect / --dry-run)
     coverage %, orphaned sections, token usage,
     estimated duration, word budget breakdown
```

---

## Dialogue Length and Duration

This is the core design question. Length is not fixed — it is **derived from three inputs in priority order**:

### 1. Target Duration (`--duration`, minutes)

The primary control. Default is 20 minutes. The pipeline works backwards from this:

```
target_minutes × 130 WPM = total_word_budget
```

130 words per minute is the calibrated rate for educational conversational speech at edge-tts default rate. This is slightly slower than casual conversation (150 WPM) because the tutor pauses to let code examples land.

| Target | Word budget | Typical unit count |
|---|---|---|
| 10 min | 1,300 words | 3–4 units |
| 20 min | 2,600 words | 5–8 units |
| 30 min | 3,900 words | 8–12 units |
| 45 min | 5,850 words | 12–16 units |
| 60 min | 7,800 words | 16–20 units |

The word budget is split across units. It does **not** include intro, transitions, and outro — those are fixed overhead (~200 words total regardless of duration).

### 2. Content Richness (hard ceiling)

The doc sets a ceiling on how long the audio *can* be, regardless of `--duration`.

The curriculum planner counts how many teachable concepts exist in the doc. Each concept needs a minimum word floor to be taught properly:

| Concept complexity | Min words needed | What it means |
|---|---|---|
| Simple (1 fact, 1 rule) | 200 words | ~1.5 min |
| Medium (analogy + code + correction) | 380 words | ~3 min |
| Complex (code trace, multi-step, edge case) | 580 words | ~4.5 min |

If the doc only supports 3 simple concepts, the maximum meaningful audio is ~600 words (~5 min). Requesting `--duration 30` on a thin doc will produce either repetition or padding — the system detects this and warns:

```
⚠ Content ceiling: this document supports a maximum of ~8 min of quality dialogue
  (3 teachable concepts found, estimated max 1,040 words).
  Requested duration: 20 min.
  Options:
    --units 3             generate all concepts, shorter session
    --difficulty beginner  expand each concept with more scaffolding (~12 min)
    provide a richer source document
```

### 3. Concept Complexity (word budget distribution)

The total word budget is not split equally across units. Each unit in the curriculum plan carries a `complexity` score (1–3) assigned by the planner. Budget is distributed proportionally:

```
words_per_complexity_point = total_word_budget / sum(all complexity scores)
unit_word_budget = unit.complexity × words_per_complexity_point
```

**Example: 20 min session, 6 units**

Total budget: 2,600 words

| Unit | Concept | Complexity | Word budget | Est. duration |
|---|---|---|---|---|
| 1 | What is the JVM | 1 | 260 words | 2 min |
| 2 | Pass-by-value trap | 3 | 780 words | 6 min |
| 3 | String == vs equals | 2 | 520 words | 4 min |
| 4 | final ≠ immutable | 2 | 520 words | 4 min |
| 5 | Checked exceptions | 2 | 520 words | 4 min |
| **Total** | | **10 pts** | **2,600 words** | **20 min** |

The `word_budget` field is passed directly to the dialogue generator in the prompt: "Write this dialogue in approximately N words."

### Duration Estimation Before Audio Generation

After script assembly but before TTS, the system prints an estimate:

```
=== Duration Estimate ===
Total script words:   2,587
Speaking rate:        130 WPM
Dialogue duration:    ~19m 54s
Silence overhead:     ~1m 20s  (turn pauses + unit breaks + intro/outro)
Estimated total:      ~21m 14s

Breakdown by unit:
  Intro              0m 45s
  Unit 1 (JVM)       2m 05s
  Unit 2 (pass-by)   6m 10s
  Unit 3 (strings)   4m 02s
  Unit 4 (final)     3m 58s
  Unit 5 (excs)      4m 01s
  Outro              0m 33s
  ─────────────────────────
  Total              21m 34s
```

---

## Conversation Format

Two formats selectable via `--format`. Both use a man's voice and a woman's voice, but the dynamic is different.

### Format 1: `tutor-student` (default)

Best for: beginners and early intermediates who need concepts explained before they can reason about them.

- **ALEX** (man, `en-US-GuyNeural`) — the tutor. Senior engineer. Explains using analogies, asks Socratic questions, corrects misconceptions firmly but without condescension.
- **MAYA** (woman, `en-US-JennyNeural`) — the student. Motivated, asks real questions, makes the exact wrong assumption beginners make. Not artificially dumb — she reasons, just from an incomplete model.

Dynamic: ALEX leads. Every beat is: explain → question → Maya gets it partially wrong → ALEX pushes back with a code clue → Maya corrects → ALEX adds the gotcha → memory hook.

```
ALEX: Here's a question before I explain anything — if you pass an object into
      a method and reassign the parameter inside, does the caller's variable change?
MAYA: I think yes? Because objects are passed by reference in Java.
ALEX: That's the most common answer, and it's almost right, which makes it
      dangerous. Java does pass a reference — but it passes it by value.
      There's a difference. Think of it this way: ...
```

### Format 2: `dual-tutor`

Best for: intermediate learners who already have the basic model and want to hear how engineers think about tradeoffs, edge cases, and real decisions.

- **ALEX** (man, `en-US-GuyNeural`) — the explainer. Lays out the concept, the rule, the standard case.
- **SAM** (woman, `en-US-SaraNeural`) — the challenger. Pushes on edge cases, asks "but what about...", voices the doubt a smart beginner would have, adds the practical perspective ("when would you actually use this?").

Dynamic: collaborative, not hierarchical. SAM does not make obvious mistakes — she raises real complexity. The listener hears two smart people working through the same thing they're trying to learn.

```
ALEX: So HashMap uses hashCode to decide which bucket to put an entry in.
      That's why two equal keys that return different hash codes will break the map.
SAM:  Right, but here's what I always find people miss — it's not just about
      overriding equals. You can override equals perfectly and still get silent
      bugs if hashCode isn't consistent. What's the actual rule?
ALEX: The contract is: if a.equals(b) is true, then a.hashCode() must equal
      b.hashCode(). The reverse doesn't have to hold — two different objects
      can return the same hash code. That's a collision, not a bug.
SAM:  So the question to ask a candidate is: "what happens if you put a mutable
      object in a HashMap and then change the field you used in hashCode?"
```

### Voice & Rate Settings

| Speaker | Voice | Rate | Role |
|---|---|---|---|
| ALEX (tutor / explainer) | `en-US-GuyNeural` | `+0%` (default) | Deliberate, clear |
| MAYA (student) | `en-US-JennyNeural` | `+5%` (slightly faster) | Natural, casual questioning |
| SAM (co-tutor) | `en-US-SaraNeural` | `+0%` | Confident, probing |

The slight rate difference between ALEX and MAYA creates natural contrast — ALEX slows down to make a point, MAYA responds at a quicker conversational pace. Do not exaggerate this; `+5%` is the maximum difference.

### Format-Specific Beat Structures

**tutor-student beat structure (9 beats):**
1. ALEX — Hook: question before any explanation
2. ALEX — Analogy: ground the concept in 2 sentences
3. ALEX — Explain: one concise factual explanation tied to the analogy
4. ALEX — Question (style from curriculum unit)
5. MAYA — Wrong/partial answer (must match `common_misconception`)
6. ALEX — Code contrast or hint (spoken as English)
7. MAYA — Corrected answer
8. ALEX — Confirm + gotcha (one surprising edge case)
9. ALEX — Memory hook + bridge to next unit

**dual-tutor beat structure (8 beats):**
1. ALEX — State the concept and the standard rule
2. SAM — Probe: "but what about..." or "what I see people miss is..."
3. ALEX — Clarify or add nuance
4. SAM — Voice the beginner doubt: "so if I understand right..."
5. ALEX — Confirm + sharpen
6. SAM — Practical question: "when would you actually reach for this?"
7. ALEX — Answer with real-world context
8. SAM — Memory hook (SAM delivers it, feels more natural as a peer takeaway)

---

## Audio Generation

### Why Audio Generation is the Hardest Step

For a 20-minute session:
- ~2,600 words of dialogue
- ~10 words per spoken line on average
- ~260 individual TTS segments to render
- Each `edge-tts` call hits Microsoft's Azure servers — latency matters

Sequential rendering would take **8–15 minutes** for a 20-minute session. Async batching brings this to **2–3 minutes**.

### Async Batch Architecture (`tts.py`)

```python
async def render_all_segments(segments: list[Segment]) -> list[AudioSegment]:
    # segments = [(speaker, text, voice, rate), ...]
    semaphore = asyncio.Semaphore(8)   # max 8 concurrent TTS calls

    async def render_one(seg):
        async with semaphore:
            communicate = edge_tts.Communicate(seg.text, seg.voice, rate=seg.rate)
            await communicate.save(seg.temp_path)
            return AudioSegment.from_mp3(seg.temp_path)

    return await asyncio.gather(*[render_one(s) for s in segments])
```

The semaphore caps concurrent requests at 8. Going higher risks rate limiting from Microsoft's endpoint; going lower wastes time.

### Silence Insertion

Silence is not filler — it is pacing. The assembler inserts silence **before** concatenation, not after, so pydub has clean boundaries:

| Pause type | Duration | When |
|---|---|---|
| Within same speaker (breath) | 150ms | Consecutive lines from same speaker |
| Speaker turn | 500ms | Any speaker change |
| Unit boundary | 1,200ms | Between teaching units |
| Intro → Unit 1 | 800ms | After the intro segment |
| Last unit → Outro | 800ms | Before the outro segment |

These are `AudioSegment.silent(duration=N)` segments inserted between rendered clips. They add ~80 seconds to a 20-minute session (accounted for in duration estimation).

### Progress Display

Audio generation is the longest step. The CLI shows a live progress bar:

```
Generating audio...
  [████████████░░░░░░░░░░░░░░░░]  44%  — rendering unit 2/5 (pass-by-value)
  Segments done: 114/260   Elapsed: 1m 12s   ETA: ~1m 30s
```

Implemented with `tqdm` (add to requirements). Each completed `render_one()` call ticks the bar.

### Session Structure (Full Audio Layout)

Every generated session follows this layout regardless of unit count:

```
[INTRO]       ~45s
  ALEX sets the topic and what the student will understand by the end.
  In dual-tutor format, both ALEX and SAM introduce themselves briefly.

[UNIT 1]      variable (based on word_budget)
  Full beat structure for unit 1.

[TRANSITION]  ~5s (spoken bridge, not silence)
  ALEX or SAM: one sentence bridging to the next unit.
  ("Now that you have the reference model in your head, let's go somewhere
  most tutorials get wrong...")

[UNIT 2..N]   variable

[OUTRO]       ~30s
  Quick-fire memory hook recap: ALEX (or SAM) reads each memory hook
  from all units as a rapid closing list.
  ("Remember: copy the address, not the house. final locks the variable,
  not the object. And if you change what hashCode reads, the map forgets
  where you left things.")
```

The outro recap is generated after all unit dialogues are assembled — it pulls the `memory_hook` strings from all unit JSON objects and wraps them in a short spoken paragraph.

### Code in Audio

Java code in the source doc must be spoken as natural English. This is handled by a pre-processing pass in the dialogue generator prompt and enforced by a post-processing sanitizer in `tts.py` before any text hits edge-tts:

| Written | Spoken as |
|---|---|
| `List<String>` | "a List of Strings" |
| `HashMap<String, Integer>` | "a HashMap from String to Integer" |
| `!=` | "not equal to" |
| `==` | "double equals" or "reference equals" |
| `.equals()` | "dot equals" |
| `NullPointerException` | "Null Pointer Exception" |
| `@Override` | "Override annotation" |
| `try { } catch (Exception e) { }` | "a try-catch block" |
| `int[]` | "an int array" |

The sanitizer applies these substitutions as a final pass on every ALEX/MAYA/SAM line before it reaches `edge-tts`. This catches cases where the LLM slips a symbol into the dialogue despite the prompt instructions.

### Output Files

```
tutorial.mp3         the main audio output
tutorial.script.txt  the full dialogue script (always saved alongside audio)
tutorial.units.json  the curriculum plan with word budgets (always saved)
```

The script and units files are saved automatically on every run, not only with `--script-only`. This lets you re-inspect or regenerate audio without re-running LLM calls.

---

## Interactive Playback Mode

### Overview

After generation, the student can play the audio directly from the CLI and interact with the tutor in real time. Audio plays in the background while the main thread reads keyboard commands. When the student asks a question, the audio pauses automatically, the LLM answers in text using the source document as context, and the student resumes with a single keypress.

This is not a voice assistant loop. Audio answers are never generated on the fly — generation is too slow for interactive use and would break the flow. Text answers are immediate and skimmable.

### What Is and Is Not Possible

| Capability | Possible | Notes |
|---|---|---|
| Play / pause / resume | Yes | `pygame.mixer` |
| Jump to a specific unit | Yes | Per-unit mp3 files |
| Rewind / fast-forward within a unit | No (early dev) | pygame doesn't support seek in mp3; Phase 2 |
| Ask a question mid-playback | Yes | Audio pauses, text answer, then resume |
| Answer grounded in source doc | Yes | Source chunks passed as LLM context |
| Immediate audio answer | No | Too slow to generate; text only |
| Multiple questions in sequence | Yes | Each pauses → answers → resumes |
| Review session Q&A later | Yes | Saved to `tutorial.session.json` |

### Per-Unit Audio Files

The TTS renderer saves two outputs instead of one:

1. `tutorial.mp3` — full concatenated session (for external players, sharing)
2. `tutorial_units/unit_01_intro.mp3`, `unit_02_jvm.mp3`, ... — one file per unit

The per-unit files are what the interactive player uses. They solve two problems:
- **No seek needed**: jumping to unit N just means playing `unit_N.mp3`
- **Position tracking**: pygame tracks position within one short file accurately; tracking position across a 20-min monolith is unreliable

The per-unit files are generated at zero extra cost — `tts.py` already builds each unit's segments separately before concatenating. Saving them individually is just skipping the final concat step for those files.

### Player State Machine

```
          ┌──────────────────────────────────────────────────────┐
          │                                                      │
  start ──►  PLAYING  ──[space / p]──►  PAUSED  ──[space / p]──►  PLAYING
               │                          │
            [? / ask]                  [? / ask]
               │                          │
               ▼                          ▼
            ASKING  ◄──────────────  ASKING
               │
          student types question
               │
               ▼
            ANSWERING  (LLM call, ~2-5s)
               │
               ▼
            answer printed to terminal
               │
               ▼
            PAUSED  (student reads answer, presses space to resume)
```

States:
- `PLAYING` — audio running, status bar updating
- `PAUSED` — audio paused, all commands available
- `ASKING` — audio paused, reading multi-line question from stdin
- `ANSWERING` — audio paused, LLM call in progress
- `STOPPED` — session ended (user quit or last unit finished)

Entering `ASKING` from either `PLAYING` or `PAUSED` always pauses audio first.

### Player Display

During playback, the terminal shows a live status line that refreshes every second:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Java Basics — Unit 2/5: Pass-by-value trap
  [████████████░░░░░░░░░░░░░]  06:42 / 21:34
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  [space] pause   [?] ask   [n] next unit   [b] prev unit   [q] quit
```

When paused:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Java Basics — Unit 2/5: Pass-by-value trap  ⏸ PAUSED
  [████████████░░░░░░░░░░░░░]  06:42 / 21:34
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  [space] resume   [?] ask   [n] next   [b] prev   [r] replay unit   [q] quit
```

Status line is redrawn using `\r` escape — no scrolling, no flicker.

### Commands Reference

| Key | Command | Behavior |
|---|---|---|
| `space` | Play / Pause | Toggle between PLAYING and PAUSED |
| `?` | Ask | Pause audio, enter question mode |
| `n` | Next unit | Skip to next teaching unit |
| `b` | Back / Prev | Go back to start of current unit (or prev unit if at start) |
| `r` | Replay | Restart current unit from the beginning |
| `s` | Summary | Print current unit's key facts and memory hook (no audio) |
| `q` | Quit | Stop playback and exit player |

No number keys or complex shortcuts. Every command is a single keypress. The `?` key was chosen for "ask" because it reads naturally as a question mark.

### Keyboard Input Architecture

On Windows, `msvcrt.kbhit()` and `msvcrt.getch()` provide non-blocking single-keypress detection without requiring Enter. On other platforms, use `readchar` (pip package, cross-platform single-keypress).

Wrap in a thin `input_handler.py`:

```python
def get_key_nonblocking() -> str | None:
    # returns the pressed key, or None if no key pressed
    import sys
    if sys.platform == "win32":
        import msvcrt
        if msvcrt.kbhit():
            return msvcrt.getch().decode("utf-8", errors="ignore")
        return None
    else:
        import readchar
        # readchar is blocking — run in a thread with timeout
        ...
```

The player loop polls `get_key_nonblocking()` at 10Hz (every 100ms) and dispatches to the appropriate state transition.

### Threading Model

```
main thread
    │
    ├── player loop (10Hz poll)
    │     reads keypresses
    │     dispatches state transitions
    │     redraws status line
    │
    └── pygame.mixer (internal thread, managed by pygame)
          plays current unit mp3
          signals end-of-track via MUSIC_END event
```

No manual audio thread needed — pygame handles playback internally. The main thread only needs to call `pygame.mixer.music.play()`, `.pause()`, `.unpause()`, and poll `pygame.event.get()` for the `MUSIC_END` event to advance to the next unit.

### Question Mode Flow

When student presses `?`:

1. Audio pauses immediately
2. Status line clears, terminal shows:
   ```
   ── Ask a question ─────────────────────────────────────────
   Current topic: Pass-by-value trap  |  Position: 06:42

   Your question (Enter to submit, Ctrl+C to cancel):
   > _
   ```
3. Student types their question (single line, Enter to submit)
4. Status shows `Thinking...` with a spinner
5. LLM call runs (see Q&A Engine below)
6. Answer printed below the question:
   ```
   ── Answer ──────────────────────────────────────────────────
   Yes — and this is exactly the trap the tutorial is building
   to. Java passes the reference by value, which means the
   reference is copied, but both copies point to the same
   object on the heap. So mutating the object through the
   parameter (like calling list.add()) is visible to the
   caller. What you can't do is reassign the parameter
   variable itself.

   To test your understanding: what do you think happens if
   you pass a String and "modify" it inside the method?

   ── Source: §4 Pass-by-Value ────────────────────────────────
   Press [space] to resume or [?] to ask another question.
   ```
7. State returns to PAUSED. Student presses `space` to resume.

If student presses `Ctrl+C` during question input, ASKING cancels and state returns to PAUSED without an LLM call.

### Q&A Engine (`qa.py`)

The answer is grounded in three layers of context, in priority order:

```
1. Source chunks for the current teaching unit
   (the most relevant content — what the unit was generated from)

2. Source chunks for adjacent units (±1 unit)
   (catches questions that spill over a unit boundary)

3. Last 3 Q&A exchanges from this session
   (prevents the tutor from repeating what was already answered)
```

LLM call structure:

```python
messages = [
    {"role": "system", "content": QA_PROMPT},
    {"role": "user", "content": f"""
Current topic: {unit.concept}
Position in session: Unit {unit.number} of {total_units}

Source content:
{format_chunks(current_chunks + adjacent_chunks)}

Prior questions asked this session:
{format_prior_qa(session_log[-3:])}

Student's question: {question}
"""}
]
```

Uses `call_type="qa"` which routes to the fast model (same as dialogue/summarize) — answers should appear in 1–3 seconds on Groq.

### Q&A Prompt (`prompts/qa.txt`)

```
You are answering a student's question during a Java audio tutorial.
The student just heard a dialogue about: {concept}.

Answer in 4–6 sentences. Rules:
- Ground your answer in the provided source content. Quote it if helpful.
- Do not re-explain what the audio just covered — the student heard it.
  Add to it, correct a misunderstanding, or go deeper.
- If the question is outside the source material, say so in one sentence
  and give a brief general answer, clearly labeled as outside the tutorial.
- End with one short follow-up question that pushes their thinking one step further.
- Cite which section your answer comes from: (§ section name).
- No "Great question!". No filler. Answer and move on.
```

### Session Log (`tutorial.session.json`)

Every Q&A exchange is appended to the session log automatically:

```json
{
  "source_file": "java-basics.md",
  "session_start": "2026-05-08T14:30:00",
  "format": "tutor-student",
  "duration_minutes": 20,
  "exchanges": [
    {
      "id": 1,
      "unit_number": 2,
      "unit_concept": "Pass-by-value trap",
      "position_seconds": 402,
      "position_label": "06:42",
      "question": "So does this mean I can never modify a list inside a method?",
      "answer": "You can modify the list — just not replace it...",
      "source_sections": ["s04_pass_by_value"],
      "timestamp": "2026-05-08T14:36:42"
    }
  ]
}
```

The session log serves multiple future purposes:
- Review questions and answers after the session
- Feed prior questions into the curriculum planner to avoid covering already-understood concepts
- Build a personal "confusion map" over multiple sessions (Phase 2)

### Launching the Player

The `--play` flag generates audio (if not already done) then immediately enters the player:

```bash
# Generate and play in one command
python tutor/tutor.py sample_docs/java-basics.md --play

# Play a previously generated session
python tutor/tutor.py play tutorial.mp3
# reads tutorial.units.json and tutorial.script.txt from same directory

# Play with a specific provider for Q&A
python tutor/tutor.py play tutorial.mp3 --provider openrouter
```

When called as `tutor.py play <file>`, the tool checks for `tutorial.units.json` in the same directory to load unit metadata and source chunk references. If not found, Q&A still works but without source-grounded context (warns the user).

### What Happens at Unit Boundaries

When a unit file finishes playing:
1. pygame fires a `MUSIC_END` event
2. Player auto-advances to the next unit file
3. Status line updates to show new unit name
4. A brief unit-boundary pause (1.2s silence) was already baked into the audio files by the TTS renderer — no extra silence is inserted at runtime

When the last unit finishes:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Session complete: Java Basics (5 units, 21m 14s)
  You asked 3 questions this session.
  Session log saved: tutorial.session.json
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  [r] replay session   [q] quit
```

---

## File Ingestion Strategy

### Token Budget Reality

| Model | Context window | Safe usable budget* |
|---|---|---|
| Groq `llama-3.3-70b-versatile` | 128k tokens | ~100k tokens |
| Groq `llama-3.1-8b-instant` | 128k tokens | ~80k tokens |
| OpenRouter free models | 8k–32k tokens | ~6k–24k tokens |

*Safe budget = context window minus system prompt, output buffer, and safety margin.

OpenRouter free models are the binding constraint — many cap at 8k total. The ingestion strategy must work within 6k tokens of usable input for the most constrained case.

### Three Ingestion Strategies

The document analyzer classifies the doc and picks a strategy automatically:

```
Token count of full doc
        │
   ≤ 6,000 tokens?  ──YES──► Strategy A: Full Document
        │
        NO
        │
   ≤ 60,000 tokens? ──YES──► Strategy B: Section Chunks
        │
        NO
        │
                             Strategy C: Sliding Window + Summarize
```

#### Strategy A — Full Document (small docs, ≤ ~6k tokens)

The whole doc goes into context for both curriculum planning and dialogue generation. No chunking, no summarization.

- Curriculum planner: receives full doc text
- Dialogue generator: receives full doc text
- When: short tutorials, single-topic cheat sheets, lesson files from this repo

#### Strategy B — Section Chunks (medium docs, 6k–60k tokens)

Split at markdown heading boundaries. Each `## Heading` becomes one chunk. If a single section exceeds 4k tokens, split further at `### Sub-heading`.

Each chunk carries a stable ID and breadcrumb path:

```python
{
  "chunk_id": "s03_memory_model",
  "breadcrumb": "Java Basics > Memory Model",
  "heading": "Memory Model",
  "level": 2,
  "token_count": 2140,
  "text": "...",
  "summary": "..."
}
```

- **Curriculum planner**: receives all summaries (~80 tokens × 20 sections = ~1,600 tokens — always fits)
- **Dialogue generator**: receives full text of only the 1–3 chunks referenced by `source_sections` in the unit JSON

#### Strategy C — Sliding Window + Summarize (large docs, > 60k tokens)

For book-length input:

1. Heading-first split; apply sliding window within oversized chunks
2. Sliding window: 2,000 token window, 200 token overlap, break at sentence boundaries
3. Summarize every chunk: one LLM call per chunk → 80-word summary
4. Cluster summaries by heading proximity (max 5 chunks per cluster)
5. Curriculum planner receives cluster summaries
6. Dialogue generator receives 1–3 individual chunks per unit

### Chunk Quality Rules

1. **Never split a code block** — a ` ```java ` block always stays in one chunk
2. **Carry parent heading** — every chunk includes its ancestor heading for context
3. **Minimum chunk size** — chunks under 50 tokens are merged into the previous chunk
4. **Deduplication** — sliding window overlaps tagged with `overlapping: true`

### Summarizer (`summarizer.py`)

One LLM call per chunk, fast model. Prompt:

```
Summarize the following section of a Java tutorial in exactly 3 sentences.
Focus on: what concept is introduced, what the learner is expected to understand,
and one concrete detail (a class name, a rule, an example).
Do not write "this section explains" — write as facts, not as a document summary.
```

Summaries are cached in `.tutor_cache/{chunk_id}.summary.txt`. Invalidated if source chunk text changes (MD5 hash check).

---

## Quality Verification System

### Running the Inspector

```bash
# Full ingestion report — no LLM calls
python tutor/tutor.py sample_docs/java-basics.md --inspect

# Inspect + show summaries
python tutor/tutor.py sample_docs/java-basics.md --inspect --show-summaries

# Curriculum plan with duration breakdown
python tutor/tutor.py sample_docs/java-basics.md --dry-run

# Script only — see full dialogue before committing to audio generation
python tutor/tutor.py sample_docs/java-basics.md --script-only
```

### Ingestion Report

```
=== Ingestion Report ===
File:              java-basics.md
Raw size:          84,312 bytes
Estimated tokens:  21,078
Strategy:          B — Section Chunks
Sections found:    22
Chunks created:    22
  Avg chunk size:  958 tokens
  Largest chunk:   3,841 tokens  (§9 Exception Handling)
  Chunks with code: 14/22

=== Chunk Map ===
ID                    Heading                      Tokens  Code
s01_intro             Introduction + Setup         189     no
s02_jvm               How the JVM Works            1,204   yes
s03_types             Primitive vs Reference       876     yes
s04_pass_by_value     Pass-by-Value                1,540   yes
s05_strings           Strings in Java              1,102   yes
...

=== Chunk Quality Warnings ===
! s09_exceptions — 3,841 tokens, no H3 sub-headings. May produce shallow dialogue.
! s17_generics — code block preserved intact at 4,102 tokens (correct behavior).

=== Orphan Risk ===
  s01_intro (189 tokens) — orientation content, likely skipped
  s11_installation (143 tokens) — setup content, likely skipped
```

### Curriculum + Duration Report (`--dry-run`)

```
=== Duration Plan ===
Target duration:   20 min
Word budget:       2,600 words (@ 130 WPM)
Silence overhead:  ~1m 20s
Format:            tutor-student

=== Teaching Units ===
                                         Complexity  Words   Est. time
Intro                                    —           100     0m 46s
Unit 1  "What is the JVM"                1           260     2m 00s
Unit 2  "Pass-by-value trap"             3           780     6m 00s
Unit 3  "String == vs equals"            2           520     4m 00s
Unit 4  "final ≠ immutable"              2           520     4m 00s
Unit 5  "Checked vs unchecked excs"      2           520     4m 00s
Outro (memory hook recap)                —           80      0m 37s
─────────────────────────────────────────────────────────────────────
Total                                                2,780   21m 23s

=== Coverage ===
Sections used:     14/22 (63.6%)
Sections skipped:  s01_intro, s02_jvm, s10_io, s11_install, ...
Note: skipped sections may have valid content — use --units or --topic to include more.
```

### What to Look For

| Signal | Meaning | Action |
|---|---|---|
| Coverage < 50% | Planner ignoring large parts of doc | Increase `--units` or split doc |
| Est. duration far below `--duration` | Doc is too thin | Use `--difficulty beginner` to expand, or add more source content |
| Est. duration far above `--duration` | Lots of content | Increase `--units` to use more of it |
| Chunk > 4k with warning | Section too dense | Add H3 headings in source doc |
| Important section in skipped list | Planner missed it | Use `--topic "concurrency"` to force inclusion |
| Low token count on used chunks | Dialogue will be shallow | Improve source doc for that section |

---

## LLM Provider Strategy

Both Groq and OpenRouter expose an **OpenAI-compatible REST API**, so a single thin wrapper covers all providers.

### Groq (primary free provider)
- Free tier: ~14,400 requests/day
- Models:
  - `llama-3.3-70b-versatile` — curriculum planning
  - `llama-3.1-8b-instant` — summarization + dialogue generation
- SDK: `groq` package or OpenAI-compat via `base_url=https://api.groq.com/openai/v1`

### OpenRouter (fallback / quota overflow)
- Free models with `:free` suffix
- Best free options:
  - `google/gemma-3-27b-it:free` — curriculum
  - `meta-llama/llama-3.1-8b-instruct:free` — summarization + dialogue
- OpenAI-compat via `base_url=https://openrouter.ai/api/v1`
- Requires `HTTP-Referer` header

### Important: OpenRouter free model context limits
Many cap at 8k tokens total (input + output). Never send more than ~6k tokens of content to an OpenRouter free model call. The ingestion strategies enforce this — each dialogue call only receives the relevant 1–3 chunks.

### Other providers (not used in early dev)
- **Anthropic** — paid; Phase 2
- **OpenAI** — paid; Phase 2

---

## Code Quality Standards

These rules apply to every file in the project, without exception.

### Hard Rules

| Rule | Limit / Requirement |
|---|---|
| Lines per file | ≤ 400 (target 200–300; 400 is the hard ceiling) |
| Lines per function / method | ≤ 40 |
| Parameters per function | ≤ 4 (use a dataclass if more are needed) |
| Nesting depth | ≤ 3 levels (flatten with early returns) |
| One class or one group of related functions per file | enforce via module boundaries |
| No `print()` in library modules | use `logging`; only `tutor.py` and display modules may print |
| No global mutable state | pass state explicitly; no module-level variables that change |
| No magic numbers or strings | all literals live in `constants.py` |
| Type hints on every function signature | `def foo(x: str) -> list[Chunk]:` |
| No bare `except:` | always catch specific exceptions |

### Principles

**Single Responsibility** — each module owns exactly one concern. If you can describe what a module does using "and", it should be split. `tts_renderer.py` renders audio segments. `audio_builder.py` assembles them. They do not know about each other's internals.

**Dependency flows downward only** — upper layers import from lower layers, never the reverse. `curriculum.py` may import from `llm.py`; `llm.py` must never import from `curriculum.py`. See the dependency diagram below.

**DRY within a layer, not across layers** — don't abstract prematurely across layer boundaries just to avoid repeating 3 lines. Duplication within the same layer is a sign to extract a helper; duplication across layers is often correct.

**Dependency injection over hardcoding** — functions receive their dependencies as arguments. `curriculum.py` receives an `llm_fn` callable instead of calling `llm.chat()` directly. This makes every function unit-testable without mocking at the module level.

```python
# bad
def plan_curriculum(summaries):
    return llm.chat(...)

# good
def plan_curriculum(summaries, llm_fn):
    return llm_fn(...)
```

**Dataclasses as contracts** — data passed between modules travels as typed dataclasses, not raw dicts or tuples. A function's type signature is its documentation.

**Pure functions by default** — functions should take inputs and return outputs without side effects. Side effects (file I/O, network calls, printing) are isolated to the outermost layer or explicitly named (`save_`, `fetch_`, `render_`).

**Fail loudly, fail early** — validate inputs at module entry points. Raise a specific `TutorError` subclass with a clear message. Never silently return `None` to indicate failure.

**No comments that describe what the code does** — name variables and functions so the code explains itself. The only acceptable comment is a one-line explanation of *why*, never *what*.

### Dependency Diagram

```
tutor.py  (CLI — argument parsing and orchestration only)
    │
    ├── ingestion/
    │     doc_analyzer.py  ──► models.py
    │     chunker.py        ──► models.py
    │     summarizer.py     ──► infra/llm.py, models.py
    │     parse_content.py  ──► models.py
    │
    ├── generation/
    │     curriculum.py     ──► infra/llm.py, models.py
    │     dialogue.py       ──► infra/llm.py, models.py
    │     assembler.py      ──► audio/sanitizer.py, models.py
    │
    ├── audio/
    │     tts_renderer.py   ──► models.py
    │     audio_builder.py  ──► models.py
    │     sanitizer.py      ──► constants.py
    │
    ├── player/
    │     player.py         ──► models.py, constants.py
    │     player_display.py ──► models.py, constants.py
    │     input_handler.py  (no internal imports)
    │
    ├── qa/
    │     qa.py             ──► infra/llm.py, models.py
    │
    ├── infra/
    │     llm.py            ──► config.py, exceptions.py
    │
    ├── inspector.py        ──► models.py
    ├── models.py           (no internal imports — pure dataclasses)
    ├── constants.py        (no internal imports — pure values)
    ├── exceptions.py       (no internal imports — pure exceptions)
    └── config.py           ──► constants.py
```

Nothing in `infra/` knows about `generation/`, `ingestion/`, or `player/`. Nothing in `models.py` imports from anywhere. This keeps the dependency graph a DAG with no cycles.

### Data Models (`models.py`)

All data structures that cross module boundaries are defined here. No module defines its own ad-hoc dict shape.

```python
from dataclasses import dataclass, field
from typing import Literal

@dataclass
class DocProfile:
    filepath: str
    raw_bytes: int
    estimated_tokens: int
    strategy: Literal["A", "B", "C"]
    section_count: int
    has_code_blocks: bool
    language_hint: str

@dataclass
class Chunk:
    chunk_id: str
    breadcrumb: str
    heading: str
    level: int
    token_count: int
    text: str
    has_code: bool
    summary: str = ""
    overlapping: bool = False

@dataclass
class TeachingUnit:
    unit: int
    concept: str
    source_sections: list[str]
    complexity: int              # 1 | 2 | 3
    word_budget: int
    key_facts: list[str]
    common_misconception: str
    good_analogy: str
    question_style: str
    memory_hook: str
    prerequisite_concepts: list[str] = field(default_factory=list)

@dataclass
class DialogueLine:
    speaker: str                 # "ALEX" | "MAYA" | "SAM"
    text: str
    unit_number: int

@dataclass
class RenderedSegment:
    line: DialogueLine
    audio_path: str
    duration_ms: int

@dataclass
class QAExchange:
    id: int
    unit_number: int
    unit_concept: str
    position_seconds: int
    question: str
    answer: str
    source_sections: list[str]
    timestamp: str

@dataclass
class SessionLog:
    source_file: str
    session_start: str
    format: str
    duration_minutes: int
    exchanges: list[QAExchange] = field(default_factory=list)
```

### Exception Hierarchy (`exceptions.py`)

```python
class TutorError(Exception):
    """Base for all tutor AI errors."""

class IngestionError(TutorError):
    """Raised when doc parsing or chunking fails."""

class LLMError(TutorError):
    """Raised when an LLM call fails or returns unparseable output."""

class TTSError(TutorError):
    """Raised when audio rendering fails."""

class PlayerError(TutorError):
    """Raised when the interactive player encounters an unrecoverable state."""

class ConfigError(TutorError):
    """Raised when required config (API key, ffmpeg) is missing."""
```

All LLM calls wrap provider exceptions in `LLMError`. The CLI catches `TutorError` at the top level and prints a clean message without a traceback (traceback goes to the log file).

### Configuration (`config.py`)

One place where `.env` is read and all settings are exposed as a typed object. No other module reads `os.environ` directly.

```python
@dataclass
class Config:
    groq_api_key: str
    openrouter_api_key: str
    default_provider: str
    anthropic_api_key: str = ""
    openai_api_key: str = ""

def load_config() -> Config:
    # reads .env, raises ConfigError if required keys are missing
    ...
```

### Constants (`constants.py`)

Every literal used in more than one place lives here.

```python
# Audio
WPM = 130
SILENCE_BREATH_MS = 150
SILENCE_TURN_MS = 500
SILENCE_UNIT_MS = 1200
SILENCE_SESSION_MS = 800
TTS_SEMAPHORE_LIMIT = 8

# Voices
VOICE_TUTOR = "en-US-GuyNeural"
VOICE_STUDENT = "en-US-JennyNeural"
VOICE_COTUTOR = "en-US-SaraNeural"
RATE_TUTOR = "+0%"
RATE_STUDENT = "+5%"
RATE_COTUTOR = "+0%"

# Ingestion
STRATEGY_A_TOKEN_LIMIT = 6_000
STRATEGY_B_TOKEN_LIMIT = 60_000
MAX_CHUNK_TOKENS = 4_000
MIN_CHUNK_TOKENS = 50
SUMMARY_CACHE_DIR = ".tutor_cache"

# Complexity
WORDS_PER_COMPLEXITY: dict[int, int] = {1: 200, 2: 380, 3: 580}
OVERHEAD_WORDS = 200   # intro + transitions + outro

# Player
PLAYER_POLL_HZ = 10
```

### Logging Strategy

Use Python's `logging` module throughout. No `print()` calls in any module except `tutor.py`, `inspector.py`, and `player/player_display.py`.

```python
# in each module
import logging
log = logging.getLogger(__name__)

log.debug("LLM prompt: %s", prompt[:200])   # full prompt only at DEBUG
log.info("Curriculum planned: %d units", len(units))
log.warning("Chunk %s exceeds 4k tokens — quality may degrade", chunk_id)
log.error("LLM call failed: %s", str(e))
```

`tutor.py` configures logging at startup:
- Default: `WARNING` level to stderr (user sees only warnings and errors)
- `--verbose`: `INFO` level
- `--debug`: `DEBUG` level, writes to `tutor.log` in the output directory

### Testing Approach

Each module should be independently unit-testable. The dependency injection pattern makes this straightforward:

- **Pure modules** (`models.py`, `constants.py`, `sanitizer.py`, `chunker.py`, `assembler.py`, `inspector.py`): test with plain `pytest`, no mocks needed
- **LLM-dependent modules** (`curriculum.py`, `dialogue.py`, `summarizer.py`, `qa.py`): inject a fake `llm_fn` that returns fixture JSON
- **Audio modules** (`tts_renderer.py`, `audio_builder.py`): test with a short real `edge-tts` call in integration tests; mock in unit tests
- **Player modules** (`player.py`, `player_display.py`): test state machine transitions without pygame; mock `pygame.mixer` in integration tests

Test file layout mirrors source layout: `tests/ingestion/test_chunker.py`, `tests/generation/test_curriculum.py`, etc.

---

## File Structure

```
tutor/
├── tutor.py                      # CLI only: parse args, call orchestration (~150 lines)
├── models.py                     # all dataclasses — no imports from this project
├── constants.py                  # all literals and magic values
├── exceptions.py                 # TutorError hierarchy
├── config.py                     # load .env → typed Config object
├── inspector.py                  # ingestion + duration quality reports (~200 lines)
│
├── ingestion/
│   ├── __init__.py
│   ├── doc_analyzer.py           # profile doc, choose strategy (~100 lines)
│   ├── chunker.py                # Strategy A/B/C splitting + quality rules (~300 lines)
│   ├── summarizer.py             # LLM call per chunk + MD5 cache (~120 lines)
│   └── parse_content.py          # extract key terms, code blocks (~150 lines)
│
├── generation/
│   ├── __init__.py
│   ├── curriculum.py             # summaries → TeachingUnit list (~150 lines)
│   ├── dialogue.py               # unit → DialogueLine list (~120 lines)
│   └── assembler.py              # join scripts, intro, outro, transitions (~200 lines)
│
├── audio/
│   ├── __init__.py
│   ├── tts_renderer.py           # async render one segment → RenderedSegment (~120 lines)
│   ├── audio_builder.py          # concat segments, insert silence, export files (~150 lines)
│   └── sanitizer.py              # code-to-speech substitution table + apply (~80 lines)
│
├── player/
│   ├── __init__.py
│   ├── player.py                 # state machine + pygame event loop (~200 lines)
│   ├── player_display.py         # terminal status line rendering (~100 lines)
│   └── input_handler.py          # non-blocking keypress, Win + cross-platform (~80 lines)
│
├── qa/
│   ├── __init__.py
│   └── qa.py                     # context builder + LLM call + session log (~150 lines)
│
├── infra/
│   ├── __init__.py
│   └── llm.py                    # provider routing, retries, error wrapping (~150 lines)
│
├── prompts/
│   ├── summarize.txt
│   ├── curriculum.txt
│   ├── dialogue.txt
│   └── qa.txt
│
├── tests/
│   ├── ingestion/
│   │   ├── test_chunker.py
│   │   └── test_doc_analyzer.py
│   ├── generation/
│   │   ├── test_curriculum.py
│   │   └── test_assembler.py
│   ├── audio/
│   │   └── test_sanitizer.py
│   └── player/
│       └── test_player_states.py
│
├── sample_docs/
│   └── java-basics.md
├── requirements.txt
├── requirements-dev.txt          # pytest, pytest-asyncio
└── .env.example
```

Generated output (alongside the audio file):
```
tutorial.mp3                  full session audio
tutorial_units/
  unit_01_intro.mp3
  unit_02_jvm.mp3
  ...
tutorial.script.txt
tutorial.units.json
tutorial.session.json
```

---

## Implementation Steps

Build order follows the dependency diagram — lower layers first.

### Step 0 — Pre-flight Checks (`config.py`)

Run before any LLM call, any file I/O, any pipeline step. Fail immediately with a clear `ConfigError` message. Do not let failures surface inside the pipeline as cryptic errors.

Checks in order:

```python
def preflight(args) -> Config:
    # 1. Input file exists and is readable
    # 2. Input file has a .md extension
    # 3. Output path parent directory is writable
    # 4. ffmpeg is reachable (subprocess.run(["ffmpeg", "-version"]))
    # 5. At least one API key is configured for the requested provider
    # 6. If --play: pygame is importable
    # 7. If --play: unit files directory exists alongside the audio file
    ...
```

Error messages must name the fix, not just the problem:

```
✗ ffmpeg not found in PATH.
  Install with: winget install ffmpeg
  Then restart your terminal.

✗ GROQ_API_KEY not set.
  Add it to tutor/.env: GROQ_API_KEY=gsk_...
  Get a free key at: console.groq.com
```

Pre-flight is synchronous and has no dependencies beyond `config.py`. It is the first call in both `cmd_generate()` and `cmd_play()`.

### Step 1 — Foundation (`models.py`, `constants.py`, `exceptions.py`, `config.py`)

Write these four files before any logic. Every other module imports from them. Because they have no internal imports, they are always safe to import from anywhere.

`models.py`: all dataclasses as specified in Code Quality Standards above.
`constants.py`: all literals as specified above.
`exceptions.py`: `TutorError` hierarchy as specified above.
`config.py`: reads `.env` via `python-dotenv`, returns a `Config` dataclass, raises `ConfigError` on missing required keys.

### Step 2 — LLM Abstraction (`infra/llm.py`)

Single public function:

```python
def chat(
    messages: list[dict],
    llm_fn: Callable | None = None,   # injection point for tests
    provider: str = "groq",
    call_type: str = "dialogue",       # selects model tier
) -> str:
```

Internally: selects model based on `(provider, call_type)`, builds the client, makes the call, wraps provider exceptions in `LLMError`, returns the response string.

**Retry strategy:** retry once on transient errors (HTTP 429 rate-limit, HTTP 503, timeout) with a 2-second wait. On the second failure, raise `LLMError`. Do not retry on 400/401 (bad request / auth) — those are permanent.

**LLM output validation and JSON parsing** — this is a critical reliability concern. Free-tier models frequently:
- Wrap JSON in markdown fences: ` ```json ... ``` `
- Add a prose sentence before or after the JSON
- Truncate the JSON if the response is near the model's output limit
- Return valid JSON with wrong field names

Parsing strategy for all calls that expect JSON:

```python
def parse_json_response(raw: str) -> any:
    # 1. Strip markdown fences if present
    text = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()

    # 2. Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 3. Extract first [...] or {...} block via regex
    match = re.search(r"(\[.*\]|\{.*\})", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 4. All parsing failed — raise for retry
    raise LLMError(f"Could not parse JSON from response: {raw[:200]}")
```

If `parse_json_response` raises, `infra/llm.py` makes one additional call with an appended message: `"Your previous response could not be parsed as JSON. Reply with the raw JSON array only, no other text."` If that also fails, raise `LLMError` to the caller. This handles 95%+ of malformed responses from free models without exposing the retry complexity to callers.

### Step 3 — Ingestion (`ingestion/`)

**`doc_analyzer.py`** — `analyze(filepath: str) -> DocProfile`. Pure function: reads file, counts words, detects language, selects strategy. No LLM calls.

**`parse_content.py`** — `extract(chunk: Chunk) -> Chunk`. Enriches a chunk in-place: populates `has_code` (detected from ` ```java ` fences), and extracts `key_terms` (bold `**text**` and inline `` `code` `` patterns). Called by `chunker.py` on every chunk after splitting, before returning. This is how `parse_content.py` connects to the pipeline — it is not called independently.

**`chunker.py`** — `chunk(text: str, strategy: str, profile: DocProfile) -> list[Chunk]`. Implements Strategy A, B, C as three private functions dispatched by strategy letter. Each sub-function is ≤ 80 lines. Quality rules (no code block splits, carry parent heading, merge tiny chunks) enforced in a separate `_apply_quality_rules(chunks)` helper.

**No-headings fallback:** if Strategy B is selected but the document has fewer than 2 `##` headings (i.e., it's a wall of text), the chunker automatically falls back to Strategy C (sliding window). It logs a `WARNING`: `"Document has no headings — falling back to sliding window chunking. Consider adding ## headings to improve chunk quality."` This prevents a silent failure where Strategy B produces one giant chunk.

**`summarizer.py`** — `summarize_all(chunks: list[Chunk], llm_fn, cache_dir: str) -> list[Chunk]`. Returns the same chunks with `.summary` populated. Reads/writes MD5-keyed cache files.

Cache key is `MD5(chunk.text + prompt_version)` — not just `MD5(chunk.text)`. A `PROMPT_VERSION` constant in `constants.py` (e.g., `"v1"`) is included in the hash. When you update `prompts/summarize.txt`, bump `PROMPT_VERSION` to invalidate all cached summaries. Same pattern applies to the dialogue cache (Step 4).

Only processes chunks with `strategy != "A"`.

### Step 4 — Generation (`generation/`)

**`curriculum.py`** — `plan(summaries: list[Chunk], profile: DocProfile, duration_min: int, llm_fn) -> list[TeachingUnit]`. Makes one LLM call. Uses `parse_json_response()` from `infra/llm.py`. Computes `word_budget` for each unit using complexity-weighted distribution. Raises `LLMError` if response cannot be parsed after retry.

**`dialogue.py`** — `generate(unit: TeachingUnit, source_chunks: list[Chunk], fmt: str, llm_fn) -> list[DialogueLine]`. One LLM call per unit.

**Dialogue parsing robustness:** The LLM outputs lines like `ALEX: some text`. The parser must handle:
- Case variations: `Alex:`, `ALEX :`, `Alex -` → normalise to uppercase speaker name
- Colon inside text: `ALEX: The method String.valueOf() works` — split only on the *first* colon
- Blank lines between turns: strip them
- Lines with no speaker label: discard with a `DEBUG` log (do not raise)
- Minimum viable output: if fewer than 4 labelled lines are returned, raise `LLMError` for retry

```python
def _parse_dialogue_line(raw_line: str) -> DialogueLine | None:
    match = re.match(r"^(ALEX|MAYA|SAM)\s*[:\-]\s*(.+)", raw_line.strip(), re.IGNORECASE)
    if not match:
        return None
    return DialogueLine(speaker=match.group(1).upper(), text=match.group(2).strip(), ...)
```

**Partial generation cache:** dialogue generation is the most expensive step (one LLM call per unit). Cache each unit's dialogue to `.tutor_cache/{chunk_id}.dialogue.{prompt_version}.json` immediately after it is generated. On re-run, if a cached dialogue exists for a unit, load it instead of calling the LLM. Cache key includes `prompt_version` (same pattern as summaries). This means a failed run mid-way resumes from the last completed unit, not from scratch.

**`assembler.py`** — `assemble(units: list[TeachingUnit], all_lines: list[list[DialogueLine]], fmt: str) -> list[DialogueLine]`. Pure function.

**Intro and outro are templated, not LLM-generated.** This is a deliberate MVP decision — adding LLM calls for intro/outro creates two more failure points, two more retry paths, and non-deterministic output with no upside for the student.

Intro template (populated from `units[0]` and the doc title):
```
ALEX: Today we're covering {doc_title}. By the end of this session,
      you'll understand {unit_count} concepts that Java developers
      regularly get wrong. Let's start with a question.
```

Outro template (populated from all `unit.memory_hook` values):
```
ALEX: Before we finish — here are the things worth remembering.
      {memory_hook_1}. {memory_hook_2}. {memory_hook_3}.
      Keep those in mind next time you're reading Java code.
```

Transition between units is a single hardcoded `ALEX:` line: `"Now let's look at something related that catches people in a different way."` — identical for every transition. Simple, reliable, acceptable for MVP. Phase 2 can make these unit-specific.

Calls `sanitizer.apply()` as a final pass on every line's text before returning.

### Step 5 — Audio (`audio/`)

**`sanitizer.py`** — `apply(text: str) -> str`. Pure function. Applies the code-to-speech substitution table from `constants.py` using `re.sub`. The substitution table is a module-level constant — a list of `(pattern, replacement)` pairs. Under 80 lines total.

**`tts_renderer.py`** — `render_segment(line: DialogueLine, out_dir: str) -> RenderedSegment`. Async. Calls `edge_tts.Communicate`, saves to a temp file, measures duration with `pydub`. One segment per call. No knowledge of batching or concatenation.

**Temp file cleanup:** `tts_renderer.py` saves each segment to `{out_dir}/seg_{unit}_{idx}.mp3`. After `audio_builder.py` completes concatenation, it deletes the temp segment files. The per-unit files in `tutorial_units/` are kept permanently. The full `tutorial.mp3` is kept. Only the intermediate `seg_*.mp3` files are deleted.

**`audio_builder.py`** — `build(lines: list[DialogueLine], out_path: str, units_dir: str) -> None`. Two responsibilities, split into two private functions:
- `_render_all(lines, out_dir) -> list[RenderedSegment]`: async batch with semaphore, progress bar
- `_assemble(segments, out_path, units_dir)`: insert silences, group by unit, save per-unit files and full concat

Public `build()` calls both in sequence. ≤ 150 lines total.

**Async/sync boundary:** `audio_builder.build()` is the only public async function called from the synchronous CLI. `tutor.py` calls it with `asyncio.run(audio_builder.build(...))`. No other module needs `asyncio.run()` — all other async functions are called from within the async context started by `build()`. This is the single entry point into the async world. Document this explicitly in `audio_builder.py` with a comment on the `build()` function.

### Step 6 — Player (`player/`)

**`input_handler.py`** — `get_key() -> str | None`. Thin platform shim: `msvcrt` on Windows, `readchar` elsewhere. No state, no side effects. Under 80 lines.

**`player_display.py`** — `render_status(unit: TeachingUnit, elapsed_s: int, total_s: int, state: str) -> None`. Prints the status bar using `\r`. All string formatting lives here; no formatting elsewhere in the player. Under 100 lines.

**`player.py`** — `TutorPlayer` class. Owns the state machine and event loop. Calls `player_display.render_status()` and `input_handler.get_key()`. Calls `qa.answer()` when the student asks. Does not format strings for display — passes data to `player_display`. Under 200 lines.

### Step 7 — Q&A (`qa/qa.py`)

`answer(question: str, current_unit: TeachingUnit, all_chunks: list[Chunk], session: SessionLog, llm_fn) -> str`. Builds context from current + adjacent chunks + recent exchanges. Makes one LLM call. Appends `QAExchange` to session. Returns answer string. Under 150 lines.

### Step 8 — Inspector (`inspector.py`)

`report_ingestion(profile: DocProfile, chunks: list[Chunk]) -> None` and `report_curriculum(units: list[TeachingUnit], chunks: list[Chunk], total_chunks: int) -> None`. Pure display functions. No LLM calls. Under 200 lines total.

### Step 9 — CLI (`tutor.py`)

Argument parsing only. No business logic. Calls orchestration functions from the packages above and handles `TutorError` at the top level.

```python
def cmd_generate(args) -> None:
    config = load_config()
    llm_fn = partial(llm.chat, provider=args.provider)
    profile = doc_analyzer.analyze(args.input)
    chunks = chunker.chunk(profile)
    chunks = summarizer.summarize_all(chunks, llm_fn)
    units = curriculum.plan(chunks, profile, args.duration, llm_fn)
    all_lines = [dialogue.generate(u, chunks, args.format, llm_fn) for u in units]
    script = assembler.assemble(units, all_lines, args.format)
    audio_builder.build(script, args.output, units_dir)
    if args.play:
        cmd_play(args)

def cmd_play(args) -> None:
    config = load_config()
    llm_fn = partial(llm.chat, provider=args.provider)
    player = TutorPlayer(unit_files, units, chunks, llm_fn)
    player.run()
```

`tutor.py` is the only place where all packages are imported together. It is the composition root.

The model defaults per `call_type` for reference:

| Provider | `curriculum` | `dialogue` / `summarize` / `qa` |
|---|---|---|
| `groq` | `llama-3.3-70b-versatile` | `llama-3.1-8b-instant` |
| `openrouter` | `google/gemma-3-27b-it:free` | `meta-llama/llama-3.1-8b-instruct:free` |

The `TeachingUnit.word_budget` is computed by `curriculum.py` after the planner returns complexity scores:

```python
base = total_word_budget / sum(u.complexity for u in units)
for u in units:
    u.word_budget = round(base * u.complexity)
```

The code sanitizer substitution table (lives in `constants.py`, applied by `sanitizer.py`):

| Written | Spoken as |
|---|---|
| `List<String>` | "a List of Strings" |
| `HashMap<K, V>` | "a HashMap from K to V" |
| `!=` | "not equal to" |
| `==` | "double equals" |
| `.equals(` | "dot equals" |
| `@Override` | "Override annotation" |
| `int[]` | "int array" |
| `NullPointerException` | "Null Pointer Exception" |
| `StackOverflowError` | "Stack Overflow Error" |

**`--difficulty` flag — what it actually changes:**

| | `beginner` (default) | `intermediate` | `advanced` |
|---|---|---|---|
| Curriculum prompt instruction | Prioritise Tier 0–2 concepts; include more scaffolding steps; analogies are mandatory | Tier 1–4; assume JVM basics known | Tier 3–6; assume OOP known; focus on contracts and concurrency |
| Complexity cap | Max complexity 2 per unit | Max complexity 3 | No cap |
| Word budget multiplier | ×1.3 (more words per concept — more scaffolding) | ×1.0 | ×0.8 (denser, fewer words per concept) |
| MAYA behaviour prompt | "The student has never written Java before" | "The student has written Java for 3 months" | "The student knows the basics but makes design-level mistakes" |

`difficulty` is passed as a string to `curriculum.py` and `dialogue.py`. Both inject it into their prompts via a `{difficulty_context}` template variable. No conditional logic in Python — the prompt text carries all the variation.

**`--topic` flag — implementation:**

`--topic` appends a single line to the curriculum prompt before the section summaries:
```
IMPORTANT: You must include a unit that covers the topic "{topic}". If the source
document does not mention it, create a unit that acknowledges it is out of scope
but explains why it matters in relation to what was covered.
```

This is the entire implementation. One appended line. No special routing logic.

**`--subject java` — what it activates:**

For MVP, `--subject java` is the only working option. It controls which concept map and which Java-specific trap list is injected into `curriculum.txt`. `--subject general` uses a stripped-down version with no Java-specific traps. Other subjects (`spring`, `sql`, `docker`) are Phase 2 stubs that fall back to `general`.

CLI commands (defined in `tutor.py`):

```
Usage:
  python tutor.py <input.md> [options]          generate audio
  python tutor.py play <audio.mp3> [options]    play existing session

Generate options:
  --output FILE         output audio file (default: tutorial.mp3)
  --provider PROVIDER   groq | openrouter  (default: groq)
  --model MODEL         override model for all LLM calls
  --duration MINUTES    target audio duration (default: 20)
  --format FORMAT       tutor-student | dual-tutor  (default: tutor-student)
  --difficulty LEVEL    beginner | intermediate | advanced (default: beginner)
  --units N             max teaching units (overrides --duration unit count)
  --topic TOPIC         force-include a topic the planner might skip
  --subject SUBJECT     java | general (default: java); spring/sql/docker = Phase 2
  --play                generate then immediately launch interactive player
  --script-only         print dialogue script to stdout, skip TTS
  --dry-run             print curriculum + duration plan, no dialogue or audio
  --inspect             print ingestion report only, no LLM calls
  --show-summaries      with --inspect: print each chunk summary
  --no-cache            ignore cached summaries, re-summarize all chunks
  --verbose             INFO-level logging to stderr
  --debug               DEBUG-level logging to tutor.log

Play options:
  --provider PROVIDER   provider used for Q&A answers (default: groq)
  --no-qa               disable Q&A (listen-only mode, no LLM calls during play)
```

---

## Prompts (Key Design)

### `prompts/summarize.txt`

```
Summarize the following section of a Java tutorial in exactly 3 sentences.
Focus on: what concept is introduced, what the learner is expected to understand,
and one concrete detail (a class name, a rule, an example).
Do not write "this section explains" — write as facts, not as a document summary.
```

### `prompts/curriculum.txt`

```
You are a senior Java engineer and educator. You will receive summaries of each
section of a Java tutorial document, plus a target word budget and duration.

Your job: identify 3–8 concepts where learners most commonly get stuck or form a
wrong mental model. For each, assign a complexity score 1–3:
  1 = single rule, one key fact, can be taught in ~200 words
  2 = requires analogy + code contrast + correction, ~400 words
  3 = multi-step reasoning, code tracing, common deep trap, ~600 words

Do not just list topics — find the specific wrong belief a beginner forms and
design the unit to correct it. Each unit must cite source_sections by chunk ID.

Java traps to prioritize: pass-by-value confusion, String == vs .equals(),
checked vs unchecked exceptions, interface vs abstract class, final ≠ immutable,
hashCode contract, autoboxing surprises.

Respond with a raw JSON array only. No text outside the array.
```

### `prompts/dialogue.txt`

```
You are writing a tutoring audio script for Java learners.

FORMAT: {format}
If tutor-student: ALEX is the tutor (explains, corrects), MAYA is the student
  (motivated, makes exactly the misconception listed in the unit).
If dual-tutor: ALEX explains and lays out the standard rule, SAM challenges,
  probes edge cases, and voices the smart beginner's doubt.

WORD BUDGET: write approximately {word_budget} words total (±15%).

CODE IN SPEECH: Never write symbols that cannot be spoken.
  List<String>  →  "a List of Strings"
  !=            →  "not equal to"
  ==            →  "double equals"
  .equals()     →  "dot equals"
  @Override     →  "Override annotation"
  int[]         →  "int array"

RULES:
- Start with a hook (a question or observation that creates tension before explaining).
- Use the provided analogy exactly. Do not invent a different one.
- MAYA/SAM must voice the common_misconception from the unit data, not a generic error.
- End with the memory_hook phrase spoken naturally in a sentence.
- No "Excellent!", "Great!", "Absolutely!". Acknowledge and continue.
- Output only labeled lines: ALEX: ... / MAYA: ... / SAM: ...
- No blank lines between turns. No stage directions.
```

### `prompts/qa.txt`

```
You are answering a student's question during a Java audio tutorial.
The student just heard a dialogue about: {concept}.

Answer in 4–6 sentences. Rules:
- Ground your answer in the provided source content. Quote it if helpful.
- Do not re-explain what the audio already covered — add to it, correct a
  misunderstanding, or go one level deeper.
- If the question is outside the source material, say so in one sentence and give
  a brief general answer, clearly labeled as outside the tutorial scope.
- End with one short follow-up question that pushes their thinking one step further.
- Cite the source section your answer draws from: (§ section name).
- No "Great question!". No filler. Answer and move on.
```

---

## Java Concept Map (Curriculum Reference)

Included inline in `curriculum.txt`:

```
Tier 0 — JVM mental model
  └─ bytecode, classloader, JIT, stack vs. heap

Tier 1 — Type system
  ├─ primitives vs. reference types
  ├─ pass-by-value (including references)
  └─ autoboxing / unboxing traps

Tier 2 — OOP mechanics
  ├─ constructors and this()
  ├─ inheritance and super
  ├─ method overloading vs. overriding
  └─ final: variable / method / class differences

Tier 3 — Core contracts
  ├─ equals() and hashCode() contract
  ├─ == vs. .equals() for Strings and objects
  ├─ Comparable vs. Comparator
  └─ interface vs. abstract class

Tier 4 — Collections
  ├─ List / Set / Map interfaces
  ├─ ArrayList vs. LinkedList
  └─ HashMap internals (buckets, load factor)

Tier 5 — Error handling
  ├─ checked vs. unchecked exceptions
  ├─ try-with-resources
  └─ when to throw vs. when to handle

Tier 6 — Concurrency (advanced)
  ├─ thread safety and shared state
  ├─ synchronized and the monitor lock
  └─ volatile and visibility
```

---

## Dependencies

```
# requirements.txt
openai>=1.0.0           # Groq + OpenRouter (OpenAI-compat)
groq>=0.9.0             # Groq's own SDK
edge-tts>=6.1.9         # free TTS
pydub>=0.25.1           # audio concatenation
pygame>=2.5.0           # audio playback in interactive player
tqdm>=4.66.0            # progress bar during TTS generation
readchar>=4.0.0         # cross-platform single-keypress (non-Windows fallback)
python-dotenv>=1.0.0
markdown-it-py>=3.0.0
```

System dep: `ffmpeg`
```
winget install ffmpeg    # Windows
brew install ffmpeg      # macOS
```

Notes:
- `pygame` is used only for playback (`--play` flag). The generate pipeline works without it.
- `readchar` is the cross-platform fallback for single-keypress input. On Windows, `msvcrt` (stdlib) is used instead and `readchar` is only installed as a fallback.
- `pygame.mixer` initialises a hidden window on some systems — suppress with `os.environ["SDL_VIDEODRIVER"] = "dummy"` before `pygame.init()`.

---

## Environment Variables

```
# .env.example

GROQ_API_KEY=gsk_...           # console.groq.com — free
OPENROUTER_API_KEY=sk-or-...   # openrouter.ai — free models available

# Phase 2 only
# ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...
```

---

## End-to-End Example

```bash
# Install
pip install -r tutor/requirements.txt
winget install ffmpeg

# Configure
cp tutor/.env.example tutor/.env   # add GROQ_API_KEY

# Step 1: inspect doc, no LLM calls
python tutor/tutor.py sample_docs/java-basics.md --inspect

# Step 2: see the duration + curriculum plan
python tutor/tutor.py sample_docs/java-basics.md --dry-run

# Step 3: read the script before generating audio
python tutor/tutor.py sample_docs/java-basics.md --script-only

# Step 4: generate audio
python tutor/tutor.py sample_docs/java-basics.md --output java-intro.mp3

# Step 5: play the generated session interactively
python tutor/tutor.py play java-intro.mp3

# Generate and immediately play in one command
python tutor/tutor.py sample_docs/java-basics.md --play

# Play without Q&A (no LLM calls during playback)
python tutor/tutor.py play java-intro.mp3 --no-qa

# Generate a 30-minute dual-tutor session, then play
python tutor/tutor.py sample_docs/java-basics.md --duration 30 --format dual-tutor --play

# Force include concurrency, 8 units, beginner difficulty
python tutor/tutor.py sample_docs/java-basics.md --topic concurrency --units 8 --difficulty beginner

# Fallback to OpenRouter if Groq quota is hit
python tutor/tutor.py sample_docs/java-basics.md --provider openrouter --output java-intro.mp3
```

### Interactive Session Example

```
$ python tutor/tutor.py play java-intro.mp3

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Java Basics — Unit 1/5: What is the JVM
  [█░░░░░░░░░░░░░░░░░░░░░░░░]  00:18 / 21:34
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  [space] pause   [?] ask   [n] next   [b] prev   [q] quit

...playing...

[user presses ?]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ⏸ PAUSED — Ask a question
  Topic: What is the JVM  |  Position: 01:44
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Your question: Does the JVM compile Java code or interpret it?

Thinking... ⣾

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Answer:
Both, in stages. The Java compiler (javac) first compiles your .java
source into bytecode — that's the .class file. The JVM then interprets
that bytecode at startup, but the JIT (Just-In-Time) compiler inside
the JVM identifies hot code paths and compiles them to native machine
code at runtime. So the first run is interpreted and slower; repeated
execution of the same method gets compiled and becomes fast.

To dig deeper: why do you think Java chose this two-stage approach
instead of compiling directly to machine code like C does?

(§ How the JVM Works)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Press [space] to resume or [?] to ask another question.

[user presses space]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Java Basics — Unit 1/5: What is the JVM
  [█████░░░░░░░░░░░░░░░░░░░░]  01:52 / 21:34
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Integration with Claude / opencode

```bash
# Read ingestion report
python tutor/tutor.py sample_docs/java-basics.md --inspect
# Claude can flag bad chunk boundaries, suggest heading edits to source doc

# Read curriculum + duration plan
python tutor/tutor.py sample_docs/java-basics.md --dry-run
# Claude can critique concept selection, adjust complexity scores, rewrite memory hooks

# Read full dialogue script
python tutor/tutor.py sample_docs/java-basics.md --script-only
# Claude can fix weak analogies, rewrite hooks, correct code-in-speech errors
```

---

## Phase 2 (after free pipeline is validated)

**LLM & TTS quality:**
- Paid LLM providers: Anthropic `claude-sonnet-4-6` and OpenAI `gpt-4o` for richer curriculum reasoning and more natural dialogue
- Paid TTS: OpenAI TTS (`onyx` / `nova`) and ElevenLabs for a consistent voice persona with more expressive delivery
- Precise token counting: replace `word * 1.3` estimate with `tiktoken`
- WPM calibration: measure actual edge-tts output duration on a test segment and compute exact WPM

**Ingestion:**
- Semantic chunking: `sentence-transformers` (free, local) for docs without good heading structure
- Multi-file input: single curriculum spanning multiple docs; cross-file `source_sections`
- Coverage threshold flag: `--min-coverage 70` — warn if planner uses less than 70% of sections

**Player enhancements:**
- True seek within a unit (rewind/fast-forward 30s): switch from `pygame` to `python-vlc` which supports `libvlc_media_player_set_time()`
- Transcript scroll: show which line of dialogue is currently being spoken, synced to playback position
- Bookmark command (`[m]`): mark a timestamp the student wants to return to, saved in session log
- Speed control (`[+]` / `[-]`): adjust playback rate 0.75×–1.5×

**Q&A enhancements:**
- Confusion map: after multiple sessions on the same doc, surface which concepts generated the most questions — feed back to curriculum planner to emphasize those in re-runs
- Session history: on `play`, load prior session log and show "you asked N questions last time" — include those Q&As as context so the tutor doesn't re-answer the same things
- Multi-turn Q&A: allow follow-up questions before resuming (current plan: one question then resume)
- Voice Q&A (Phase 3): use speech recognition to accept spoken questions, still answer in text

**Content:**
- More subjects: `--subject spring`, `--subject sql`, `--subject docker` with matching concept maps
- Exercise export: generate `.json` for `standalone/lesson.html` so audio concepts map to interactive exercises
- Adaptive re-runs: use session Q&A history to detect confusion → regenerate that unit at a deeper level
