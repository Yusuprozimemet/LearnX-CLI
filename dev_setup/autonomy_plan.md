# Autonomy Plan for LearnX — Spec-Driven Development

## What Autonomy Means Here

Autonomy is not about trusting the AI blindly. It is about structuring your work so
the AI can run a full implement → test → fix → retest cycle without you being in the
loop at each step.

You already have the three prerequisites in place:

| Prerequisite    | How You Have It                                          |
|-----------------|----------------------------------------------------------|
| Spec-driven     | `specs/v3/day13.md` etc. with acceptance criteria        |
| Context hygiene | One spec per session, clear file boundaries per day      |
| Sandbox         | `sandbox/dayN` git branch, scoped pytest command         |

Autonomy is the fourth layer. It says: *given those guardrails, the agent can run
the loop end-to-end. You review the result, not each step.*

---

## The Shift in Your Role

**Before autonomy (what you have been doing):**

```
You: "Read day13 spec and implement the timing change."
Claude: [writes code]
You: run pytest, paste failure output
Claude: [fixes]
You: run pytest again, paste output
Claude: [fixes again]
You: "Looks good, anything else?"
```

You are the test runner. You are the feedback loop. You are the bottleneck.

**With autonomy:**

```
You: "Implement day13. Run tests. Fix failures. Report when all criteria are green."
Claude: [implements → runs pytest → reads output → fixes → runs again → reports]
```

You come back to a result. You review it. You decide to merge or push back.

---

## What Makes Autonomy Safe on This Project

The sandbox plan already handles the risk:

- Claude works on a `sandbox/dayN` branch — `main` is untouched
- Scoped tests (`py -m pytest tutor/tests/audio/ -v`) limit blast radius
- The merge gate (full suite + ruff) is a hard exit condition
- Acceptance criteria in the spec are the definition of "done"

If the agent makes a mistake inside the branch, you delete the branch and start over.
The cost of a bad autonomous run is a discarded branch, not broken production code.

---

## How to Hand Off a Spec for Autonomous Execution

### The handoff prompt structure

When you start a spec day, give Claude one message with everything it needs:

```
Spec: specs/v3/day13.md
Branch: sandbox/day13 (create from main)
Scope: tutor/audio/audio_builder.py, tutor/models.py
Test command: py -m pytest tutor/tests/audio/ -v
Merge gate: py -m pytest && py -m ruff check tutor/

Implement all changes described in the spec. Run the test command after each
change. Fix any failures. When all acceptance criteria are green and the merge
gate passes, report what you did and what changed.
Do not merge to main — I will do that after reviewing.
```

That is the entire handoff. You do not need to explain the spec — Claude reads it.
You do not manage the iterations — Claude runs them.

### What you review when Claude comes back

- Which files changed and why (matches the spec's stated file list?)
- Did all acceptance criteria get checked off?
- Did the merge gate (full suite) pass?
- Are there any new files Claude created that were not in the spec?

If those four questions are answered correctly, you merge. If not, you push back
with a specific correction — not a re-explanation of the whole spec.

---

## Levels of Autonomy — Start at Level 1

You do not have to jump to full autonomy immediately. There are natural levels:

### Level 1 — Autonomous implementation, you run tests

```
You: "Implement day13."
Claude: [writes all the code]
You: run pytest, paste results
Claude: [fixes if needed]
```

This is what you have been doing. It is already partially autonomous — you are not
telling Claude which lines to change.

### Level 2 — Autonomous implementation + test reading

```
You: "Implement day13. Here are the test results: [paste output]"
Claude: [implements + fixes based on the pasted output in one go]
```

You run tests once at the end rather than iterating. Fewer round trips.

### Level 3 — Autonomous loop (Claude runs tests)

Claude runs `py -m pytest` directly using its Bash tool, reads the output, fixes,
and re-runs without waiting for you. You set the permissions to allow it.

This is the full autonomy mode. It requires:
- Claude Code permission to run `py -m pytest` automatically (no prompt per run)
- A sandbox branch already created (so there is no risk to main)
- Clear acceptance criteria (so Claude knows when to stop iterating)

### Level 4 — Autonomous session (you come back to a finished spec)

You open Claude, paste the handoff prompt, and walk away. You come back and Claude
has implemented, iterated through failures, fixed them, and is reporting the result.

This is the conference speaker's vision. It is achievable on this project today
because the specs are tight enough.

---

## Enabling Level 3 on This Project

Level 3 requires telling Claude Code which commands it can run without asking you
each time. You can configure this in your project settings.

Add `py -m pytest` and `py -m ruff check` to the auto-approved command list so
Claude does not stop and ask permission on every test run.

Use the `/update-config` skill to do this, or manually add the commands to
`.claude/settings.json`:

```json
{
  "permissions": {
    "allow": [
      "Bash(py -m pytest*)",
      "Bash(py -m ruff check*)",
      "Bash(py -m ruff format --check*)",
      "Bash(git checkout -b sandbox/*)",
      "Bash(git status)",
      "Bash(git diff*)"
    ]
  }
}
```

With these in place, Claude can run the full test → fix → retest loop without
stopping. The loop exits when tests go green, not when you say so.

---

## What Autonomy Looks Like for Each Spec Day

### Day 13 — Handoff prompt

```
Spec: specs/v3/day13.md
Branch: sandbox/day13 (create from main)
Scope: tutor/audio/audio_builder.py, tutor/models.py,
       tutor/tests/audio/test_audio_builder.py
Test command: py -m pytest tutor/tests/audio/ -v
Merge gate: py -m pytest && py -m ruff check tutor/

Implement the timing capture changes. Write the new tests listed in the spec.
Run tests after each change and fix failures. Stop when all acceptance criteria
pass and the merge gate is clean. Report which criteria are green.
```

### Day 14 — Handoff prompt

```
Spec: specs/v3/day14.md
Branch: sandbox/day14 (create from main, after day13 is merged)
Scope: tutor/generation/segment_planner.py (new file),
       tutor/models.py, tutor/prompts/visual_v2.txt
Test command: py -m pytest tutor/tests/generation/test_segment_planner.py -v
Merge gate: py -m pytest && py -m ruff check tutor/

Implement the dialogue-aware visual planner. Write all 12 tests listed in the
spec. Run and fix until green. Report when done.
```

You write the same shape of prompt for Day 15 and Day 16.

---

## Context Hygiene During Autonomous Runs

Autonomy and context hygiene work against each other if you are not careful. A long
autonomous session accumulates context — test output, intermediate failures, fix
attempts. By the end, Claude may have a cluttered picture of what it is doing.

To keep context clean during an autonomous run:

1. **One spec per session.** Start a fresh Claude session for each spec day. Do not
   carry Day 13's context into Day 14.
2. **Handoff prompt is self-contained.** Everything Claude needs is in the prompt.
   Claude should not need to remember previous conversations.
3. **If the session runs long and Claude seems confused**, start a new session with
   the same handoff prompt + the current test failure output. Fresh context, same goal.

This matches what you are already doing. Autonomy does not change the hygiene rule —
it just means the session runs longer before you need to check in.

---

## The Honest Boundaries

Autonomy works well when:
- The spec is unambiguous (your v3 specs are)
- The failing test tells you exactly what is wrong (pytest output does this)
- The fix is mechanical (wrong return value, missing field, off-by-one)

Autonomy breaks down when:
- The spec has a gap that requires a design decision
- A failure could be fixed two different ways with different trade-offs
- Something outside the spec is failing and it is unclear why

Your fix files (`fix001`–`fix015`) are a record of exactly these moments. Most of
them (ffmpeg path, pydub AudioSegment.empty(), ruff lint drift) are the kind of
environmental or tool-compatibility surprise that no spec can predict. When these
happen, the agent stops and asks. That is correct behaviour, not a failure of
autonomy.

The goal is not to eliminate human judgment. It is to reserve your judgment for the
decisions that actually need it, and hand the mechanical iteration to the agent.

---

## Summary: The Four Pillars Working Together

```
Spec-driven     →  Claude knows exactly what "done" means
Context hygiene →  Claude stays on task, not haunted by old decisions
Sandbox         →  Claude can act freely without risk to main
Autonomy        →  Claude runs the full loop; you review results
```

Start at Level 1 (you already are). Try Level 2 on Day 14. Try Level 3 on Day 15
once you have added the pytest permission to settings. See how far you can get before
Claude needs to ask you something.

That experiment is what the conference speaker was pointing at.
