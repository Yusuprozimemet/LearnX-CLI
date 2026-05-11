# Day 4 — Dev_Setup Documentation Update

## Goal

Update the dev_setup documentation to reflect the new container-based workflow.
Days 1–3 changed the tools; Day 4 changes the documentation so that future sessions
start from the correct mental model.

Three changes:
1. Create `dev_setup/container_plan.md` — the primary reference for the Docker workflow.
2. Add a "Level 4 via Container" section to `dev_setup/autonomy_plan.md`.
3. Add a container-mode handoff block to `dev_setup/handoff_template.md`.

No code changes. No infrastructure changes. This day is documentation only.

---

## Done (merge gate)

```powershell
# No pytest additions for this day. Full suite must still pass.
py -m pytest
py -m ruff check tutor/
py -m ruff format --check tutor/
```

Report: paste gate output. List each acceptance criterion with pass/fail.
Stop: do not merge to main — wait for human review.

---

## Data boundary

```
Creates (new):
  dev_setup/container_plan.md         ← primary reference for Docker workflow

Modifies (existing):
  dev_setup/autonomy_plan.md          ← add Level 4 via Container section
  dev_setup/handoff_template.md       ← add container-mode handoff block

Does NOT touch:
  tutor/                  ← no application code
  Dockerfile              ← already created in Day 1
  scripts/                ← already created in Days 2–3
  .claude/                ← already updated in Days 2–3
  specs/v3/               ← no spec changes
```

---

## `dev_setup/container_plan.md` — required sections

Write this file from scratch. It must contain at minimum:

### 1. What the Container Workflow Solves (one paragraph)

Explain that git branch isolation protects `main` but does not protect your machine
from the agent running `git push`, `git reset`, or destructive commands. Docker adds
a second isolation layer: the agent's filesystem access is limited to `/workspace`.

### 2. How It Works (diagram + prose)

```
Host machine                          Docker container (learnx-dev)
─────────────────                     ─────────────────────────────
~/.claude      (read-only mount)  →   /home/dev/.claude
~/.gitconfig   (read-only mount)  →   /home/dev/.gitconfig
E:/HYF/backend (read-write mount) →   /workspace
                                       ↑
                                  claude --dangerously-skip-permissions
                                  runs here; can write to /workspace only
```

Container CANNOT access: SSH keys, other repos, GitHub remotes, Docker daemon.

### 3. Starting a Spec Session (step-by-step)

```powershell
# 1. Create sandbox branch (on host, as usual)
git checkout main
git checkout -b sandbox/dayN

# 2. Start the agent inside the container
python scripts/learnx_dk.py

# 3. Give the handoff prompt (see handoff_template.md container section)
# Agent implements → runs python -m pytest → fixes → reports done

# 4. Run review (on host or inside container)
python scripts/run_review.py --spec specs/v3/dayN.md

# 5. Human reads findings + diff, then merges (on host, as usual)
git checkout main
git merge sandbox/dayN
git branch -d sandbox/dayN
```

### 4. Why the Deny Rules Were Removed

The four deny rules (`git push`, `git merge`, `git reset`, `git branch -D`) existed to
protect against the agent acting destructively on the real machine. Inside the container:
- `git push` fails silently — no remote is configured
- `git merge` and `git reset` affect only `/workspace`, not the host's git state
- `git branch -D` can only delete branches inside the container's clone

The container is the guard. The deny rules were a symptom of not having the guard.

### 5. Rebuilding the Image

When to rebuild: only when `requirements.txt` changes or a new system tool is needed.

```powershell
docker build -t learnx-dev .
```

Between spec days: the image stays the same. The project code is always mounted fresh.

### 6. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `claude: command not found` | Image not rebuilt after adding npm install | `docker build -t learnx-dev .` |
| Tests pass on host, fail in container | Missing dependency in requirements.txt | Add to requirements.txt, rebuild |
| `Permission denied` on mounted files | UID mismatch | Add `--user $(id -u)` to docker run call in learnx_dk.py |
| `git push` succeeds inside container | Remote was configured inside container | Check `.git/config` inside container; remove remote |

---

## `dev_setup/autonomy_plan.md` — section to add

Add this section after the existing "Level 3" section (before "The Honest Boundaries"):

```markdown
### Level 4 — Autonomous session via Docker container (the goal state)

```
You: python scripts/learnx_dk.py
     [paste handoff prompt inside the container session]
     [walk away]
Claude: [implements → runs python -m pytest → reads output → fixes → runs again → reports]
You: python scripts/run_review.py --spec specs/v3/dayN.md
     [read findings, read diff, merge or push back]
```

This is Level 4 because:
- You do not approve individual commands (--dangerously-skip-permissions)
- You do not run tests yourself (agent runs python -m pytest directly)
- You do not watch the session (container handles isolation)
- You return to a report, not a question

Level 4 is safe here because the container is the sandbox. The four-pillar structure
(spec-driven, context hygiene, sandbox branch, acceptance criteria exit condition) is
unchanged. The container adds a hard filesystem boundary on top of the branch boundary.
```

---

## `dev_setup/handoff_template.md` — block to add

Add a "Container Mode" section at the top of the file, before the existing template.
Mark the existing template as "Host Mode (Level 1–3)".

The container-mode block:

```markdown
## Container Mode (Level 4) — Recommended

Use this when you want uninterrupted autonomous execution.

### Prerequisites
- `docker build -t learnx-dev .` has been run at least once
- You are on a `sandbox/dayN` branch (created on the host as usual)

### Handoff steps

1. Start the container session:
   ```powershell
   python scripts/learnx_dk.py
   ```

2. Paste this prompt inside the container Claude session:
   ```
   Spec:         specs/v3/day<N>.md
   Branch:       sandbox/day<N> (already created on host)
   Files:        [list from spec data boundary]
   Test command: python -m pytest tutor/tests/<folder>/ -v
   Merge gate:   python -m pytest && python -m ruff check tutor/

   Implement all changes in the spec. Run tests after each change.
   Fix failures. When all acceptance criteria are green and the gate passes,
   report: which criteria are green, gate output, files changed.
   ```

3. Walk away. Come back when the agent reports.

4. Run the review from the host:
   ```powershell
   python scripts/run_review.py --spec specs/v3/day<N>.md
   ```

5. Read findings + `git diff main...HEAD`. Merge if clean.
```

---

## Acceptance criteria

- [ ] `dev_setup/container_plan.md` exists and contains all 6 required sections
- [ ] Section 2 contains the host ↔ container volume diagram
- [ ] Section 3 contains the 5-step session start sequence
- [ ] Section 4 explains why deny rules were removed
- [ ] `dev_setup/autonomy_plan.md` has a "Level 4 via Docker container" section
- [ ] Level 4 section explains what makes it safe (container = sandbox, not just trust)
- [ ] `dev_setup/handoff_template.md` has a "Container Mode (Level 4)" block at the top
- [ ] Container-mode block has the exact handoff prompt template
- [ ] Existing host-mode template is preserved (not deleted), marked "Host Mode (Level 1–3)"
- [ ] All three files pass a read-through: no broken references, no TODO placeholders left

---

## Tests

This day creates documentation files only. There are no new pytest functions.

Validation: read each file against the acceptance criteria above. Each `- [ ]` item is a
checklist you tick manually after reading the file. If a section is missing or a reference
is broken, fix the file before marking the criterion done.
