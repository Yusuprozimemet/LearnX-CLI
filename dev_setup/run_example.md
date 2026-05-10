# Run Example — How to Use the LearnX Dev Workflow

## The Core Pattern (Works with Any AI Tool)

The workflow has two halves:

```
YOUR HALF (human):
  1. Update plan/v3_plan.md     ← architectural decisions, the "why"
  2. Rewrite specs/v3/dayN.md   ← exact spec: data boundary, models, algorithm, criteria
  3. Fill in the handoff prompt  ← from dev_setup/handoff_template.md

AI HALF:
  4. Read the spec
  5. Create sandbox/dayN branch
  6. Implement → test → fix → report
  7. STOP — you review and merge
```

The handoff prompt is the bridge. Everything before it is yours; everything after is the AI's.
The spec is the contract. The AI implements to the spec, not to your intent.

---

## Concrete Example: Starting Day 13

You have updated the spec. You open a fresh AI session and send this (from the template):

```
=== LEARNX HANDOFF — Day 13 ===

Spec:         specs/v3/day13.md
Branch:       sandbox/day13   ← create from main
Files to change:
  - tutor/audio/audio_builder.py
  - tutor/models.py            (add TimingEntry dataclass)
  - tutor/tests/audio/test_audio_builder.py   (new file — 7 tests listed in spec)

Scoped test command:   py -m pytest tutor/tests/audio/ -v
Merge gate:            py -m pytest && py -m ruff check tutor/ && py -m ruff format --check tutor/

Day 13 captures exact per-line millisecond timestamps during audio assembly and writes
them to tutorial.timing.json.

INSTRUCTIONS:
1. Read the spec completely before writing any code.
2. Create the branch from main.
3. Implement only the files listed above. Do not modify other files.
4. Run the scoped test command after each change. Fix failures before continuing.
5. When scoped tests are green, run the full merge gate.
6. Report: each acceptance criterion and whether it passes. Show gate output.
7. Do NOT merge to main — I will review and merge.

Read these fix notes before starting:
  - fixes/fix001.md — ffmpeg path on Windows
  - fixes/fix013.md — timing inflation root cause (this is what Day 13 fixes)
```

That message is the entire activation. You send it once. You don't need to explain the project
history, the v3 architecture, or how pydub works. All of that is in the spec and CLAUDE.md.

---

## Tool-by-Tool: How the Pattern Differs

---

### Claude Code (Anthropic CLI)

**How context loads:**
`CLAUDE.md` is read automatically at the start of every session. You never need to paste it.
The AI already knows the project layout, the four-pillar workflow, the current state, and
the hard rules before you type anything.

**How to start:**
Open Claude Code in the project directory. Paste the handoff prompt. Done.

**The loop:**
With `.claude/settings.json` configured (already done in this repo), Claude can run
`py -m pytest`, `py -m ruff`, and safe git commands without asking your permission each time.
The implement → test → fix → retest cycle runs without interruption.

**What you do:**
Send one message (the handoff prompt). Come back to a report. Review the diff.
Run `git merge sandbox/day13` if it looks right.

**Autonomy level:** Full (Level 3–4 from `dev_setup/autonomy_plan.md`).

**Example session:**

```
You:    [pastes Day 13 handoff prompt]

Claude: [reads CLAUDE.md — already loaded]
        [reads specs/v3/day13.md]
        [git checkout main && git checkout -b sandbox/day13]
        [edits tutor/models.py — adds TimingEntry]
        [edits tutor/audio/audio_builder.py]
        [writes tutor/tests/audio/test_audio_builder.py]
        [runs: py -m pytest tutor/tests/audio/ -v]
        [reads failure output — fixes _concat_with_silence return type]
        [runs: py -m pytest tutor/tests/audio/ -v]  ← green
        [runs: py -m pytest]                         ← full suite
        [runs: py -m ruff check tutor/]              ← clean
        [reports: 7/7 criteria green, gate passed, files changed: 3]

You:    [review the diff]
        [git merge sandbox/day13]
```

You were not in the loop during steps 2–10. That is the point.

---

### GitHub Copilot (VS Code / JetBrains)

**How context loads:**
Copilot does NOT auto-read `CLAUDE.md`. You must give it context manually.

In VS Code Copilot Chat, attach files explicitly:
```
#file:CLAUDE.md  #file:specs/v3/day13.md
[paste the handoff prompt body]
```

Alternatively, copy the contents of `CLAUDE.md` and paste them before the handoff prompt.
Either way, the context is manual — you do this every session.

**The loop:**
Copilot cannot run terminal commands. It can only suggest code in the editor.
You are the test runner. The loop is:

```
You:      [give context + handoff prompt in Copilot Chat]
Copilot:  [suggests changes to audio_builder.py]
You:      [accept the suggestion in the editor]
You:      [run: py -m pytest tutor/tests/audio/ -v  in your terminal]
You:      [paste failure output back into Copilot Chat]
Copilot:  [suggests a fix]
You:      [accept, run tests again]
... repeat until green
```

**What changes vs Claude Code:**
- You run every test yourself
- You paste failure output back each time
- Context must be re-attached if you close and reopen the chat
- No way to give it the git commands — you create the branch yourself

**Autonomy level:** Level 1 (you are the test runner and feedback loop).

**What stays the same:**
The spec, the handoff prompt structure, the acceptance criteria, and the merge gate
are identical. The discipline does not change — only who runs the tests.

**Practical tip:**
Copilot works best when you give it one file at a time. For Day 13:
1. Open `tutor/models.py` — ask Copilot to add the `TimingEntry` dataclass from the spec
2. Open `tutor/audio/audio_builder.py` — ask it to modify `_concat_with_silence`
3. Ask it to write `test_audio_builder.py` listing the 7 test names from the spec

Smaller, scoped requests produce better results than "implement the whole spec."

---

### OpenCode (SST Terminal TUI)

**What it is:**
OpenCode is an open-source terminal-based AI coding assistant (similar to Claude Code in
concept). It runs in the terminal, supports multiple AI providers, and can read and edit files.

**How context loads:**
OpenCode supports a project rules file. Place your project instructions where OpenCode
expects them (check its documentation for the exact filename — it may be `.opencode/rules.md`
or similar). If it does not auto-load `CLAUDE.md` by name, copy the content into whatever
rules file it does support, or paste it manually at the start of the session.

**The loop:**
OpenCode can run shell commands if configured to do so. The pattern is the same as Claude Code:

```
You:        [start opencode in the project directory]
You:        [paste the handoff prompt]
OpenCode:   [reads project rules / CLAUDE.md equivalent]
            [reads specs/v3/day13.md]
            [runs git, pytest, ruff as permitted]
            [reports when done]
```

**Key difference from Claude Code:**
The permission model may differ. OpenCode may prompt for shell command approval differently
or may not have a `settings.json` equivalent for pre-approving commands. Check its docs.
If it can't run commands autonomously, it drops to Level 1 (you run tests manually).

**What stays the same:**
The spec, the handoff prompt, the acceptance criteria — all identical. The workflow is
tool-agnostic. OpenCode reads the same spec, edits the same files, and should be checked
against the same merge gate.

---

### Aider (CLI, Open Source)

**What it is:**
Aider is a popular open-source CLI coding assistant. You add files to its "chat" explicitly,
then give it instructions. It commits changes automatically.

**How context loads:**
Aider reads a `.aider.conf.yml` for configuration and supports a `CONVENTIONS.md`-style
file. Add `CLAUDE.md` to Aider's read-only context:

```bash
aider --read CLAUDE.md --read specs/v3/day13.md \
      tutor/audio/audio_builder.py tutor/models.py
```

The `--read` files are context-only (Aider won't edit them). The positional files are
editable.

**The loop:**
Aider can run tests with `--test-cmd`:

```bash
aider --test-cmd "py -m pytest tutor/tests/audio/ -v" \
      --read CLAUDE.md --read specs/v3/day13.md \
      tutor/audio/audio_builder.py tutor/models.py
```

With `--test-cmd` set, Aider runs the tests itself after each change and shows you the
output. You still need to tell it to fix failures — it does not loop autonomously by default.

**What changes vs Claude Code:**
- You specify which files to edit upfront (Aider does not infer from the spec)
- Auto-commits: Aider commits each change. Disable with `--no-auto-commits` if you want
  to review before committing.
- Branch management is manual — create `sandbox/day13` yourself before running Aider.

**Autonomy level:** Level 1–2.

---

## Summary: Tool Comparison

| | Claude Code | Copilot Chat | OpenCode | Aider |
|---|---|---|---|---|
| Auto-reads CLAUDE.md | ✅ Yes | ❌ Manual | ⚠️ Check docs | ❌ Manual (`--read`) |
| Runs tests autonomously | ✅ Yes | ❌ No | ⚠️ Depends on config | ⚠️ With `--test-cmd` |
| Full implement→test→fix loop | ✅ Unattended | ❌ You iterate | ⚠️ Partial | ⚠️ Partial |
| Autonomy level | 3–4 | 1 | 1–3 | 1–2 |
| Handoff prompt needed | ✅ Same | ✅ Same + paste CLAUDE.md | ✅ Same | ✅ Same + `--read` flags |
| Spec unchanged | ✅ | ✅ | ✅ | ✅ |
| Merge gate unchanged | ✅ | ✅ | ✅ | ✅ |

**The spec and the handoff prompt are identical across all tools.**
The only thing that changes is who runs the test loop and how much context loading is automatic.

---

## When to Change Which File

| You want to... | Change this |
|---|---|
| Rethink the v3 architecture | `plan/v3_plan.md` |
| Change what Day 13 implements | `specs/v3/day13.md` |
| Change Day 14–16 to reflect Day 13 changes | `specs/v3/day14.md` … `day16.md` |
| Update the activation prompt for Day 13 | `dev_setup/handoff_template.md` (Day 13 section) |
| Add a new gotcha discovered during implementation | `fixes/fix016.md` |
| Change the overall workflow rules | `CLAUDE.md` |
| Change which commands run without permission | `.claude/settings.json` |

**Rule:** Change the plan first. Change the spec second. The spec is what the AI reads.
Never ask the AI to implement from a plan — always from a spec.
