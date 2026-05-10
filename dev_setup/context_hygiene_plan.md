# Context Hygiene Plan for LearnX

## What Context Hygiene Means

Every AI session has a context window — a fixed amount of information the model can
hold at once. Context hygiene is the practice of managing what goes into that window
deliberately, so the agent always has the right information and none of the wrong
information.

Bad context hygiene looks like:
- Starting Day 14 in the same session where Day 13's debugging is still visible
- Pasting the entire codebase when only one file is relevant
- Letting a session run so long that early decisions are buried under later noise
- Carrying a failed approach into the next attempt instead of starting clean

Good context hygiene looks like:
- One fresh session per spec day
- Only the current spec and the relevant files in context
- Starting a new session when a session gets confused or stuck
- Handoff prompts that are self-contained — the agent does not need to remember
  anything from a previous conversation

---

## Why It Matters for This Project

LearnX has grown across three versions (v0 → v1 → v2 → v3) and 15 fix files. A
session that has seen all of that history will carry stale assumptions:

- v1's approach to timing (word count estimation) conflicts with v3's approach
  (exact timestamps from audio builder)
- A fix applied in fix007 may contradict how the agent remembers the function
  working from an earlier session
- Half-finished Day 13 code left in context will confuse Day 14 implementation

The agent is not stupid — it is confused. Confusion comes from noise in the context,
not from lack of capability. Context hygiene removes the noise.

---

## The Core Rule

**One spec. One session. One branch.**

| Scope     | Boundary                                              |
|-----------|-------------------------------------------------------|
| Spec      | One day's spec (`specs/v3/day13.md`)                  |
| Session   | New Claude session for each spec day                  |
| Branch    | `sandbox/day13` created fresh from `main`             |

When the spec is done, the session ends. The next spec day gets a fresh session
with no memory of what happened in the last one.

---

## What Goes Into the Context

For each spec day, the context should contain exactly:

### Always include
- The spec file (`specs/v3/dayN.md`) — the source of truth
- The files the spec says to change — no others
- The test file for those changes — so Claude can run and read tests
- The handoff prompt (structured, see below)

### Include when relevant
- The plan file for this version (`plan/v3_plan.md`) — only for big-picture questions
- The specific fix file if a known issue from a previous session applies
  (e.g., fix007 if pydub audio duration is involved)

### Never include
- Fix files from unrelated days — they add noise
- Old spec versions (v1, v2 specs) — the agent will mix old and new approaches
- The full test suite — only the tests for the current spec
- Long conversation history from a previous day — start fresh

---

## The Handoff Prompt — Your Context Hygiene Tool

The handoff prompt is a short, structured message that gives the agent everything
it needs in one place. Because it is self-contained, you can start a fresh session
at any time and the agent picks up exactly where you intend.

### Template

```
Spec:         specs/v3/day<N>.md
Branch:       sandbox/day<N> (create from main)
Files to change:
  - tutor/<path>/<file>.py
  - tutor/models.py (add <Model> dataclass)
  - tutor/tests/<path>/test_<file>.py (write new tests)
Test command: py -m pytest tutor/tests/<path>/ -v
Merge gate:   py -m pytest && py -m ruff check tutor/

[one sentence about what this day is doing, for orientation]

Implement the changes described in the spec. Run tests after each change.
Fix any failures. Report when all acceptance criteria are green.
```

### Day 13 example

```
Spec:         specs/v3/day13.md
Branch:       sandbox/day13 (create from main)
Files to change:
  - tutor/audio/audio_builder.py
  - tutor/models.py (add TimingEntry dataclass)
  - tutor/tests/audio/test_audio_builder.py (add 7 new tests)
Test command: py -m pytest tutor/tests/audio/ -v
Merge gate:   py -m pytest && py -m ruff check tutor/

Day 13 captures exact millisecond timestamps for every dialogue line during
audio assembly and writes them to tutorial.timing.json.

Implement the changes described in the spec. Run tests after each change.
Fix any failures. Report when all acceptance criteria are green.
```

This prompt fits in a few lines. A new session started with this prompt has
everything it needs. Nothing from Day 12's session bleeds in.

---

## Signs That Context Has Gone Bad

Watch for these during a session. They are signals to start fresh:

| Signal | What It Means |
|--------|---------------|
| Agent references a decision from earlier in the conversation as if it were code | The session is too long; old decisions are being treated as ground truth |
| Agent proposes a solution that contradicts the spec | Earlier context (old approach, old fix) is winning over the spec |
| Agent says "as we discussed" about something that was actually abandoned | It is mixing up attempts from earlier in the session |
| Test output from three iterations ago is being referenced | Context is cluttered with stale state |
| Agent starts refactoring code the spec did not mention | It has run out of clear direction and is filling the gap with its own ideas |

When you see these, do not try to correct the agent. Start a new session with the
handoff prompt and paste the current test failure output. Fresh context, same goal.

---

## Context Hygiene Across Spec Days

The spec days in v3 are sequential and dependent:

```
Day 13 → writes tutorial.timing.json
Day 14 → reads tutorial.units.json, writes tutorial.segments.json
Day 15 → reads tutorial.segments.json, writes PNGs
Day 16 → reads timing.json + segments.json, drives beat_timer and subtitle_writer
```

Each day produces an output that the next day reads. This is the correct architecture
for context hygiene too: each session receives the previous day's *result* (the merged
code in `main`), not the previous day's *conversation*.

```
Day 13 session  →  merge to main  →  Day 14 session reads main
Day 14 session  →  merge to main  →  Day 15 session reads main
```

Never carry Day 13's session into Day 14. The code in `main` is the handoff, not
the conversation.

---

## Context Hygiene When a Session Gets Stuck

Sometimes a session hits a wall: a test keeps failing, the agent is going in circles,
or the approach is clearly wrong. The temptation is to keep pushing in the same
session.

Instead:

1. **Stop the session.** Do not try one more thing.
2. **Write a short fix note** — one or two sentences describing what the actual
   problem turned out to be (this is what the `fixes/` folder is for).
3. **Open a new session** with the handoff prompt + the specific failure.
4. **Give the agent only the failure**, not the history of attempts that did not work.

Example:

```
[fresh session]
Spec: specs/v3/day13.md
Branch: sandbox/day13 (already created, do not recreate)

One test is failing. The error is:
  AssertionError: end_ms - start_ms == 3240, expected 3200
  (test_timing_duration_matches_pydub_len)

The audio file is 3200 ms. The mismatch appears to come from AudioSegment.empty()
adding an unexpected 40 ms. Investigate and fix only this.
```

The agent gets a clean context focused on one specific failure. It does not know
about the three previous failed attempts. It solves the problem faster.

---

## The Relationship Between the Four Pillars

```
Context hygiene and spec-driven:
  → The spec is what you put in the context. A clean spec = a clean context.
  → A vague spec forces the agent to fill gaps from earlier in the conversation,
    which is exactly what context hygiene is trying to prevent.

Context hygiene and sandbox:
  → The sandbox branch isolates code; context hygiene isolates information.
  → Together: the agent has a clean branch to work on AND a clean mental model
    of what it is doing.

Context hygiene and autonomy:
  → Autonomy requires a long session (the agent runs many iterations).
  → Good context hygiene at the START of the session (tight handoff prompt,
    right files, no noise) is what keeps the agent on track through a long run.
  → If context hygiene is poor, autonomy amplifies the problem — the agent
    wanders further before you notice.
```

---

## Quick Reference: Context Hygiene Checklist

Before starting each spec day:

```
[ ] New session opened — not continuing from the previous spec day
[ ] Handoff prompt written — spec, branch, files, test command, merge gate
[ ] Only the current spec in context — no old specs, no old fix files
[ ] Only the relevant source files attached — not the whole tutor/ tree
[ ] Previous day's code is merged to main — the branch, not the session, is the handoff
```

During the session:

```
[ ] If the agent references abandoned approaches → start fresh
[ ] If tests have been failing for 3+ iterations without progress → start fresh
[ ] If the agent proposes changes outside the spec's file list → correct it immediately
[ ] If the session is going well → let it run; do not interrupt with new information
```

After the session:

```
[ ] Write a fix note if anything surprising happened (even if resolved)
[ ] Merge the branch to main before starting the next session
[ ] Delete the sandbox branch after merging — clean slate
```

---

## Summary

Context hygiene is not about being paranoid. It is about being deliberate. The agent
works best when it has exactly the right information and none of the wrong information.

A fresh session with a tight handoff prompt and the right files will outperform a
long session that has accumulated noise — every time.

The rule is simple: **one spec, one session, one branch.** Everything else follows
from that.
