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
  → python scripts/learnx_dk.py      # Claude agent runs inside Docker, zero prompts
  → unit tests + E2E smoke tests      # real pipeline: ffprobe · pydub · Playwright
  → 5-agent review (code + product quality)
  → human reads findings + screenshots → merges
```

Four launcher modes:

| Mode | Where | Use when |
|------|-------|----------|
| `supervised` | host | new spec, unfamiliar territory |
| `assisted` | host | trusted scope, iterating fast |
| `container` | Docker | standard autonomous spec day |
| `yolo` | Docker + auto review | walk away, come back to results |

```bash
python scripts/learnx_dk.py                        # supervised (default)
python scripts/learnx_dk.py --mode container
python scripts/learnx_dk.py --mode yolo --spec dev_setup_update/specs/day0.md
```

v4 workflow upgrade in progress — see [`dev_setup_update/update_plan.md`](dev_setup_update/update_plan.md).
