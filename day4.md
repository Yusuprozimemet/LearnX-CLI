# Day 4 — Interactive Player

## What works at the end of this day

```bash
python tutor/tutor.py play tutorial_units/  # play by units directory
python tutor/tutor.py sample_docs/java-basics.md --play  # generate + play
```

The interactive player runs in the terminal. Audio plays unit by unit. The status bar shows the current unit, elapsed time, and available commands. All keyboard commands work: space (pause/resume), n (next), b (back), r (replay), s (summary), q (quit). Q&A is not yet wired — pressing `?` prints "Q&A available on Day 5."

## Prerequisites

- Day 2 completed and `tutorial_units/` directory with unit `.mp3` files exists
- Install pygame:
  ```bash
  pip install pygame
  ```

---

## Files to create today

---

### 1. `tutor/player/__init__.py` (empty)

---

### 2. `tutor/player/input_handler.py` (~70 lines)

Platform shim for non-blocking single-keypress input. No state, no side effects.

```python
import sys
import logging

log = logging.getLogger(__name__)

def get_key() -> str | None:
    """Return the pressed key as a string, or None if no key is available."""
    if sys.platform == "win32":
        return _get_key_windows()
    return _get_key_unix()


def _get_key_windows() -> str | None:
    import msvcrt
    if msvcrt.kbhit():
        raw = msvcrt.getch()
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return None
    return None


def _get_key_unix() -> str | None:
    try:
        import readchar
        import threading

        result: list[str | None] = [None]

        def _read() -> None:
            result[0] = readchar.readchar()

        t = threading.Thread(target=_read, daemon=True)
        t.start()
        t.join(timeout=0.05)   # 50ms non-blocking window
        return result[0]
    except ImportError:
        log.warning("readchar not installed — keyboard input unavailable on non-Windows. pip install readchar")
        return None
```

---

### 3. `tutor/player/player_display.py` (~90 lines)

All terminal rendering lives here. No string formatting elsewhere in the player.

```python
import sys
import logging
from tutor.models import TeachingUnit
from tutor.constants import PLAYER_BAR_WIDTH

log = logging.getLogger(__name__)

PLAYER_BAR_WIDTH = 50   # add to constants.py

BORDER = "━" * 56
COMMANDS_PLAYING = "  [space] pause   [?] ask   [n] next   [b] prev   [q] quit"
COMMANDS_PAUSED  = "  [space] resume   [?] ask   [n] next   [b] prev   [r] replay   [s] summary   [q] quit"


def render_status(
    unit: TeachingUnit,
    unit_idx: int,
    total_units: int,
    elapsed_s: int,
    total_s: int,
    state: str,
) -> None:
    """Redraw the status bar in-place using \\r. Does not scroll."""
    bar = _progress_bar(elapsed_s, total_s)
    elapsed_fmt = _fmt_time(elapsed_s)
    total_fmt = _fmt_time(total_s)
    state_tag = "  ⏸ PAUSED" if state == "PAUSED" else ""

    line1 = f"  {unit.concept} — Unit {unit_idx}/{total_units}{state_tag}"
    line2 = f"  {bar}  {elapsed_fmt} / {total_fmt}"
    cmds = COMMANDS_PAUSED if state in ("PAUSED", "ASKING") else COMMANDS_PLAYING

    sys.stdout.write(f"\r\033[2K{BORDER}\n{line1}\n{line2}\n{BORDER}\n{cmds}\n")
    sys.stdout.flush()


def clear_status() -> None:
    """Clear 5 lines of status bar output."""
    for _ in range(5):
        sys.stdout.write("\033[F\033[2K")
    sys.stdout.flush()


def print_summary(unit: TeachingUnit) -> None:
    print(f"\n{BORDER}")
    print(f"  Summary: {unit.concept}")
    print(f"  Key facts:")
    for fact in unit.key_facts:
        print(f"    • {fact}")
    print(f"  Remember: {unit.memory_hook}")
    print(f"{BORDER}\n")


def print_session_complete(unit_count: int, total_s: int, qa_count: int) -> None:
    print(f"\n{BORDER}")
    print(f"  Session complete: {unit_count} units, {_fmt_time(total_s)}")
    if qa_count:
        print(f"  You asked {qa_count} question(s) this session.")
    print(f"{BORDER}")
    print("  [r] replay session   [q] quit\n")


def _progress_bar(elapsed_s: int, total_s: int) -> str:
    if total_s <= 0:
        return "[" + "░" * PLAYER_BAR_WIDTH + "]"
    ratio = min(elapsed_s / total_s, 1.0)
    filled = int(ratio * PLAYER_BAR_WIDTH)
    empty = PLAYER_BAR_WIDTH - filled
    return "[" + "█" * filled + "░" * empty + "]"


def _fmt_time(seconds: int) -> str:
    m, s = divmod(max(seconds, 0), 60)
    return f"{m:02d}:{s:02d}"
```

Add `PLAYER_BAR_WIDTH = 40` to `constants.py`.

---

### 4. `tutor/player/player.py` (~200 lines)

State machine + event loop. Calls `player_display` and `input_handler`. Does not format strings for display.

```python
import logging
import os
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Literal

import pygame

from tutor.models import TeachingUnit
from tutor.player import player_display, input_handler
from tutor.exceptions import PlayerError
from tutor.constants import PLAYER_POLL_HZ

log = logging.getLogger(__name__)

PlayerState = Literal["PLAYING", "PAUSED", "ASKING", "ANSWERING", "STOPPED"]

MUSIC_END = pygame.USEREVENT + 1


@dataclass
class TutorPlayer:
    unit_files: list[str]           # sorted paths to tutorial_units/*.mp3
    units: list[TeachingUnit]       # parallel list of unit metadata
    qa_count: int = 0               # how many questions asked this session
    _state: PlayerState = field(default="PAUSED", init=False)
    _current_idx: int = field(default=0, init=False)
    _start_time: float = field(default=0.0, init=False)
    _pause_start: float = field(default=0.0, init=False)
    _paused_elapsed: float = field(default=0.0, init=False)
```

**`run()` method** — the main loop:
```python
def run(self) -> None:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    pygame.mixer.init()
    pygame.mixer.music.set_endevent(MUSIC_END)

    self._load_unit(0)
    self._play()

    poll_interval = 1.0 / PLAYER_POLL_HZ

    try:
        while self._state != "STOPPED":
            self._handle_events()
            self._handle_keys()
            self._redraw()
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        pass
    finally:
        pygame.mixer.quit()
        pygame.quit()
```

**State transitions:**

```python
def _play(self) -> None:
    pygame.mixer.music.play()
    self._state = "PLAYING"
    self._start_time = time.time()

def _pause(self) -> None:
    pygame.mixer.music.pause()
    self._pause_start = time.time()
    self._state = "PAUSED"

def _resume(self) -> None:
    pygame.mixer.music.unpause()
    paused_for = time.time() - self._pause_start
    self._start_time += paused_for
    self._state = "PLAYING"

def _load_unit(self, idx: int) -> None:
    if idx >= len(self.unit_files):
        self._on_session_complete()
        return
    self._current_idx = idx
    self._paused_elapsed = 0.0
    pygame.mixer.music.load(self.unit_files[idx])
    log.info("Loaded unit %d: %s", idx, self.unit_files[idx])
```

**Event handling:**

```python
def _handle_events(self) -> None:
    for event in pygame.event.get():
        if event.type == MUSIC_END and self._state == "PLAYING":
            next_idx = self._current_idx + 1
            if next_idx < len(self.unit_files):
                self._load_unit(next_idx)
                self._play()
            else:
                self._on_session_complete()

def _handle_keys(self) -> None:
    if self._state in ("ASKING", "ANSWERING"):
        return
    key = input_handler.get_key()
    if key is None:
        return
    dispatch: dict[str, callable] = {
        " ": self._toggle_play_pause,
        "p": self._toggle_play_pause,
        "n": self._next_unit,
        "b": self._prev_unit,
        "r": self._replay_unit,
        "s": self._print_summary,
        "q": self._quit,
        "?": self._ask_question,
    }
    action = dispatch.get(key)
    if action:
        action()

def _toggle_play_pause(self) -> None:
    if self._state == "PLAYING":
        self._pause()
    elif self._state == "PAUSED":
        self._resume()

def _next_unit(self) -> None:
    was_playing = self._state == "PLAYING"
    pygame.mixer.music.stop()
    next_idx = min(self._current_idx + 1, len(self.unit_files) - 1)
    self._load_unit(next_idx)
    if was_playing:
        self._play()

def _prev_unit(self) -> None:
    was_playing = self._state == "PLAYING"
    pygame.mixer.music.stop()
    prev_idx = max(self._current_idx - 1, 0)
    self._load_unit(prev_idx)
    if was_playing:
        self._play()

def _replay_unit(self) -> None:
    pygame.mixer.music.stop()
    self._load_unit(self._current_idx)
    self._play()

def _print_summary(self) -> None:
    if self._current_idx < len(self.units):
        player_display.print_summary(self.units[self._current_idx])

def _quit(self) -> None:
    pygame.mixer.music.stop()
    self._state = "STOPPED"

def _ask_question(self) -> None:
    # Day 5: Q&A wired here. Day 4: stub.
    if self._state == "PLAYING":
        self._pause()
    print("\nQ&A available from Day 5 — press [space] to resume.")
```

**Redraw + elapsed time tracking:**

```python
def _redraw(self) -> None:
    if self._state == "STOPPED" or self._current_idx >= len(self.units):
        return
    unit = self.units[self._current_idx]
    elapsed_s = self._elapsed_seconds()
    total_s = self._unit_duration_s()
    player_display.render_status(
        unit=unit,
        unit_idx=self._current_idx + 1,
        total_units=len(self.units),
        elapsed_s=elapsed_s,
        total_s=total_s,
        state=self._state,
    )

def _elapsed_seconds(self) -> int:
    if self._state == "PAUSED":
        return int(self._pause_start - self._start_time)
    if self._state == "PLAYING":
        return int(time.time() - self._start_time)
    return 0

def _unit_duration_s(self) -> int:
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_mp3(self.unit_files[self._current_idx])
        return len(audio) // 1000
    except Exception:
        return 0   # unknown duration is acceptable

def _on_session_complete(self) -> None:
    self._state = "STOPPED"
    player_display.print_session_complete(
        unit_count=len(self.units),
        total_s=sum(self._get_duration(f) for f in self.unit_files),
        qa_count=self.qa_count,
    )
```

---

### 5. `tutor/tutor.py` — implement `play` subcommand (modify existing)

Replace the Day 1 `cmd_play` stub:

```python
def cmd_play(args) -> None:
    from tutor.player.player import TutorPlayer

    # Resolve unit files
    if hasattr(args, "audio_file"):
        # "play" subcommand: find units dir alongside the audio file
        audio_path = Path(args.audio_file)
        units_dir = audio_path.parent / "tutorial_units"
    else:
        # --play flag: units dir alongside the output path
        units_dir = Path(args.output).parent / "tutorial_units"

    if not units_dir.exists():
        raise PlayerError(
            f"tutorial_units/ not found at {units_dir}.\n"
            "  Run generation first: python tutor.py <input.md> --output <file.mp3>"
        )

    unit_files = sorted(units_dir.glob("*.mp3"))
    if not unit_files:
        raise PlayerError(f"No .mp3 files found in {units_dir}")

    # Load unit metadata if available
    units_json = units_dir.parent / "tutorial.units.json"
    if units_json.exists():
        import json
        with open(units_json) as f:
            raw_units = json.load(f)
        from tutor.models import TeachingUnit
        units = [TeachingUnit(**u) for u in raw_units]
    else:
        # Fallback: stub units from filenames
        units = [
            TeachingUnit(
                unit=i,
                concept=f.stem.replace("_", " ").title(),
                source_sections=[],
                complexity=2,
                word_budget=400,
                key_facts=[],
                common_misconception="",
                good_analogy="",
                question_style="recall",
                memory_hook="",
            )
            for i, f in enumerate(unit_files)
        ]

    player = TutorPlayer(unit_files=[str(f) for f in unit_files], units=units)
    player.run()
```

Also save `tutorial.units.json` at the end of `cmd_generate()`, right after audio is built:

```python
import json
units_json_path = Path(args.output).with_suffix("") .parent / "tutorial.units.json"
with open(units_json_path, "w", encoding="utf-8") as f:
    # TeachingUnit is a dataclass — use dataclasses.asdict
    from dataclasses import asdict
    json.dump([asdict(u) for u in units], f, indent=2, ensure_ascii=False)
print(f"  Units:  {units_json_path}")
```

---

## Acceptance criteria

1. `python tutor/tutor.py play tutorial_units/` — player starts, audio plays, status bar visible

2. Press `space` — audio pauses; status bar shows "⏸ PAUSED"

3. Press `space` again — audio resumes from where it paused

4. Press `n` — jumps to next unit; status bar updates to show new unit name

5. Press `b` — goes back to previous unit or replays from start

6. Press `r` — replays current unit from beginning

7. Press `s` while paused — prints unit summary and memory hook (does not clear terminal)

8. Press `q` — session complete message prints, player exits cleanly

9. Press `?` — prints "Q&A available from Day 5" and stays paused

10. `python tutor/tutor.py sample_docs/java-basics.md --play` — generates audio (or uses cache) then immediately launches player

---

## Gotchas

**`SDL_VIDEODRIVER=dummy`**: pygame initialises a video subsystem even for audio-only use. Without `os.environ["SDL_VIDEODRIVER"] = "dummy"`, on headless or terminal-only environments pygame raises `pygame.error: No available video device`. Set it before `pygame.init()`.

**`MUSIC_END` event timing**: pygame fires `MUSIC_END` after the track finishes. There is a ~50–100ms delay between the track ending and the event arriving in the event queue. This is normal — don't add sleep to compensate.

**Status bar scrolling**: the `render_status()` function uses `\r` to overwrite the current line. This only works if the display fits in one terminal line. If you're printing multi-line status (as above with 5 lines), you need to use ANSI escape codes to move the cursor up before rewriting. The `clear_status()` helper does this with `\033[F\033[2K` (move up one line, clear it), called once per line before rewriting. Call `clear_status()` inside `render_status()` on all but the first render.

Implementation hint for multi-line rewrite:
```python
# In render_status(), track whether this is the first render
# On subsequent renders, move cursor up 5 lines before writing
```
Add a `_first_render: bool = True` field to `player_display.py` module state (module-level variable is acceptable here since it's a display module, not a data module).

**`_unit_duration_s()` is slow**: loading an mp3 with pydub on every redraw (10 Hz) is expensive. Cache the duration per file: compute it once when `_load_unit()` is called and store in `self._current_unit_duration_s`.

**`tutorial.units.json` schema**: `TeachingUnit` has `prerequisite_concepts: list[str]` with a `field(default_factory=list)` — this serialises fine with `dataclasses.asdict()`. On deserialization, `TeachingUnit(**u)` works as long as all fields are present. If loading an older JSON without `prerequisite_concepts`, it will fail. Add a guard: `u.setdefault("prerequisite_concepts", [])` before `TeachingUnit(**u)`.

**Player runs in the same process as generation**: when `--play` is used, `cmd_generate()` runs first (which calls `asyncio.run()`), then `cmd_play()` runs. This is fine — `asyncio.run()` creates and destroys its own event loop. pygame has no event loop conflict with asyncio because pygame uses its own internal thread for audio.
