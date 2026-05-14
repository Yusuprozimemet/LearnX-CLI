# LearnX — How to Use the 4 Dev Modes

## What's actually happening right now

A conversation with Claude Code — you typing, Claude reading files and editing code —
**is** supervised mode. Claude Code running on your host machine. You're already using
the workflow; the launcher just gives you a way to switch modes when starting a new session.

---

## How to launch a mode

The launcher starts a **new Claude Code session**. Run it from PowerShell in the project root:

```powershell
# from C:\Users\HackYourFuture\yusup\LearnX-CLI
python scripts/learnx_dk.py --mode <MODE>
```

That opens a fresh Claude terminal. The mode controls two things: **where** Claude runs
and **what it can do without asking you**.

---

## Mode 1 — supervised (default)

```powershell
python scripts/learnx_dk.py
# same as:
python scripts/learnx_dk.py --mode supervised
```

- Runs Claude on your host machine
- Deny rules in `.claude/settings.json` are active
- Claude will stop and ask you before: `git push`, `git merge`, `git reset`, `git branch -D`
- Everything else prompts normally
- **Use this when:** you want to watch what's happening, you're exploring, or it's a short task

---

## Mode 2 — assisted

```powershell
python scripts/learnx_dk.py --mode assisted
```

- Still runs on your host machine
- Temporarily removes the deny rules for the session (writes a local override file, deletes it when done)
- Claude can `git add`, `git commit`, `git checkout`, `git stash` without asking
- Still asks for `git push` and `git merge` — you keep control of what goes to remote
- **Use this when:** you trust the task scope and the constant approval prompts are slowing you down

---

## Mode 3 — container

```powershell
python scripts/learnx_dk.py --mode container
```

- Runs Claude **inside the `learnx-dev` Docker container**
- Zero prompts — `--dangerously-skip-permissions`
- Claude can only touch `/workspace` (your project folder, mounted read-write)
- Cannot touch your SSH keys, other repos, or push to GitHub (no remote configured inside container)
- **Use this when:** you're handing off a full spec day and want no interruptions

---

## Mode 4 — yolo

```powershell
python scripts/learnx_dk.py --mode yolo --spec specs/v3/dayN.md
```

- Same as container, but after Claude finishes it **automatically runs**:
  1. E2E smoke tests
  2. The multi-agent review pipeline
- You walk away and come back to a complete report
- **Use this when:** you've done this spec before, you trust it, and you want to do something else

---

## Which AI model?

The mode doesn't control the model — **Claude Code controls the model**. Change it with
`/model` inside any Claude session, or in Claude Code settings.

| Model | Speed | Best for |
|---|---|---|
| `claude-sonnet-4-6` | Fast | Default — most tasks |
| `claude-opus-4-7` | Slower, smarter | Complex reasoning, hard bugs |
| `claude-haiku-4-5` | Fastest, cheapest | Simple tasks, quick lookups |

---

## What to actually do day-to-day

**For conversations and quick tasks (like this one):**
Just open Claude Code normally. That's supervised mode. No launcher needed.

**For a spec day with fewer interruptions:**
```powershell
git checkout main
git checkout -b sandbox/dayN
python scripts/learnx_dk.py --mode assisted
# paste the handoff prompt from dev_setup/handoff_template.md
```

**For a full autonomous spec day:**
```powershell
git checkout main
git checkout -b sandbox/dayN
python scripts/learnx_dk.py --mode container
# paste the handoff prompt — walk away
```

**For fully hands-off (implement + test + review, come back to results):**
```powershell
git checkout main
git checkout -b sandbox/dayN
python scripts/learnx_dk.py --mode yolo --spec specs/v3/dayN.md
```

---

## Preview any mode without launching

Add `--dry-run` to see the exact commands that would run, without executing anything:

```powershell
python scripts/learnx_dk.py --mode yolo --spec specs/v3/day13.md --dry-run
```

---

## Quick decision guide

```
Exploring / chatting / short task?        → open Claude Code directly (supervised)
Active spec work, fewer prompts?          → assisted
Full spec day, zero interruptions?        → container
Walk away completely, get full report?    → yolo --spec specs/v3/dayN.md
```

---

## Known rough edges

- **Docker must be running** before using `container` or `yolo` mode
- **Handoff prompt is manual** — copy it from `dev_setup/handoff_template.md` each time
- **Model selection** is separate from mode selection — set it inside the Claude session with `/model`
