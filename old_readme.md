# LearnX CLI

Turn any Markdown document into an interactive audio tutorial. The CLI reads your `.md` file, breaks it into teaching units, generates a tutor–student dialogue with an LLM, renders it to speech, and plays it back with a live Q&A engine.

```
.md file → LLM dialogue → TTS audio → interactive player
```

---

## Quick start

```bash
# 1. Install dependencies
pip install -r requirements.txt      # or: pip install edge-tts pydub pygame-ce openai python-dotenv audioop-lts

# 2. Add your API key
echo "GROQ_API_KEY=gsk_..." > tutor/.env

# 3. Generate and play
python -m tutor.tutor sample_docs/java-basics.md --play
```

**Requires:** Python 3.11+, [ffmpeg](https://ffmpeg.org/download.html) in PATH.

---

## Setup

### API keys

Create `tutor/.env`:

```env
GROQ_API_KEY=gsk_...          # free at console.groq.com
OPENROUTER_API_KEY=sk-or-...  # optional fallback, free at openrouter.ai
```

### ffmpeg

```bash
# Windows
winget install ffmpeg

# macOS
brew install ffmpeg

# Linux
apt install ffmpeg
```

---

## Commands

### Generate audio

```bash
python -m tutor.tutor <input.md> [options]
```

| Option | Default | Description |
|---|---|---|
| `--output FILE` | `tutorial.mp3` | Output audio file path |
| `--duration MIN` | `20` | Target session length in minutes |
| `--format FORMAT` | `tutor-student` | `tutor-student` or `dual-tutor` |
| `--difficulty LEVEL` | `beginner` | `beginner`, `intermediate`, or `advanced` |
| `--units N` | auto | Cap the number of teaching units |
| `--topic TEXT` | — | Force a specific concept into the curriculum |
| `--provider NAME` | `groq` | `groq` or `openrouter` |
| `--play` | — | Launch the player immediately after generation |
| `--script-only` | — | Print the dialogue script; skip audio generation |
| `--dry-run` | — | Show curriculum plan; skip dialogue and audio |
| `--inspect` | — | Show ingestion report; skip everything else |
| `--show-summaries` | — | Print chunk summaries (use with `--inspect`) |
| `--no-cache` | — | Clear cached summaries and dialogues |
| `--verbose` | — | Show INFO-level logs |
| `--debug` | — | Write DEBUG logs to `tutor.log` |

### Play existing audio

```bash
python -m tutor.tutor play <tutorial_units/>
python -m tutor.tutor play tutorial_units/ --no-qa
```

The `play` subcommand takes the path to the `tutorial_units/` directory created during generation.

| Option | Description |
|---|---|
| `--no-qa` | Disable the `?` key; listen-only mode |
| `--provider NAME` | LLM provider for Q&A answers |

---

## Examples

```bash
# Inspect a document — see how it will be chunked, no LLM calls
python -m tutor.tutor notes.md --inspect

# Preview the curriculum without generating anything
python -m tutor.tutor notes.md --dry-run

# Print the full dialogue script
python -m tutor.tutor notes.md --script-only

# Generate a 30-minute intermediate session on HashMap
python -m tutor.tutor notes.md \
  --duration 30 \
  --difficulty intermediate \
  --topic "HashMap internals" \
  --output session.mp3

# Dual-tutor format: two experts (ALEX + SAM) instead of tutor + student
python -m tutor.tutor notes.md --format dual-tutor --output dual.mp3

# Generate then play in one command
python -m tutor.tutor notes.md --play

# Play a previously generated session
python -m tutor.tutor play tutorial_units/

# Regenerate everything fresh, bypassing the cache
python -m tutor.tutor notes.md --no-cache --script-only
```

---

## Player keyboard controls

When the player is running:

| Key | Action |
|---|---|
| `space` | Pause / resume |
| `n` | Next unit |
| `b` | Previous unit |
| `r` | Replay current unit |
| `s` | Print unit summary and memory hook |
| `?` | Ask a question (Q&A engine) |
| `q` | Quit |

---

## Q&A engine

Press `?` at any point during playback:

1. Audio pauses
2. A question prompt appears showing the current topic and position
3. Type your question and press Enter
4. The LLM answers in 1–3 seconds, grounded in the source document
5. Press `space` to resume

Every exchange is saved to `tutorial.session.json` alongside the audio.

Use `--no-qa` to disable Q&A entirely.

---

## Output files

After generation, the working directory contains:

| File | Contents |
|---|---|
| `tutorial.mp3` | Full concatenated audio |
| `tutorial_units/` | Per-unit `.mp3` files for the player |
| `tutorial.script.txt` | Full dialogue script |
| `tutorial.units.json` | Teaching unit metadata |
| `tutorial.chunks.json` | Source chunks used for Q&A context |
| `tutorial.session.json` | Q&A exchanges from the current session |
| `.tutor_cache/` | Cached summaries and dialogues (delete with `--no-cache`) |

---

## Dialogue formats

**`tutor-student`** (default): ALEX (tutor) explains; MAYA (student) makes the classic misconception, gets corrected.

**`dual-tutor`**: ALEX lays out the rule; SAM probes edge cases, voices beginner doubts, and delivers the memory hook.

Voices use Microsoft Azure Neural TTS via [edge-tts](https://github.com/rany2/edge-tts) — no API key needed for TTS.

---

## Ingestion strategies

The CLI auto-selects a chunking strategy based on document size:

| Strategy | Condition | Behaviour |
|---|---|---|
| A | ≤ 6k tokens | Single chunk — full document sent as one unit |
| B | 6k–60k tokens | Split on `##` headings |
| C | > 60k tokens or no headings | Sliding window (2k tokens, 200-token overlap) |

Run `--inspect` to see which strategy was chosen and how many chunks were created.

---

## Difficulty levels

| Level | Word budget multiplier | Suitable for |
|---|---|---|
| `beginner` | ×1.3 (more words, more analogies) | No prior Java experience |
| `intermediate` | ×1.0 | 3+ months of Java |
| `advanced` | ×0.8 (denser, fewer analogies) | OOP-fluent, design-level focus |

---

## Running tests

```bash
python -m pytest
```

40 tests across ingestion, generation, audio, and player modules. No API keys required — LLM calls are mocked.

---

## LLM providers

| Provider | Models used | Notes |
|---|---|---|
| `groq` (default) | `llama-3.3-70b` (curriculum), `llama-3.1-8b` (dialogue, Q&A) | Free tier, fast |
| `openrouter` | `gemma-3-27b`, `llama-3.1-8b` (free tier) | Fallback option |

Rate-limit retries with exponential backoff are built in. Switch providers with `--provider openrouter`.
