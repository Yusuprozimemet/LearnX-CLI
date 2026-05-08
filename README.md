# LearnX CLI

> **Spec-driven development project** — every feature was designed in a written specification before a single line of code was written. See [`specs/`](specs/) for the full day-by-day spec chain.

Turn any Markdown document into an interactive audio tutorial with a live Q&A engine — all from a branded terminal shell.

![LearnX CLI](learnX.png)

---

## What it does

```
.md file → LLM dialogue → TTS audio → interactive player + Q&A
```

1. **Ingests** a Markdown file and chunks it by heading structure or sliding window
2. **Summarises** each chunk with an LLM and plans a teaching curriculum
3. **Generates** a tutor–student (or dual-tutor) dialogue script
4. **Renders** each unit to speech via Microsoft Azure Neural TTS (no TTS API key needed)
5. **Plays back** through an interactive shell with pause, skip, replay, and a live Q&A engine

---

## How it was built — spec-driven development

Each feature day had a written specification reviewed and approved before implementation began:

| Spec | Feature |
|---|---|
| [`specs/day1.md`](specs/day1.md) | Document ingestion — chunking strategies A/B/C |
| [`specs/day2.md`](specs/day2.md) | LLM summarisation and curriculum planning |
| [`specs/day3.md`](specs/day3.md) | Dialogue generation, difficulty levels, caching |
| [`specs/day4.md`](specs/day4.md) | Interactive audio player — state machine, keyboard controls |
| [`specs/day5.md`](specs/day5.md) | Live Q&A engine — grounded answers, session logging |
| [`specs/day6.md`](specs/day6.md) | Dual-tutor format, `--topic` flag, code quality audit |
| [`specs/day7.md`](specs/day7.md) | Branded `/command` shell — REPL, dynamic prompt, logo |

Post-implementation fixes are documented in [`specs/fix.md`](specs/fix.md).  
Architecture plan: [`plan/v1_plan.md`](plan/v1_plan.md).

---

## Quick start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Add your API key
echo "GROQ_API_KEY=gsk_..." > tutor/.env

# 3. Launch the shell
python -m tutor
```

**Requires:** Python 3.11+, [ffmpeg](https://ffmpeg.org/download.html) in PATH.  
**API key:** Free at [console.groq.com](https://console.groq.com).

---

## Setup

### API keys — `tutor/.env`

```env
GROQ_API_KEY=gsk_...          # required — free at console.groq.com
OPENROUTER_API_KEY=sk-or-...  # optional fallback — free at openrouter.ai
```

### ffmpeg

```bash
winget install ffmpeg          # Windows
brew install ffmpeg            # macOS
apt install ffmpeg             # Linux
```

> LearnX auto-detects common Windows install paths (including versioned folders like
> `C:\ffmpeg\ffmpeg-8.x\bin\`) so a terminal restart is not always required.

---

## Shell commands

Launch with `python -m tutor`. The prompt updates dynamically to show player state:

```
LearnX > /generate notes.md --difficulty intermediate
LearnX [▶ 2/5  Pass-by-Value] > /ask what is the difference between == and .equals()?
```

| Command | Description |
|---|---|
| `/generate <file.md> [flags]` | Generate audio from a Markdown file |
| `/play [path]` | Start or resume playback |
| `/pause` | Pause playback |
| `/resume` | Resume playback |
| `/stop` | Stop and unload the player |
| `/next` | Jump to next unit |
| `/prev` | Jump to previous unit |
| `/replay` | Replay current unit |
| `/ask [question]` | Ask a question about the current unit |
| `/summary` | Print unit summary and memory hook |
| `/status` | Show state, unit, elapsed time, Q&A count |
| `/inspect <file.md>` | Show ingestion report — no LLM calls |
| `/dry-run <file.md> [flags]` | Preview curriculum without generating audio |
| `/help [command]` | List all commands or show detail for one |
| `/quit` | Exit LearnX |

### `/generate` flags

| Flag | Default | Description |
|---|---|---|
| `--duration N` | `20` | Target session length in minutes |
| `--difficulty LEVEL` | `beginner` | `beginner` / `intermediate` / `advanced` |
| `--format FORMAT` | `tutor-student` | `tutor-student` or `dual-tutor` |
| `--topic TEXT` | — | Force a specific concept into the curriculum |
| `--units N` | auto | Cap the number of teaching units |
| `--provider NAME` | `groq` | `groq` or `openrouter` |
| `--no-cache` | — | Clear cached summaries and regenerate |
| `--script-only` | — | Print dialogue script; skip audio |
| `--dry-run` | — | Preview curriculum; skip dialogue and audio |
| `--verbose` | — | Show INFO-level logs (per-unit progress) |
| `--debug` | — | Write DEBUG logs to `tutor.log` |

---

## Dialogue formats

**`tutor-student`** (default) — ALEX (tutor) explains; MAYA (student) voices the classic misconception and gets corrected.

**`dual-tutor`** — ALEX lays out the rule; SAM probes edge cases and delivers the memory hook as a peer takeaway.

Voices use [edge-tts](https://github.com/rany2/edge-tts) (Microsoft Azure Neural TTS) — no TTS API key required.

---

## LLM configuration — `tutor/llm_config.toml`

All model names, token budgets, and call settings live in one file. No Python edits needed to switch models or tune limits:

```toml
[providers.groq]
curriculum = "llama-3.3-70b-versatile"
dialogue   = "llama-3.1-8b-instant"

[max_tokens]
dialogue = 1500

[limits]
max_source_tokens = 1500   # raise on paid tier

[llm]
temperature   = 0.7
retry_count   = 2
```

| Provider | Models | Notes |
|---|---|---|
| `groq` (default) | `llama-3.3-70b` (curriculum), `llama-3.1-8b` (dialogue, Q&A) | Free tier, fast |
| `openrouter` | `gemma-3-27b`, `llama-3.1-8b` (free tier) | Fallback option |

---

## Ingestion strategies

Auto-selected based on document size:

| Strategy | Condition | Behaviour |
|---|---|---|
| A | ≤ 6 k tokens | Whole document as one chunk |
| B | 6 k – 60 k tokens | Split on `##` headings |
| C | > 60 k tokens or no headings | Sliding window (2 k tokens, 200-token overlap) |

Run `/inspect <file.md>` to see which strategy was chosen.

---

## Q&A engine

Press `/ask` at any point during playback:

1. Audio pauses automatically
2. Type your question at the prompt
3. The LLM answers in 1–3 seconds, grounded in the source document and prior exchanges
4. Every exchange is saved to `tutorial.session.json`

Use `--no-qa` with `/play` to disable Q&A entirely.

---

## Output files

| File | Contents |
|---|---|
| `tutorial.mp3` | Full concatenated audio |
| `tutorial_units/` | Per-unit `.mp3` files for the player |
| `tutorial.script.txt` | Full dialogue script |
| `tutorial.units.json` | Teaching unit metadata |
| `tutorial.chunks.json` | Source chunks used for Q&A context |
| `tutorial.session.json` | Q&A exchanges from the current session |
| `.tutor_cache/` | Cached summaries and dialogues |

---

## Tests

```bash
python -m pytest
```

40 tests across ingestion, generation, audio, and player modules. No API keys required — all LLM calls are mocked.

---

## Project structure

```
tutor/
  cli/              # Interactive shell (Day 7)
    shell.py        # REPL loop + dynamic prompt
    commands.py     # /command handlers
    logo.py         # ASCII banner
    theme.py        # ANSI colour helpers
  player/           # Audio player (Day 4)
    player.py       # TutorPlayer state machine
    player_display.py
    input_handler.py
  generation/       # LLM pipeline (Days 2–3, 6)
    curriculum.py
    dialogue.py
  ingestion/        # Document parsing (Day 1)
    chunker.py
    summarizer.py
    doc_analyzer.py
  qa/               # Q&A engine (Day 5)
    qa.py
  audio/            # TTS rendering (Day 4)
    audio_builder.py
    tts_renderer.py
  infra/
    llm.py          # LLM client + config loader
  llm_config.toml   # Model names, token budgets, call settings
  prompts/          # Prompt templates
specs/              # Day-by-day feature specifications
plan/               # Architecture planning
```
