# Container Plan — LearnX Docker Workflow

## 1. What the Container Workflow Solves

A git branch isolates `main` from work-in-progress, but it does not protect your
host machine from the agent running destructive commands like `git push`, `git reset
--hard`, or `git branch -D`. Those commands affect your real repository, your SSH
keys, and potentially your GitHub remote — even from inside a sandbox branch.

Docker adds a second isolation layer. The agent's filesystem access is hard-limited
to `/workspace` (this repo). It cannot reach your home directory, your SSH keys,
other repositories, or the Docker daemon itself. `--dangerously-skip-permissions`
is safe here because the container is the deny rule — not a setting in a config file
that a rogue command could overwrite.

---

## 2. How It Works

```
Host machine                          Docker container (learnx-dev)
─────────────────                     ─────────────────────────────
~/.claude      (read-only mount)  →   /home/dev/.claude
~/.gitconfig   (read-only mount)  →   /home/dev/.gitconfig
project dir    (read-write mount) →   /workspace
                                       ↑
                                  claude --dangerously-skip-permissions
                                  runs here; can write to /workspace only
```

Container CANNOT access: SSH keys, other repos, GitHub remotes, Docker daemon.

The agent runs as non-root user `dev` (UID 1000) inside the container. Files it
creates inside `/workspace` are owned by UID 1000, which on most Linux hosts matches
the primary user. On Windows with Docker Desktop the ownership mapping is handled
automatically.

---

## 3. Starting a Spec Session

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

---

## 4. Why the Deny Rules Were Removed

The four deny rules (`git push`, `git merge`, `git reset`, `git branch -D`) existed
to protect against the agent acting destructively on the real machine. Inside the
container these risks disappear:

- `git push` fails silently — no remote is configured inside the container
- `git merge` and `git reset` affect only `/workspace`, not the host's git state
- `git branch -D` can only delete branches inside the container's clone

The container is the guard. The deny rules were a symptom of not having the guard.

When running in `supervised` or `assisted` mode (on the host), the deny rules in
`.claude/settings.json` are still active. They are only bypassed in `container` and
`yolo` modes where the container boundary already provides the protection.

---

## 5. Rebuilding the Image

Rebuild only when `tutor/requirements.txt` changes or a new system tool is needed.

```powershell
docker build -t learnx-dev .
```

Between spec days the image stays the same. The project code is always mounted fresh
at `/workspace` — changes you make on the host are immediately visible inside the
container on the next run.

---

## 6. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `claude: command not found` | Image not rebuilt after npm install step | `docker build -t learnx-dev .` |
| Tests pass on host, fail in container | Missing dependency in requirements.txt | Add to `tutor/requirements.txt`, rebuild |
| `Permission denied` on mounted files | UID mismatch on Linux host | Add `--user $(id -u)` to docker run call in `learnx_dk.py` |
| `git push` succeeds inside container | Remote was configured inside container | Check `.git/config` inside container; remove remote |
| `audioop-lts` install fails in image | Package only exists for Python 3.13+ | Already handled — see `dev_setup_update/fixes/fix001.md` |
| Playwright browser not found | Browser binary not in image | Rebuild image — `playwright install chromium` runs at build time |
