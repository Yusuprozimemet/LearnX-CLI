# Day 7 — Interactive Shell & Branded CLI

## What works at the end of this day

```bash
# New entry point — shows logo + drops into REPL
python -m tutor

# All slash-commands work in the shell
LearnX > /generate sample_docs/java-basics.md --difficulty intermediate
LearnX > /play tutorial_units/
LearnX [▶ 2/5  Pass-by-Value] > /pause
LearnX [⏸ 2/5  Pass-by-Value] > /ask what is the difference between stack and heap?
LearnX [⏸ 2/5  Pass-by-Value] > /resume
LearnX [▶ 2/5  Pass-by-Value] > /next
LearnX [▶ 3/5  String Equality] > /summary
LearnX [▶ 3/5  String Equality] > /stop
LearnX > /help
LearnX > /quit
```

Old argparse commands (`python -m tutor.tutor <file.md> --dry-run`) continue to work unchanged — this day adds a shell on top, not a replacement.

---

## Day 7 is a UX sprint

No new AI features. The goals are:
1. A branded welcome screen with ASCII logo
2. A `/command`-style REPL that wraps the existing generation and player machinery
3. The player runs in a background thread so the shell stays interactive during playback
4. A dynamic prompt that reflects player state (playing, paused, stopped)
5. Coloured output throughout — errors in red, success in green, info in cyan

---

## Files to create today

---

### 1. `tutor/cli/__init__.py` (empty)

---

### 2. `tutor/cli/theme.py` (~40 lines)

All ANSI colour codes live here. No colour values anywhere else in `cli/`.

```python
import os
import sys

# Enable ANSI on Windows (requires Windows 10+)
if sys.platform == "win32":
    os.system("")

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"

# Foreground colours
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
MAGENTA = "\033[95m"
CYAN   = "\033[96m"
WHITE  = "\033[97m"
GREY   = "\033[90m"

def red(s: str)     -> str: return f"{RED}{s}{RESET}"
def green(s: str)   -> str: return f"{GREEN}{s}{RESET}"
def yellow(s: str)  -> str: return f"{YELLOW}{s}{RESET}"
def cyan(s: str)    -> str: return f"{CYAN}{s}{RESET}"
def grey(s: str)    -> str: return f"{GREY}{s}{RESET}"
def bold(s: str)    -> str: return f"{BOLD}{s}{RESET}"
def dim(s: str)     -> str: return f"{DIM}{s}{RESET}"
def magenta(s: str) -> str: return f"{MAGENTA}{s}{RESET}"
```

---

### 3. `tutor/cli/logo.py` (~50 lines)

The welcome banner. Printed once at startup, never again.

```python
from tutor.cli import theme

LOGO = r"""
██╗     ███████╗ █████╗ ██████╗ ███╗   ██╗██╗  ██╗
██║     ██╔════╝██╔══██╗██╔══██╗████╗  ██║╚██╗██╔╝
██║     █████╗  ███████║██████╔╝██╔██╗ ██║ ╚███╔╝ 
██║     ██╔══╝  ██╔══██║██╔══██╗██║╚██╗██║ ██╔██╗ 
███████╗███████╗██║  ██║██║  ██║██║ ╚████║██╔╝ ██╗
╚══════╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝
"""

TAGLINE = "  Audio tutorials from any Markdown document"
VERSION = "v1.0"
DIVIDER = "─" * 54


def print_welcome() -> None:
    print(theme.CYAN + LOGO + theme.RESET, end="")
    print(f"  {theme.bold(TAGLINE.strip())}   {theme.dim(VERSION)}")
    print(theme.dim(f"  {DIVIDER}"))
    print(theme.dim("  Type /help to see available commands.\n"))
```

Logo rendering notes:
- The block characters (`█`, `╗`, `═`, etc.) are Unicode — they render correctly on any modern terminal with a Unicode font.
- On Windows cmd.exe, set the console font to Cascadia Code or Consolas before running; Windows Terminal works out of the box.
- `theme.CYAN` wraps the full logo block so it renders in cyan; `theme.RESET` after.

---

### 4. `tutor/cli/commands.py` (~200 lines)

One function per command. Each receives the parsed tokens and a `ShellContext` and returns nothing (prints its own output). No argparse inside — just token splitting.

```python
import logging
import shlex
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from tutor.cli import theme

if TYPE_CHECKING:
    from tutor.cli.shell import ShellContext

log = logging.getLogger(__name__)
```

#### `ShellContext` dataclass

Defined here, used by shell.py:

```python
from dataclasses import dataclass, field
from tutor.player.player import TutorPlayer

@dataclass
class ShellContext:
    player: TutorPlayer | None = None
    player_thread: threading.Thread | None = None
    last_units_dir: Path | None = None
```

#### Command handlers

Each function has signature `def cmd_NAME(tokens: list[str], ctx: ShellContext) -> None`.

**`cmd_generate`**

Parses the remaining tokens as argparse-style flags and calls the existing `cmd_generate()` in `tutor.py`. Runs in the foreground (blocks the shell while generating).

```python
def cmd_generate(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /generate <file.md> [--duration N] [--difficulty LEVEL]
              [--format FORMAT] [--topic TEXT] [--units N] [--no-cache]"""
    if not tokens:
        print(theme.red("  Error: /generate requires a file path."))
        print(theme.dim("  Example: /generate notes.md --difficulty intermediate"))
        return

    import sys
    from tutor import tutor as _tutor

    # Build a fake sys.argv and call the existing main logic
    file_path = tokens[0]
    extra_flags = tokens[1:]
    old_argv = sys.argv
    sys.argv = ["tutor", file_path] + extra_flags
    try:
        args = _parse_generate_args(sys.argv[1:])
        _tutor.cmd_generate(args)
        ctx.last_units_dir = Path(getattr(args, "output", "tutorial.mp3")).parent / "tutorial_units"
        print(theme.green("\n  Generation complete. Type /play to start listening.\n"))
    except SystemExit:
        pass
    except Exception as e:
        print(theme.red(f"\n  Error: {e}\n"))
    finally:
        sys.argv = old_argv
```

`_parse_generate_args` is a private helper that builds an `argparse.Namespace` from a token list using the same parser definition as `tutor.py` — extract the parser into a shared function (see "Modifications to existing files" below).

**`cmd_play`**

Starts or resumes the player in a background thread.

```python
def cmd_play(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /play [path-to-tutorial_units/]  [--no-qa] [--provider groq|openrouter]"""
    # Resolve units_dir
    if tokens:
        units_dir = Path(tokens[0])
    elif ctx.last_units_dir and ctx.last_units_dir.exists():
        units_dir = ctx.last_units_dir
    else:
        print(theme.red("  Error: no units directory known. Run /generate first, or pass a path."))
        return

    # If player already running, resume instead of restarting
    if ctx.player and ctx.player._state == "PAUSED":
        ctx.player._resume()
        print(theme.green("  Resumed."))
        return

    if ctx.player and ctx.player._state == "PLAYING":
        print(theme.yellow("  Already playing. Use /pause, /next, /stop."))
        return

    # Build player using existing cmd_play logic
    import argparse
    from tutor import tutor as _tutor

    args = argparse.Namespace(
        audio_file=str(units_dir),
        provider=_get_flag(tokens, "--provider", "groq"),
        no_qa="--no-qa" in tokens,
    )
    try:
        player = _tutor._build_player(args)   # new helper — see modifications
    except Exception as e:
        print(theme.red(f"  Error: {e}"))
        return

    ctx.player = player
    ctx.last_units_dir = units_dir

    def _run():
        player.run_in_shell()   # new method — see modifications

    ctx.player_thread = threading.Thread(target=_run, daemon=True)
    ctx.player_thread.start()
    print(theme.green(f"  Playing from {units_dir}"))
    print(theme.dim("  Controls: /pause  /next  /prev  /stop  /ask  /summary"))
```

**`cmd_pause`**

```python
def cmd_pause(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /pause"""
    if not _require_player(ctx): return
    if ctx.player._state != "PLAYING":
        print(theme.yellow("  Not currently playing."))
        return
    ctx.player._pause()
    print(theme.cyan("  Paused."))
```

**`cmd_resume`**

```python
def cmd_resume(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /resume"""
    if not _require_player(ctx): return
    if ctx.player._state != "PAUSED":
        print(theme.yellow("  Not paused."))
        return
    ctx.player._resume()
    print(theme.green("  Resumed."))
```

**`cmd_stop`**

```python
def cmd_stop(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /stop"""
    if not _require_player(ctx): return
    ctx.player._quit()
    if ctx.player_thread:
        ctx.player_thread.join(timeout=2.0)
    ctx.player = None
    ctx.player_thread = None
    print(theme.cyan("  Stopped."))
```

**`cmd_next`**, **`cmd_prev`**, **`cmd_replay`**

```python
def cmd_next(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /next"""
    if not _require_player(ctx): return
    ctx.player._next_unit()

def cmd_prev(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /prev"""
    if not _require_player(ctx): return
    ctx.player._prev_unit()

def cmd_replay(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /replay"""
    if not _require_player(ctx): return
    ctx.player._replay_unit()
```

**`cmd_ask`**

```python
def cmd_ask(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /ask [question text]
    If question is provided inline, skips the prompt."""
    if not _require_player(ctx, require_unit=True): return

    was_playing = ctx.player._state == "PLAYING"
    if was_playing:
        ctx.player._pause()

    question = " ".join(tokens).strip() if tokens else None
    if not question:
        try:
            question = input(theme.cyan("  Your question: ")).strip()
        except (KeyboardInterrupt, EOFError):
            print()
            if was_playing:
                ctx.player._resume()
            return

    if not question:
        if was_playing:
            ctx.player._resume()
        return

    ctx.player._ask_question_from_shell(question)   # new method — see modifications
```

**`cmd_summary`**

```python
def cmd_summary(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /summary"""
    if not _require_player(ctx, require_unit=True): return
    ctx.player._print_summary()
```

**`cmd_status`**

```python
def cmd_status(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /status"""
    if not ctx.player:
        print(theme.dim("  No active session."))
        return
    p = ctx.player
    state_str = {
        "PLAYING": theme.green("▶ Playing"),
        "PAUSED": theme.yellow("⏸ Paused"),
        "STOPPED": theme.dim("■ Stopped"),
        "ASKING": theme.cyan("? Asking"),
        "ANSWERING": theme.cyan("⟳ Answering"),
    }.get(p._state, p._state)

    unit = p.units[p._current_idx] if p._current_idx < len(p.units) else None
    unit_str = f"Unit {p._current_idx + 1}/{len(p.units)} — {unit.concept}" if unit else "—"
    elapsed = p._elapsed_seconds()
    total = p._unit_duration_s()
    m_el, s_el = divmod(elapsed, 60)
    m_to, s_to = divmod(total, 60)

    print(f"\n  State:    {state_str}")
    print(f"  Unit:     {unit_str}")
    print(f"  Time:     {m_el:02d}:{s_el:02d} / {m_to:02d}:{s_to:02d}")
    print(f"  Q&A:      {p.qa_count} question(s) this session\n")
```

**`cmd_inspect`**

```python
def cmd_inspect(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /inspect <file.md> [--show-summaries]"""
    if not tokens:
        print(theme.red("  Error: /inspect requires a file path."))
        return
    import sys, argparse
    from tutor import tutor as _tutor
    args = argparse.Namespace(
        input=tokens[0],
        inspect=True,
        show_summaries="--show-summaries" in tokens,
        no_cache=False,
        provider="groq",
        output="tutorial.mp3",
    )
    try:
        _tutor.cmd_generate(args)
    except Exception as e:
        print(theme.red(f"  Error: {e}"))
```

**`cmd_dryrun`**

```python
def cmd_dryrun(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /dry-run <file.md> [--difficulty LEVEL] [--duration N] [--topic TEXT]"""
    if not tokens:
        print(theme.red("  Error: /dry-run requires a file path."))
        return
    import sys, argparse
    from tutor import tutor as _tutor
    args = _parse_generate_args([tokens[0]] + ["--dry-run"] + tokens[1:])
    try:
        _tutor.cmd_generate(args)
    except Exception as e:
        print(theme.red(f"  Error: {e}"))
```

**`cmd_clear`**

```python
def cmd_clear(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /clear"""
    import os
    os.system("cls" if os.name == "nt" else "clear")
```

**`cmd_help`**

```python
HELP_TEXT = """
{bold}Available commands{reset}

  {cyan}/generate{reset} <file.md> [flags]   Generate audio from a Markdown file
  {cyan}/play{reset} [path]                  Start or resume the player
  {cyan}/pause{reset}                        Pause playback
  {cyan}/resume{reset}                       Resume playback
  {cyan}/stop{reset}                         Stop and unload the player
  {cyan}/next{reset}                         Jump to next unit
  {cyan}/prev{reset}                         Jump to previous unit
  {cyan}/replay{reset}                       Replay current unit from the start
  {cyan}/ask{reset} [question]               Ask a question about the current unit
  {cyan}/summary{reset}                      Print current unit summary and memory hook
  {cyan}/status{reset}                       Show player state, unit, and elapsed time
  {cyan}/inspect{reset} <file.md>            Show ingestion report (no LLM calls)
  {cyan}/dry-run{reset} <file.md> [flags]    Preview curriculum without generating audio
  {cyan}/clear{reset}                        Clear the terminal
  {cyan}/help{reset} [command]               Show this help or detail on one command
  {cyan}/quit{reset}                         Exit LearnX

{bold}/generate flags:{reset}
  --duration N          Target session length in minutes (default: 20)
  --difficulty LEVEL    beginner | intermediate | advanced (default: beginner)
  --format FORMAT       tutor-student | dual-tutor (default: tutor-student)
  --topic TEXT          Force a specific concept into the curriculum
  --units N             Cap the number of teaching units
  --provider NAME       groq | openrouter (default: groq)
  --no-cache            Clear cached summaries and regenerate

{bold}Examples:{reset}
  /generate notes.md
  /generate notes.md --difficulty intermediate --topic "HashMap internals"
  /generate notes.md --format dual-tutor --duration 30
  /play
  /play tutorial_units/
  /ask what is the difference between == and .equals()?
"""


def cmd_help(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /help [command]"""
    # Per-command detail: look up docstring from the handler
    if tokens:
        name = tokens[0].lstrip("/")
        handler = COMMAND_MAP.get(f"/{name}") or COMMAND_MAP.get(name)
        if handler and handler.__doc__:
            print(f"\n  {theme.cyan(f'/{name}')}")
            for line in handler.__doc__.strip().splitlines():
                print(f"    {line}")
            print()
            return
        print(theme.yellow(f"  Unknown command: /{name}"))
        return
    print(HELP_TEXT.format(
        bold=theme.BOLD, reset=theme.RESET, cyan=theme.CYAN
    ))
```

#### Private helpers

```python
def _require_player(ctx: ShellContext, require_unit: bool = False) -> bool:
    if not ctx.player:
        print(theme.red("  No active player. Use /play first."))
        return False
    if ctx.player._state == "STOPPED":
        print(theme.red("  Player has stopped. Use /play to start a new session."))
        return False
    if require_unit and ctx.player._current_idx >= len(ctx.player.units):
        print(theme.red("  No unit loaded."))
        return False
    return True


def _get_flag(tokens: list[str], flag: str, default: str) -> str:
    try:
        idx = tokens.index(flag)
        return tokens[idx + 1]
    except (ValueError, IndexError):
        return default
```

#### Command dispatch table

```python
COMMAND_MAP: dict[str, callable] = {
    "/generate":  cmd_generate,
    "/gen":       cmd_generate,
    "/play":      cmd_play,
    "/pause":     cmd_pause,
    "/resume":    cmd_resume,
    "/stop":      cmd_stop,
    "/next":      cmd_next,
    "/prev":      cmd_prev,
    "/back":      cmd_prev,
    "/replay":    cmd_replay,
    "/ask":       cmd_ask,
    "/summary":   cmd_summary,
    "/status":    cmd_status,
    "/inspect":   cmd_inspect,
    "/dry-run":   cmd_dryrun,
    "/dryrun":    cmd_dryrun,
    "/clear":     cmd_clear,
    "/help":      cmd_help,
    "/?":         cmd_help,
    "/quit":      None,   # handled in shell loop
    "/exit":      None,
    "/q":         None,
}
```

---

### 5. `tutor/cli/shell.py` (~100 lines)

The REPL main loop.

```python
import sys
from tutor.cli import theme
from tutor.cli.logo import print_welcome
from tutor.cli.commands import COMMAND_MAP, ShellContext

EXIT_COMMANDS = {"/quit", "/exit", "/q"}


def _build_prompt(ctx: ShellContext) -> str:
    p = ctx.player
    if p is None or p._state == "STOPPED":
        return f"{theme.CYAN}LearnX{theme.RESET} > "

    state_icon = "▶" if p._state == "PLAYING" else "⏸"
    unit = p.units[p._current_idx] if p._current_idx < len(p.units) else None
    concept = unit.concept[:24] if unit else "—"
    idx_str = f"{p._current_idx + 1}/{len(p.units)}"
    state_str = theme.green(state_icon) if p._state == "PLAYING" else theme.yellow(state_icon)
    return (
        f"{theme.CYAN}LearnX{theme.RESET} "
        f"[{state_str} {theme.dim(idx_str)}  {concept}] > "
    )


def run_shell() -> None:
    print_welcome()
    ctx = ShellContext()

    while True:
        try:
            prompt = _build_prompt(ctx)
            line = input(prompt).strip()
        except (KeyboardInterrupt, EOFError):
            print()
            _graceful_exit(ctx)
            break

        if not line:
            continue

        # Split into command + tokens
        parts = line.split(None, 1)
        cmd = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""
        try:
            import shlex
            tokens = shlex.split(rest)
        except ValueError:
            tokens = rest.split()

        if cmd in EXIT_COMMANDS:
            _graceful_exit(ctx)
            break

        handler = COMMAND_MAP.get(cmd)
        if handler is None:
            if cmd.startswith("/"):
                print(theme.red(f"  Unknown command: {cmd}"))
                print(theme.dim("  Type /help to see available commands."))
            else:
                # Bare text — treat as /ask if player is active
                if ctx.player and ctx.player._state in ("PLAYING", "PAUSED"):
                    from tutor.cli.commands import cmd_ask
                    cmd_ask([line], ctx)
                else:
                    print(theme.dim(f"  (Commands start with /  — try /help)"))
            continue

        try:
            handler(tokens, ctx)
        except KeyboardInterrupt:
            print()
        except Exception as e:
            print(theme.red(f"  Error: {e}"))
            import logging
            logging.getLogger(__name__).exception("Unhandled error in command %s", cmd)


def _graceful_exit(ctx: ShellContext) -> None:
    if ctx.player and ctx.player._state != "STOPPED":
        ctx.player._quit()
    if ctx.player_thread:
        ctx.player_thread.join(timeout=2.0)
    print(theme.dim("\n  Goodbye.\n"))
```

---

### 6. `tutor/__main__.py` (~20 lines)

Makes `python -m tutor` invoke the shell.

```python
import io
import sys


def main() -> None:
    # UTF-8 stdout — same fix as tutor.py, moved here for the new entry point
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    from tutor.cli.shell import run_shell
    run_shell()


if __name__ == "__main__":
    main()
```

---

## Modifications to existing files

---

### `tutor/player/player.py` — add `run_in_shell()` and `_ask_question_from_shell()`

The existing `run()` method handles its own keyboard input via `input_handler.get_key()`. In shell mode, keystrokes come from the REPL instead. Add a second run method that skips `_handle_keys()`:

```python
def run_in_shell(self) -> None:
    """Like run(), but skips keyboard polling — commands arrive via shell."""
    import os, pygame, time
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
            # No _handle_keys() — shell thread sends commands directly
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        pass
    finally:
        pygame.mixer.quit()
        pygame.quit()
```

Note: `run_in_shell()` does NOT call `_redraw()` — the status bar lives in the shell prompt instead.

Add `_ask_question_from_shell()` — called by `cmd_ask` with the question already in hand:

```python
def _ask_question_from_shell(self, question: str) -> None:
    """Answer question text from shell without prompting for input."""
    if self.no_qa or self.llm_fn is None:
        player_display.print_qa_disabled()
        return
    if self._current_idx >= len(self.units):
        player_display.print_no_context()
        return

    player_display.print_thinking()
    from tutor.qa import qa
    answer_text = qa.answer(
        question=question,
        current_unit=self.units[self._current_idx],
        all_chunks=self.chunks,
        session=self.session,
        llm_fn=self.llm_fn,
        position_seconds=self._elapsed_seconds(),
    )
    self.qa_count += 1
    player_display.print_answer(answer_text, self.units[self._current_idx].concept)
    player_display.print_resume_hint()
```

---

### `tutor/tutor.py` — extract `_build_player()` and `_make_generate_parser()`

`commands.py` needs to build a player and parse generate args without duplicating the logic in `tutor.py`. Extract two helpers:

**`_make_generate_parser()`** — returns the argparse parser (currently inline in `main()`):

```python
def _make_generate_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tutor")
    parser.add_argument("input", nargs="?")
    parser.add_argument("--output", default="tutorial.mp3")
    parser.add_argument("--provider", default="groq")
    parser.add_argument("--duration", type=int, default=DEFAULT_DURATION_MIN)
    parser.add_argument("--format", default=DEFAULT_FORMAT, dest="fmt")
    parser.add_argument("--difficulty", default=DEFAULT_DIFFICULTY)
    parser.add_argument("--units", type=int, default=None)
    parser.add_argument("--subject", default=DEFAULT_SUBJECT)
    parser.add_argument("--topic", default=None)
    parser.add_argument("--play", action="store_true")
    parser.add_argument("--script-only", action="store_true", dest="script_only")
    parser.add_argument("--dry-run", action="store_true", dest="dry_run")
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument("--show-summaries", action="store_true", dest="show_summaries")
    parser.add_argument("--no-cache", action="store_true", dest="no_cache")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--debug", action="store_true")
    return parser
```

`main()` then becomes: `args = _make_generate_parser().parse_args()`

**`_build_player(args)`** — refactor the player-construction logic out of `cmd_play()`:

```python
def _build_player(args) -> TutorPlayer:
    """Build a TutorPlayer from play-command args. Raises PlayerError on failure."""
    # (move the existing unit/chunk/session/llm setup from cmd_play here)
    # Returns a ready TutorPlayer, does not call .run()
    ...
```

`cmd_play()` then becomes: `player = _build_player(args); player.run()`

---

## Acceptance criteria

1. `python -m tutor` — logo prints in cyan, REPL starts, prompt shows `LearnX > `

2. `/help` — all commands listed with descriptions; `/help generate` shows `/generate` flags

3. `/generate sample_docs/java-basics.md --dry-run` — curriculum plan prints, no error

4. `/generate sample_docs/java-basics.md` — full generation runs, ends with "Generation complete. Type /play."

5. `/play` (after generation) — player starts in background thread, prompt changes to `LearnX [▶ 1/5 ...] >`

6. `/pause` — prompt changes to `LearnX [⏸ 1/5 ...] >`

7. `/resume` — prompt changes back to `LearnX [▶ 1/5 ...] >`

8. `/next`, `/prev`, `/replay` — unit index in prompt updates accordingly

9. `/ask what is pass-by-value` — inline question, answer prints with citation, no extra prompt

10. `/ask` (no args) — question prompt appears; Ctrl+C cancels cleanly

11. `/summary` — prints unit summary and memory hook

12. `/status` — prints state, unit name, elapsed/total time, Q&A count

13. `/stop` — player thread joins cleanly, prompt returns to `LearnX > `

14. `/inspect sample_docs/java-basics.md` — ingestion report prints

15. Bare text while playing (e.g., typing `what is a stack?`) — treated as `/ask`

16. `/quit` or Ctrl+D — player stops if running, "Goodbye." prints, exits cleanly

17. `python -m tutor.tutor sample_docs/java-basics.md --dry-run` — old argparse path still works, no logo

18. All 40 existing tests still pass (`py -m pytest`)

---

## Gotchas

**Player thread vs pygame event loop**: pygame's `event.get()` is not thread-safe on all platforms. In `run_in_shell()`, the player thread owns all pygame calls. The shell thread must never call pygame functions directly — it only mutates player state (Python attribute assignments), which are atomic for simple types. This is safe because CPython's GIL prevents torn reads/writes on scalar attributes like `_state`.

**`input()` and the player thread**: `input()` blocks the main thread. While waiting for the user to type, the player thread continues running `_handle_events()` and advancing through units. This is the correct behaviour — the player background-advances, and the shell handles commands when the user presses Enter.

**Prompt redraw after player events**: When a unit finishes and the player auto-advances, the prompt still shows the old unit (e.g., `[▶ 2/5 ...]`). The prompt is only redrawn on the next `input()` call (when the user types something or presses Enter). This is acceptable for an MVP — the prompt catches up on the next keystroke. A fully live prompt would require a more complex curses or prompt_toolkit setup.

**`shlex.split` on Windows paths**: `shlex.split("notes.md")` works fine. `shlex.split(r"C:\Users\me\notes.md")` may fail on backslashes — users should quote paths with spaces: `"C:\Users\me\my notes.md"`. Document this in `/help generate`.

**Bare text as `/ask`**: Only route bare text to `/ask` when the player is PLAYING or PAUSED and Q&A is enabled. If the player is stopped, print the hint message instead of silently failing.

**Thread cleanup on Ctrl+C**: `KeyboardInterrupt` in the main thread does not kill the daemon player thread immediately — it will be killed when the process exits. The `_graceful_exit()` function calls `player._quit()` first (sets `_state = "STOPPED"` which exits the while loop) and then `thread.join(timeout=2.0)`. If join times out, the daemon thread dies with the process anyway.

**Logo on Windows cmd.exe**: Block characters render correctly in Windows Terminal, VS Code terminal, and PowerShell 7. In legacy `cmd.exe`, they may render as boxes. The `os.system("")` call in `theme.py` enables ANSI processing on Windows 10+. If the logo looks broken, switch to Windows Terminal.
