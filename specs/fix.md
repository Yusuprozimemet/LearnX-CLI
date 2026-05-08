# Post-Day-7 Fixes

Bugs and configuration issues discovered and fixed after the full Day 1–7 implementation.

---

## Fix 1 — ffmpeg not found despite being installed

**Symptom**

```
RuntimeWarning: Couldn't find ffmpeg or avconv - defaulting to ffmpeg, but may not work
Error: ffmpeg not found in PATH.
```

**Root cause**

ffmpeg was installed at `C:\ffmpeg\ffmpeg-8.1.1-essentials_build\bin\ffmpeg.exe` (a
versioned subfolder), but the system PATH entry pointed to `C:\ffmpeg\bin\` which did
not exist. `_check_ffmpeg()` only tried `subprocess.run(["ffmpeg", ...])` against PATH
and raised an error immediately on failure.

**Fix** — `tutor/config.py`

`_check_ffmpeg()` now:
1. Tries `ffmpeg -version` via PATH first (fast path).
2. On failure, globs common Windows install layouts: `C:\ffmpeg\bin\`, `C:\ffmpeg\*\bin\`,
   `C:\Program Files\ffmpeg\*\bin\`, `C:\tools\ffmpeg\bin\`.
3. On finding the binary, calls `_inject_ffmpeg(bin_dir)` which:
   - Prepends the directory to `os.environ["PATH"]` for the process lifetime.
   - Patches `pydub.AudioSegment.converter/ffmpeg/ffprobe` so pydub's runtime calls
     also find the binary (eliminating the RuntimeWarning).
4. Only raises `ConfigError` if nothing is found anywhere.

---

## Fix 2 — 413 "Request too large" errors from Groq free tier

**Symptom**

```
Error: LLM call failed after retry: Error code: 413 - {'error': {'message':
'Request too large for model `llama-3.1-8b-instant` ... Limit 6000, Requested 6916 ...'}}
```

**Root cause**

Groq's free tier caps each request (input + output tokens combined) at 6 000 tokens for
`llama-3.1-8b-instant`. The dialogue prompt was:

| Part | Tokens |
|---|---|
| `dialogue.txt` system prompt + speaker constraint | ~630 |
| Unit JSON | ~200 |
| Source text (`MAX_SOURCE_TOKENS = 4 000`) | ~4 000 |
| **Input total** | **~4 830** |
| Expected output (uncapped — Groq uses model max) | ~2 000+ |
| **Request total** | **~6 830 → exceeds 6 000** |

**Fix** — `tutor/llm_config.toml`, `tutor/infra/llm.py`, `tutor/ingestion/summarizer.py`

Three changes applied together:

1. **Lower `max_source_tokens` 4 000 → 1 500** in `llm_config.toml` so dialogue input
   stays around 2 330 tokens.
2. **Add explicit `max_tokens` per call type** passed to the API so Groq can account for
   the full request budget upfront:
   `curriculum 2 000 / dialogue 1 500 / summarize 400 / qa 600`.
3. **Handle 413 as non-retriable** — a structurally oversized prompt will fail every
   time; retrying just wastes quota. The error message now points to `llm_config.toml`.
4. **Truncate chunk text before summarisation** to `max_summarize_input_tokens = 3 000`
   (added to `summarizer.py`) for the same reason.

**Estimated token budget per dialogue call after fix:**

```
Input:  ~630 (prompt) + ~200 (unit) + ~1 500 (source) = ~2 330
Output: 1 500 (capped)
Total:  ~3 830  ← safely under 6 000
```

---

## Fix 3 — LLM settings hardcoded across multiple files

**Symptom**

Model names, token limits, temperature, and retry settings were scattered across
`tutor/constants.py` and `tutor/infra/llm.py` as Python literals. Changing the model
required editing source code.

**Fix** — new file `tutor/llm_config.toml`

All LLM-related configuration moved to a single TOML file. No Python code changes
needed to switch models or tune budgets.

```toml
[providers.groq]
curriculum = "llama-3.3-70b-versatile"
dialogue   = "llama-3.1-8b-instant"

[max_tokens]
dialogue = 1500

[limits]
max_source_tokens = 1500

[llm]
temperature   = 0.7
retry_count   = 2
retry_delay_s = 2.0
```

`tutor/infra/llm.py` reads this file at startup using Python 3.11's built-in `tomllib`
and builds `MODEL_MAP`, `MAX_TOKENS_MAP`, and `LIMITS` from it. The `LIMITS` dict is
exported for use by `dialogue.py` and `summarizer.py`.

---

## Fix 4 — `--verbose` / `--debug` not recognised by `/generate`

**Symptom**

```
LearnX > /generate notes.md --verbose
generate: error: unrecognized arguments: --verbose
Error: could not parse arguments.
```

**Root cause**

`_make_generate_parser()` was extracted from the CLI's `main()` parser but `--verbose`
and `--debug` were not included in the extraction. Additionally, the shell process had
already called `logging.basicConfig()` at startup, making any subsequent `basicConfig`
call a no-op — so calling `_setup_logging(args)` per command would have had no effect
even if the flags existed.

**Fix** — `tutor/tutor.py`, `tutor/cli/commands.py`

1. Added `--verbose` and `--debug` to `_make_generate_parser()`.
2. Added `_apply_log_level(args)` helper in `commands.py` that calls
   `logging.getLogger().setLevel()` directly on the live root logger — this works at
   any point in the process and is not affected by `basicConfig` being already called.
3. `cmd_generate` in the shell calls `_apply_log_level(args)` immediately after parsing.
