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

## Quick start

```powershell
pip install -r requirements.txt
echo "GROQ_API_KEY=gsk_..." > tutor/.env
playwright install chromium
python -m tutor
```

Requires Python 3.12+, [ffmpeg](https://ffmpeg.org/download.html) in PATH.
Free API key at [console.groq.com](https://console.groq.com).

```
LearnX > /generate notes.md    # markdown → dialogue → audio
LearnX > /play                  # interactive player with live Q&A
LearnX > /video                 # render slides + assemble MP4
LearnX > /help                  # all commands
```

---

## How it was built

Spec-driven development — every feature started as a written specification before
any code was written. 16 spec days across v0–v3. Full spec chain in [`specs/`](specs/).

<p align="center">
  <img src="agile.png" alt="Dev loop" />
</p>

---

## Dev workflow

Each spec day follows this loop:

```
write spec → create branch → run yolo → read report → merge
```

Everything runs through one launcher script. Claude implements the spec inside a
Docker container, then E2E tests and a 5-agent review run automatically.

---

## One-time setup

Do this once on a new machine.

**1. Install Docker Desktop**

Download from [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/).
Open Docker Desktop and wait for the status bar to show **"Engine running"**.

**2. Build the Docker image** (from the project root)

```powershell
docker build -t learnx-dev .
```

Takes 2–5 minutes. Only re-run when `requirements.txt` changes.

**3. Activate the Python venv**

```powershell
.\.venv\Scripts\Activate.ps1
```

> If blocked by execution policy:
> `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

---

## Running a spec day

### Step 1 — Open Docker Desktop

Make sure the status bar shows **"Engine running"** before continuing.

### Step 2 — Open a PowerShell window

> Must be a real PowerShell window — not inside a Claude Code session.

```powershell
cd C:\Users\HackYourFuture\yusup\LearnX-CLI
.\.venv\Scripts\Activate.ps1
```

### Step 3 — Create the branch

```powershell
git checkout main
git checkout -b sandbox/dayN
```

Replace `dayN` with the actual day number (e.g. `day18`).

### Step 4 — Dry run

```powershell
python scripts/learnx_dk.py --mode yolo --spec specs/v4/dayN.md --dry-run
```

Prints the 3 commands that will run without executing anything. Check it looks right.

### Step 5 — Launch

```powershell
python scripts/learnx_dk.py --mode yolo --spec specs/v4/dayN.md
```

Claude Code opens inside the container. When you see the `>` prompt, paste:

```
Read specs/v4/dayN.md completely before writing any code.
Branch sandbox/dayN is already created on the host.
Implement exactly what the spec says. Run the merge gate when done and report.
```

Then walk away.

### Step 6 — What happens automatically

After Claude finishes and you see its report, it exits the container. Then automatically:

1. **E2E smoke tests** run inside the container (ffmpeg + Playwright available)
2. **5-agent review** runs — code quality, spec compliance, test coverage, simplification
3. A consolidated report prints with `MERGE READY` or `NEEDS FIXES`

### Step 7 — After the report

If `MERGE READY`:

```powershell
git checkout main
git pull origin main
gh pr create --title "fix(dayN): ..." --body "..."
# or merge directly:
git merge sandbox/dayN
git push origin main
```

If `NEEDS FIXES`: read the findings, fix the issues, re-run the merge gate:

```powershell
python -m pytest tutor/tests/ --ignore=tutor/tests/e2e/ -m "not slow" -v
python -m ruff check tutor/
```

---

## The 4 modes

| Mode | Where Claude runs | Prompts | Use when |
|------|-------------------|---------|----------|
| `supervised` | host | frequent | exploring, short tasks — **current mode when you open Claude Code directly** |
| `assisted` | host | rare | trusted scope, fewer interruptions |
| `container` | Docker | zero | full spec day, no interruptions |
| `yolo` | Docker + auto review | zero | walk away, come back to a full report |

```powershell
python scripts/learnx_dk.py                              # supervised (default)
python scripts/learnx_dk.py --mode assisted
python scripts/learnx_dk.py --mode container
python scripts/learnx_dk.py --mode yolo --spec specs/v4/dayN.md
```

> Always use forward slashes in `--spec`: `specs/v4/dayN.md` not `specs\v4\dayN.md`.
> Backslashes corrupt the path (`\v` is a vertical-tab character).

---

## Which model?

Change model inside any Claude session with `/model`:

| Model | Speed | Best for |
|-------|-------|----------|
| `claude-sonnet-4-6` | fast | default — most tasks |
| `claude-opus-4-7` | slower, smarter | complex reasoning, hard bugs |
| `claude-haiku-4-5` | fastest | simple tasks, quick lookups |
