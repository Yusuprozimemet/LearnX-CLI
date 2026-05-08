# Day 2 — Audio Generation

## What works at the end of this day

```bash
python tutor/tutor.py sample_docs/java-basics.md --output java-intro.mp3
```

The command runs the full pipeline: ingestion → curriculum → dialogue → TTS → concatenation. It produces:
- `java-intro.mp3` — the full session audio (playable in any media player)
- `tutorial_units/unit_01_intro.mp3`, `unit_02_*.mp3`, ... — one file per teaching unit
- `tutorial.script.txt` — full dialogue script saved alongside the audio

Two distinct voices are audible (ALEX + MAYA). No symbol leakage (no `<`, `==`, `@Override` in the audio). A progress bar shows TTS generation progress.

## Prerequisites

- Day 1 completed and `--script-only` works
- `ffmpeg` installed and in PATH
  ```
  winget install ffmpeg    # Windows
  ```
- Install the remaining packages:
  ```bash
  pip install edge-tts pydub tqdm
  ```

## Files to create or modify today

Build in this exact order.

---

### 1. `tutor/config.py` — add ffmpeg pre-flight (modify existing)

Add an ffmpeg check to `preflight()`. Only run this check when mode is `"output"` (i.e., `--output` is being used, not `--script-only` / `--dry-run` / `--inspect`).

```python
import subprocess

def _check_ffmpeg() -> None:
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        raise ConfigError(
            "ffmpeg not found in PATH.\n"
            "  Install with: winget install ffmpeg\n"
            "  Then restart your terminal."
        ) from e
```

Call `_check_ffmpeg()` inside `preflight()` when `mode == "output"`. Do not call it for `--inspect`, `--dry-run`, or `--script-only`.

---

### 2. `tutor/audio/tts_renderer.py` (~120 lines)

One responsibility: render a single `DialogueLine` to an mp3 file using edge-tts.

```python
import asyncio
import logging
import os
from pathlib import Path

import edge_tts
from pydub import AudioSegment

from tutor.models import DialogueLine, RenderedSegment
from tutor.constants import VOICE_TUTOR, VOICE_STUDENT, RATE_TUTOR, RATE_STUDENT
from tutor.exceptions import TTSError

log = logging.getLogger(__name__)

VOICE_MAP: dict[str, str] = {
    "ALEX": VOICE_TUTOR,
    "MAYA": VOICE_STUDENT,
    "SAM": VOICE_TUTOR,   # SAM voice overridden on Day 6
}

RATE_MAP: dict[str, str] = {
    "ALEX": RATE_TUTOR,
    "MAYA": RATE_STUDENT,
    "SAM": RATE_TUTOR,
}

async def render_segment(line: DialogueLine, out_dir: str, idx: int) -> RenderedSegment:
    """Render one DialogueLine to an mp3 file. Returns path and duration."""
    voice = VOICE_MAP.get(line.speaker, VOICE_TUTOR)
    rate = RATE_MAP.get(line.speaker, RATE_TUTOR)
    out_path = str(Path(out_dir) / f"seg_{line.unit_number:03d}_{idx:04d}.mp3")

    try:
        communicate = edge_tts.Communicate(line.text, voice, rate=rate)
        await communicate.save(out_path)
    except Exception as e:
        raise TTSError(f"TTS failed for line {idx}: {e}") from e

    try:
        audio = AudioSegment.from_mp3(out_path)
        duration_ms = len(audio)
    except Exception as e:
        raise TTSError(f"Could not read rendered segment {out_path}: {e}") from e

    return RenderedSegment(line=line, audio_path=out_path, duration_ms=duration_ms)
```

Key constraints:
- No knowledge of batching, silence insertion, or concatenation — one segment, one call
- Does not delete its output file — `audio_builder.py` owns cleanup
- `idx` is the global segment index across all units (used to make filenames unique)

---

### 3. `tutor/audio/audio_builder.py` (~150 lines)

Two responsibilities: async batch rendering + assembly into per-unit and full files.

```python
import asyncio
import logging
import os
import shutil
from pathlib import Path

from pydub import AudioSegment
from tqdm import tqdm

from tutor.models import DialogueLine, RenderedSegment
from tutor.constants import (
    TTS_SEMAPHORE_LIMIT,
    SILENCE_BREATH_MS,
    SILENCE_TURN_MS,
    SILENCE_UNIT_MS,
    SILENCE_SESSION_MS,
)
from tutor.audio.tts_renderer import render_segment
from tutor.exceptions import TTSError

log = logging.getLogger(__name__)
```

**Public entry point** (the only async function called from `tutor.py` via `asyncio.run()`):
```python
async def build(lines: list[DialogueLine], out_path: str, units_dir: str) -> None:
    """
    Entry point from tutor.py: asyncio.run(audio_builder.build(...))
    This is the single crossing point from sync → async for the entire pipeline.
    """
    tmp_dir = str(Path(out_path).parent / ".tts_tmp")
    Path(tmp_dir).mkdir(parents=True, exist_ok=True)
    Path(units_dir).mkdir(parents=True, exist_ok=True)

    segments = await _render_all(lines, tmp_dir)
    _assemble(segments, out_path, units_dir)
    _cleanup_tmp(tmp_dir)
    log.info("Audio saved: %s", out_path)
```

**`_render_all`** — async batch with semaphore and progress bar:
```python
async def _render_all(lines: list[DialogueLine], tmp_dir: str) -> list[RenderedSegment]:
    semaphore = asyncio.Semaphore(TTS_SEMAPHORE_LIMIT)
    results: list[RenderedSegment | None] = [None] * len(lines)

    with tqdm(total=len(lines), desc="Generating audio", unit="seg") as pbar:
        async def render_one(idx: int, line: DialogueLine) -> None:
            async with semaphore:
                results[idx] = await render_segment(line, tmp_dir, idx)
                pbar.update(1)

        await asyncio.gather(*[render_one(i, line) for i, line in enumerate(lines)])

    return [r for r in results if r is not None]
```

**`_assemble`** — insert silence, group by unit, save per-unit and full concat:
```python
def _assemble(segments: list[RenderedSegment], out_path: str, units_dir: str) -> None:
    unit_groups: dict[int, list[RenderedSegment]] = {}
    for seg in segments:
        unit_num = seg.line.unit_number
        unit_groups.setdefault(unit_num, []).append(seg)

    unit_audio: list[AudioSegment] = []
    for unit_num in sorted(unit_groups.keys()):
        group = unit_groups[unit_num]
        combined = _concat_with_silence(group)

        unit_label = f"unit_{unit_num:02d}"
        if unit_num == 0:
            unit_label = "unit_00_intro"
        elif unit_num == -1:
            unit_label = "unit_99_outro"

        unit_path = str(Path(units_dir) / f"{unit_label}.mp3")
        combined.export(unit_path, format="mp3")
        log.info("Saved unit: %s", unit_path)

        unit_audio.append(combined)
        if unit_num != -1:
            unit_audio.append(AudioSegment.silent(duration=SILENCE_UNIT_MS))

    full_audio = sum(unit_audio, AudioSegment.empty())
    full_audio.export(out_path, format="mp3")
    log.info("Saved full audio: %s (%d segments)", out_path, len(segments))
```

**`_concat_with_silence`** — insert pause between turns within a unit:
```python
def _concat_with_silence(segments: list[RenderedSegment]) -> AudioSegment:
    result = AudioSegment.empty()
    prev_speaker: str | None = None

    for seg in segments:
        audio = AudioSegment.from_mp3(seg.audio_path)
        if prev_speaker is None:
            pass
        elif prev_speaker == seg.line.speaker:
            result += AudioSegment.silent(duration=SILENCE_BREATH_MS)
        else:
            result += AudioSegment.silent(duration=SILENCE_TURN_MS)
        result += audio
        prev_speaker = seg.line.speaker

    return result
```

**`_cleanup_tmp`** — remove intermediate segment files:
```python
def _cleanup_tmp(tmp_dir: str) -> None:
    shutil.rmtree(tmp_dir, ignore_errors=True)
```

**Critical constraint on `_assemble`:** unit_number = 0 = intro, unit_number = -1 = outro, unit_number 1..N = teaching units. Sort the keys numerically, placing -1 last (outro). The sorted order should be: 0, 1, 2, ..., N, -1. Adjust the sort: `sorted(unit_groups.keys(), key=lambda x: 999 if x == -1 else x)`.

---

### 4. `tutor/tutor.py` — wire in audio generation (modify existing)

In `cmd_generate()`, replace the Day 1 stub:
```python
# was:
print("Audio generation not yet implemented — use --script-only for now.")

# becomes:
script_path = Path(args.output).with_suffix(".script.txt")
units_dir = str(Path(args.output).parent / "tutorial_units")

# save script alongside audio (always)
with open(script_path, "w", encoding="utf-8") as f:
    for line in script:
        f.write(f"{line.speaker}: {line.text}\n")

print(f"Script saved: {script_path}")
print(f"Generating audio — this takes 2–4 minutes for a 20-min session...")

asyncio.run(audio_builder.build(script, args.output, units_dir))

print(f"\nDone.")
print(f"  Audio:  {args.output}")
print(f"  Units:  {units_dir}/")
print(f"  Script: {script_path}")
```

Also add the import:
```python
from tutor.audio import audio_builder
```

---

### 5. Duration estimate printout (add to `tutor.py`)

After `assembler.assemble()` but before the `--script-only` check, print a duration estimate. Add a helper function at the bottom of `tutor.py`:

```python
def _print_duration_estimate(script: list[DialogueLine], units: list[TeachingUnit]) -> None:
    total_words = sum(len(line.text.split()) for line in script)
    dialogue_secs = (total_words / WPM) * 60
    silence_secs = 80  # approx overhead from pauses
    total_secs = int(dialogue_secs + silence_secs)
    mins, secs = divmod(total_secs, 60)
    print(f"\n=== Duration Estimate ===")
    print(f"Script words:  {total_words:,}")
    print(f"Estimated:     ~{mins}m {secs:02d}s (incl. pauses)")
```

Call it after `assemble()`:
```python
script = assembler.assemble(units, all_lines, args.format, doc_title)
_print_duration_estimate(script, units)
```

---

## Acceptance criteria

Run these in order. All must pass.

1. `python tutor/tutor.py sample_docs/java-basics.md --output java-intro.mp3`
   - No errors
   - Progress bar appears and reaches 100%
   - Prints "Done." with file paths

2. `java-intro.mp3` exists and plays in a media player (Windows Media Player, VLC, etc.)

3. Audio contains two distinct voices — ALEX's voice is noticeably different from MAYA's

4. `tutorial_units/` directory contains at least 3 `.mp3` files (intro + units + outro)

5. `tutorial.script.txt` exists and contains `ALEX:` / `MAYA:` lines with no symbols like `<`, `@`, `==`

6. Re-run the command — second run completes faster (dialogue cache hit, only TTS is re-run)

7. Check unit audio files individually — `tutorial_units/unit_01_*.mp3` plays correctly in isolation

---

## Gotchas

**ffmpeg not found**: pydub requires ffmpeg for mp3 export. If you see `FileNotFoundError: [WinError 2] The system cannot find the file specified` inside pydub, your ffmpeg is not in PATH. Restart the terminal after `winget install ffmpeg`.

**edge-tts rate limiting**: Microsoft's TTS endpoint occasionally returns errors under load. The semaphore limits concurrency to 8. If you still see sporadic `TTSError`, reduce `TTS_SEMAPHORE_LIMIT` to 4 in `constants.py` and re-run.

**pydub `.from_mp3()` on empty files**: if edge-tts returns a zero-byte file (rare), pydub raises `CouldntDecodeError`. The fix is to check `os.path.getsize(out_path) > 0` in `render_segment()` before loading, and raise `TTSError` if zero.

**`asyncio.run()` in tutor.py**: do not call `asyncio.run()` from inside any function that is already running inside an event loop (this can happen in Jupyter or certain test runners). In `tutor.py`, `asyncio.run()` is called from the synchronous `cmd_generate()` function — this is correct and safe. Never call `asyncio.run()` from inside `audio_builder.py` itself.

**Outro ordering**: `unit_number = -1` for outro lines means a naive `sorted()` will place them before unit 0. The sort key `lambda x: 999 if x == -1 else x` fixes this. Verify the outro is audible at the end, not the beginning.

**Long silence at unit boundaries**: `SILENCE_UNIT_MS = 1200` adds 1.2 seconds between units. This is intentional — it signals the unit boundary to the listener. Do not reduce it to < 800ms.

**No `--play` yet**: Day 2 only adds `--output`. The `--play` flag prints "Player not yet implemented — use `python tutor.py play <file>` on Day 4." Add this stub so the flag doesn't cause an error.
