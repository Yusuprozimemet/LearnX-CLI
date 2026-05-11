# Day 0 — Repository Cleanup

## Goal

Clean up the repository before adding new infrastructure. Three problems exist today:

1. **`ralphex/` is tracked as a directory** — a cloned reference repo sitting inside
   the project. It is not part of LearnX, should never be committed, and will bloat
   the Docker build context unless excluded.

2. **Loose output files at root** — `tutorial.session.json` and `tutorial_units/` exist
   at the project root. Both match existing `.gitignore` rules (`*.session.json`,
   `tutorial_units/`) but appear in the working tree, which means they were committed
   before those rules were added and are now tracked. They need to be untracked.

3. **`.gitignore` gaps** — `ralphex/`, Docker build artifacts, and the `sandbox/`
   script directory are not covered.

Day 0 has no Python code changes. It is git operations + `.gitignore` edits only.
It must be done before Day 1 so that `.dockerignore` starts from a clean baseline
and the Docker build context does not include `ralphex/` or orphaned output files.

---

## Done (merge gate)

```powershell
# No application code changed — only run ruff to confirm no accidents
py -m ruff check tutor/

# Verify untracked files are gone from git index
git ls-files tutorial.session.json tutorial_units/
# Expected: no output (files are no longer tracked)

git ls-files ralphex/
# Expected: no output (directory is no longer tracked)

# Confirm .gitignore covers new patterns
git check-ignore -v ralphex/
git check-ignore -v tutorial.session.json
```

Report: paste the four command outputs. List each acceptance criterion with pass/fail.
Stop: do not merge to main — wait for human review.

---

## Data boundary

```
Modifies (existing):
  .gitignore               ← add ralphex/, docker artifacts, sandbox/ clarification

Git operations (not file edits):
  git rm --cached tutorial.session.json    ← untrack; file stays on disk
  git rm --cached -r tutorial_units/       ← untrack; directory stays on disk
  git rm --cached -r ralphex/              ← untrack; directory stays on disk

Does NOT touch:
  tutor/          ← no application code
  .claude/        ← no settings changes
  dev_setup/      ← no documentation changes
  Dockerfile      ← does not exist yet (Day 1 creates it)
```

---

## `.gitignore` additions

Add these blocks to `.gitignore` after the existing sections:

```gitignore
# Reference repos — cloned locally for reading, not part of this project
ralphex/

# Docker build artifacts
.docker/
*.dockerignore.bak

# Dev workflow scripts output
scripts/__pycache__/

# sandbox/ prototype scripts — tracked selectively; outputs are not
sandbox/*.log
sandbox/*.json
sandbox/*.mp3
```

Do NOT remove any existing rules. Only append.

---

## Git untracking commands

Run these in order. They remove files from git's index (stops tracking them) without
deleting them from disk. After running, the files still exist locally but git ignores them.

```powershell
# Untrack loose output files at root
git rm --cached tutorial.session.json
git rm --cached -r tutorial_units/

# Untrack ralphex reference repo
git rm --cached -r ralphex/

# Stage the .gitignore change
git add .gitignore

# Verify nothing unexpected is staged
git status
```

Before committing, read `git status` carefully. Only `.gitignore` modifications and
the deleted-from-index files should appear. If any `tutor/` files appear, something
went wrong — do not commit.

---

## Acceptance criteria

- [ ] `git ls-files tutorial.session.json` returns no output (file untracked)
- [ ] `git ls-files tutorial_units/` returns no output (directory untracked)
- [ ] `git ls-files ralphex/` returns no output (directory untracked)
- [ ] `git check-ignore -v ralphex/` shows the new rule from `.gitignore`
- [ ] `.gitignore` contains `ralphex/` rule
- [ ] `.gitignore` contains Docker artifact rules
- [ ] All existing `.gitignore` rules are preserved (no accidental deletions)
- [ ] `py -m ruff check tutor/` exits 0 (no accidental Python changes)
- [ ] `tutorial.session.json` still exists on disk (untracked ≠ deleted)
- [ ] `tutorial_units/` still exists on disk (untracked ≠ deleted)

---

## Tests

This day makes no Python code changes. There are no new pytest functions.
Validation is the four shell commands in the Done section plus the acceptance
criteria checklist above.
