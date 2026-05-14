# LearnX

![CI](https://github.com/Yusuprozimemet/LearnX-CLI/actions/workflows/ci.yml/badge.svg)

Turn any Markdown document into an audio tutorial and MP4 video from a terminal shell.

```
.md file → LLM curriculum → TTS audio → interactive player + Q&A
                           → LLM segment plan → HTML slides → MP4 video
```

<p align="center">
  <img src="learnX.png" alt="LearnX CLI output" />
</p>

---

## How it was built

Every feature started as a written specification before any code was written —
spec-driven development with an agile outer loop and a waterfall inner loop per spec day.
16 spec days across v0–v3. Full spec chain in [`specs/`](specs/).

<p align="center">
  <img src="agile.png" alt="Dev loop" />
</p>

---

## Quick start

```bash
pip install -r requirements.txt
echo "GROQ_API_KEY=gsk_..." > tutor/.env
playwright install chromium   # for /video
python -m tutor
```

Requires Python 3.12+, [ffmpeg](https://ffmpeg.org/download.html) in PATH.
Free API key at [console.groq.com](https://console.groq.com).

```
LearnX > /generate notes.md          # markdown → dialogue → audio
LearnX > /play                        # interactive player with live Q&A
LearnX > /video                       # render slides + assemble MP4
LearnX > /help                        # all commands
```

---

## Dev workflow

The development loop used to build LearnX — and to continue building it:

```
write spec
  → git checkout -b sandbox/dayN
  → py scripts/learnx_dk.py           # Claude agent runs, zero prompts
  → unit tests + E2E smoke tests      # real pipeline: ffprobe · pydub · Playwright
  → 5-agent review (code + product quality)
  → human reads findings + screenshots → merges
```

---

### Step 0 — One-time setup

These steps only need to be done once on a new machine.

#### 1. Install Docker Desktop

Download and install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/).
After install, open Docker Desktop and wait until the status bar shows **"Engine running"**.

Verify it works:
```powershell
docker version
```
You should see both Client and Server versions printed.

#### 2. Build the Docker image

Run this once from the project root. Only re-run when `requirements.txt` changes.

```powershell
docker build -t learnx-dev .
```

This takes 2-5 minutes the first time. When it finishes you should see:
```
Successfully tagged learnx-dev:latest
```

Verify the image exists:
```powershell
docker images learnx-dev
```

#### 3. Activate the Python virtual environment

```powershell
.\.venv\Scripts\Activate.ps1
```

Your prompt will change to show `(LearnX-CLI)` at the start. After activation,
`py` and `python` both use the project venv.

> If you get a permissions error, run this first:
> `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

---

### The 4 launcher modes

Everything goes through one command run from the project root. The mode controls
**where** Claude runs and **what it can do without asking you**.

```powershell
py scripts/learnx_dk.py --mode <MODE>
```

| Mode | Where Claude runs | Prompts | Use when |
|------|-------------------|---------|----------|
| `supervised` | host machine | frequent — risky ops blocked | exploring, short tasks, watching every step |
| `assisted` | host machine | rare — only push/merge to remote | trusted scope, fewer interruptions |
| `container` | Docker | zero | full spec day, no interruptions |
| `yolo` | Docker + auto review | zero | walk away, come back to a full report |

#### supervised (default)

```powershell
py scripts/learnx_dk.py
```

Claude runs on your host machine. Deny rules in `.claude/settings.json` are
active — Claude stops and asks before `git push`, `git merge`, `git reset`,
`git branch -D`. **This is the mode you are in when you open Claude Code directly.**

#### assisted

```powershell
py scripts/learnx_dk.py --mode assisted
```

Still on host, but deny rules are temporarily lifted for the session. Claude can
`git add`, `git commit`, `git stash` freely. `git push` and `git merge` to remote
still prompt — you keep control of what leaves your machine.

#### container

```powershell
py scripts/learnx_dk.py --mode container
```

Claude runs inside the `learnx-dev` Docker container with
`--dangerously-skip-permissions`. Zero prompts. Claude can only touch
`/workspace` (the project folder). Cannot reach your SSH keys, other repos,
or the GitHub remote.

Requires Docker Desktop running and the `learnx-dev` image built (see Step 0).

#### yolo

```powershell
py scripts/learnx_dk.py --mode yolo --spec specs/v4/dayN.md
```

Same as container, but after Claude exits it automatically runs E2E smoke tests
then the multi-agent review pipeline. Walk away and come back to a full report.

---

### Running a spec day end-to-end (yolo)

Follow these steps in order every time you start a new spec day.

**Step 1 — Check Docker is running**

Open Docker Desktop. The status bar must show **"Engine running"** before you
continue. If it shows "starting", wait 30 seconds and check again.

**Step 2 — Activate the venv** (if not already active)

```powershell
.\.venv\Scripts\Activate.ps1
```

**Step 3 — Create the sandbox branch**

Always branch from `main`, never from another sandbox branch.

```powershell
git checkout main
git checkout -b sandbox/day17
```

**Step 4 — Dry run to confirm everything is wired up**

```powershell
py scripts/learnx_dk.py --mode yolo --spec specs/v4/day17.md --dry-run
```

This prints the 3 commands that will run — nothing is executed. Check that:
- Step 1 shows a `docker run` command with `-v .../LearnX-CLI:/workspace`
- Step 2 shows your venv Python path followed by `-m pytest tutor/tests/e2e/`
- Step 3 shows your venv Python path followed by `scripts/run_review.py`

If it looks correct, proceed.

**Step 5 — Launch**

```powershell
py scripts/learnx_dk.py --mode yolo --spec specs/v4/day17.md
```

> **Important:** this command must be run from a real PowerShell terminal, not
> from inside a Claude Code session. The `docker run -it` flag requires a real
> TTY. Open a new PowerShell window if you are currently inside Claude Code.

When the container opens and Claude prompts you, paste this (replace `day17`
with the actual day number):

```
Read specs/v4/day17.md completely before writing any code.
Branch sandbox/day17 is already created on the host.
Implement exactly what the spec says. Run the merge gate when done and report.
```

Then walk away. When it finishes you will see:
1. Claude's implementation report in the terminal
2. E2E test results printed automatically
3. Review pipeline output (5-agent code + product quality check)

**Step 6 — Review and merge**

Read the findings. If everything looks good, merge from your host:

```powershell
git checkout main
git merge sandbox/day17
```

> **Path note:** always use forward slashes in `--spec` (`specs/v4/day17.md`),
> not backslashes. Backslashes in paths like `specs\v4\...` contain `\v` which
> is a vertical-tab character and silently corrupts the path.

---

### Which model?

The mode does not control which Claude model is used. Change it inside any
Claude session with `/model`:

| Model | Speed | Best for |
|-------|-------|----------|
| `claude-sonnet-4-6` | fast | default — most tasks |
| `claude-opus-4-7` | slower, smarter | complex reasoning, hard bugs |
| `claude-haiku-4-5` | fastest | simple tasks, quick lookups |

---

### Quick decision guide

```
Chatting / exploring / short task?        → open Claude Code directly (supervised)
Active spec work, fewer interruptions?    → assisted
Full spec day, zero interruptions?        → container
Walk away, get a full report?             → yolo --spec specs/v4/dayN.md
```

---

### Preview any mode without launching

```powershell
py scripts/learnx_dk.py --mode yolo --spec specs/v4/day17.md --dry-run
py scripts/learnx_dk.py --mode container --dry-run
py scripts/learnx_dk.py --mode assisted --dry-run
```

Prints the exact shell commands that would run — nothing is executed.


