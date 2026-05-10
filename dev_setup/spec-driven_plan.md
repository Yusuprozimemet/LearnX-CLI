# Spec-Driven Development Plan for LearnX

## What Spec-Driven Development Is

Spec-driven development (SDD) means writing a precise, self-contained description of
what a piece of software should do — before touching any code. The spec is not a
comment, not a ticket title, not a vague goal. It is a document that a developer (or
an AI agent) can read and know exactly what files to change, what the output must look
like, and what tests prove it is correct.

The spec is the source of truth. The code is the implementation of that truth. The
tests are the proof.

---

## How This Project Already Does It

Look at the structure of `specs/v3/day13.md`:

```
Goal              ← one paragraph, the "why"
Data boundary     ← what files are read and written, nothing else
New model         ← the exact dataclass with field names and types
Algorithm         ← pseudocode or real code showing the logic
Acceptance criteria  ← a checklist; every item is testable
Tests             ← exact test function names to write
```

Every spec in this project follows this shape. That is not accidental — this shape
forces the spec writer (you) to think through the design before the agent starts
coding. The agent does not design; it implements.

Compare this to a vague instruction:

```
Vague:  "Add timing to the audio builder."
Spec:   "Modify _concat_with_silence() to return tuple[AudioSegment, list[TimingEntry]].
         Write tutorial.timing.json to audio/<session>/ with version:1 at top level.
         Teaching units 1..N only; unit 0 and -1 excluded."
```

The vague version produces a guess. The spec version produces an implementation you
can verify line by line.

---

## The Anatomy of a Good Spec

Every spec in this project has the same structure. Here is what each section does and
why it matters:

### 1. Goal (one paragraph)

What problem does this solve and why now? This is for humans, not the agent.
It keeps the spec grounded in the real reason for the change.

```
Day 13 goal: "During audio assembly, record the exact millisecond start and end
offset of every dialogue line and write it to tutorial.timing.json. This gives
every downstream step deterministic, zero-estimation timestamps."
```

### 2. Data boundary

What files does this change read? What does it write? What does it not touch?

This is the most discipline-enforcing section. If you cannot state the data
boundary clearly, the design is not ready. Agents that do not have a data boundary
tend to write to the wrong files or read state they should not.

```
Writes (new):  audio/<session>/tutorial.timing.json
Reads (unchanged): audio/<session>/tutorial_units/*.mp3
```

### 3. New models / signatures

If new data structures are introduced, define them exactly. Field names, types,
default values. No ambiguity. The agent copies this into `models.py`.

### 4. Algorithm

Pseudocode or real Python showing the core logic. This is not the full
implementation — it is the skeleton. Edge cases should appear here.

```python
for idx, seg in enumerate(segments):
    gap = 0 if prev_speaker is None else ...
    cursor_ms += gap
    entries.append(TimingEntry(..., start_ms=cursor_ms, end_ms=cursor_ms + len(audio)))
    cursor_ms += len(audio)
```

### 5. Acceptance criteria

A checklist. Each item must be:
- **Testable** — you can write a pytest assertion for it
- **Binary** — it either passes or it does not
- **Specific** — not "timing is correct" but "start_ms of entry N equals end_ms of
  entry N-1 + silence gap"

This list is what the agent iterates against. It is also what you check when the
agent reports done.

### 6. Tests

Exact test function names to write. Not descriptions — names. This means the
agent does not invent test names and you know exactly which tests should exist.

```
test_timing_file_written_after_build
test_timing_keys_match_teaching_units
test_timing_offsets_no_gaps_no_overlaps
```

---

## What the Fix Files Teach You About Specs

The `fixes/` folder contains 15 post-mortems. Each one is a case where the
implementation ran into something the spec did not cover. Read them as a guide to
what to put in specs:

| Fix        | What the spec missed                                          |
|------------|---------------------------------------------------------------|
| fix001     | ffmpeg path on Windows — spec assumed PATH was correct        |
| fix003     | `AudioSegment.empty()` is not addable to silence — API detail |
| fix007     | Pydub duration in milliseconds, not seconds — unit confusion  |
| fix015     | Ruff lint rules — spec never mentioned code style gate        |

The pattern: specs missed environmental assumptions, library API details, and
tooling requirements. Over time, good specs add these as explicit constraints:

- "Use `AudioSegment.silent(duration=gap)` not `AudioSegment.empty()`."
- "File must pass `py -m ruff check` before the acceptance criteria are considered met."

Every fix file is a lesson in what the next spec should make explicit.

---

## How to Write a Spec — Step by Step

Use Day 13 as a template. For any new feature:

### Step 1: Write the goal first

One paragraph. Answer: what problem does this solve, and what is the simplest thing
that could work?

### Step 2: Draw the data boundary

List every file the change reads and every file it writes. If you are not sure,
that is a signal the design is not ready.

### Step 3: Define new data structures

Write out the dataclass or JSON format before thinking about the code. The shape
of the data drives the shape of the code.

### Step 4: Write the algorithm in pseudocode

Do not write the full implementation. Write the skeleton — enough that a competent
developer (or Claude) can fill it in. Include the edge cases that are not obvious.

### Step 5: Write the acceptance criteria

Start with "what would a failing test look like?" and work backwards. Every
criterion is a test waiting to be written.

### Step 6: List the test function names

Name the tests before writing them. This forces you to think about coverage. If
you cannot name a test, you do not know what you are testing.

---

## Spec Versioning in This Project

The project uses versioned spec folders: `specs/v0/`, `specs/v1/`, `specs/v2/`,
`specs/v3/`. This matches the plan files: `plan/v0_plan.md` through `plan/v3_plan.md`.

The rule: when a major architectural shift happens (v1 → v2 → v3), old specs are
not deleted. They stay as a record of what was implemented and why it was superseded.

This matters for regression protection: if a v3 change breaks a v2 behaviour, you
can read the v2 spec to understand what the intended behaviour was.

---

## Spec-Driven vs. Other Approaches

| Approach              | How decisions are made         | Who designs        |
|-----------------------|--------------------------------|--------------------|
| Vibe-driven           | Agent guesses from context     | Agent              |
| Comment-driven        | Inline comments guide changes  | Agent (partially)  |
| Ticket-driven         | Short issue descriptions        | Mixed              |
| **Spec-driven (SDD)** | Precise doc before any code    | **You**            |

In spec-driven development, the human does the design work. The agent does the
implementation work. This is the correct division of labour: agents are fast and
tireless at mechanical coding; humans understand requirements, trade-offs, and
constraints.

The spec is where your understanding lives. The code is where the agent's execution
lives.

---

## Connecting Spec-Driven to the Other Three Pillars

```
Spec-driven
  → The spec tells the agent exactly what "done" means.
  → Without this, context hygiene fails: the agent does not know what to focus on.
  → Without this, the sandbox is just a branch with random changes.
  → Without this, autonomy is dangerous: the agent has no exit condition.

Context hygiene depends on spec-driven:
  → You only put the current spec in the context. The spec defines what "current" means.

Sandbox depends on spec-driven:
  → The spec's data boundary tells you which files to scope your branch to.
  → The spec's acceptance criteria is the merge gate.

Autonomy depends on spec-driven:
  → The agent runs autonomously until the acceptance criteria are all green.
  → Without acceptance criteria, the agent does not know when to stop.
```

---

## Quick Reference: Spec Checklist

Before handing a spec to Claude (or starting to code yourself):

```
[ ] Goal paragraph written — one paragraph, explains the why
[ ] Data boundary written — reads X, writes Y, does not touch Z
[ ] New models defined — exact field names and types
[ ] Algorithm sketched — pseudocode covering the happy path and key edge cases
[ ] Acceptance criteria written — each one is a testable, binary assertion
[ ] Test names listed — exact pytest function names
[ ] File size constraint noted — e.g., "audio_builder.py stays under 400 lines"
[ ] Ruff gate mentioned — implementation must pass ruff check and format
```

If any item is missing, fill it in before starting. A five-minute spec gap costs
a two-hour debugging session on the other side.
