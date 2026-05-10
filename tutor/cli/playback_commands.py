from __future__ import annotations

import argparse
import logging
import threading
import time
from pathlib import Path

from tutor.cli import theme
from tutor.cli.shell_context import ShellContext

log = logging.getLogger(__name__)

AUDIO_DIR = Path("audio")


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


def _resolve_units_dir(token: str) -> Path | None:
    """Resolve a token to a tutorial_units directory.

    Accepts:
      - a session name  (e.g. "week2_3")  → audio/week2_3/tutorial_units/
      - a direct path to tutorial_units/  → used as-is
      - a path to any file inside audio/  → parent/tutorial_units/
    """
    p = Path(token)

    if p.exists():
        return p if p.is_dir() else p.parent / "tutorial_units"

    candidate = AUDIO_DIR / token / "tutorial_units"
    if candidate.exists():
        return candidate

    return None


def cmd_play(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /play [session-name | path] [--no-qa] [--provider groq|openrouter]
    session-name: folder name under audio/ (see /sessions)"""
    unit_token = next((t for t in tokens if not t.startswith("--")), None)
    if unit_token:
        units_dir = _resolve_units_dir(unit_token)
        if units_dir is None:
            print(theme.red(f"  Session '{unit_token}' not found."))
            print(theme.dim("  Use /sessions to list available sessions."))
            return
    elif ctx.last_units_dir and ctx.last_units_dir.exists():
        units_dir = ctx.last_units_dir
    else:
        print(theme.red("  No session known. Run /generate first or pass a session name."))
        print(theme.dim("  Use /sessions to list available sessions."))
        return

    if ctx.player and ctx.player._state == "PAUSED":
        ctx.player._resume()
        print(theme.green("  Resumed."))
        return

    if ctx.player and ctx.player._state == "PLAYING":
        print(theme.yellow("  Already playing. Use /pause, /next, /stop."))
        return

    if ctx.player and ctx.player._state == "STOPPED":
        if ctx.player_thread:
            ctx.player_thread.join(timeout=1.0)
        ctx.player = None
        ctx.player_thread = None

    from tutor.exceptions import TutorError
    from tutor.tutor import _build_player

    play_args = argparse.Namespace(
        audio_file=str(units_dir),
        provider=_get_flag(tokens, "--provider", "groq"),
        no_qa="--no-qa" in tokens,
    )
    try:
        player = _build_player(play_args)
    except TutorError as e:
        print(theme.red(f"  Error: {e}"))
        return

    ctx.player = player
    ctx.last_units_dir = units_dir

    def _run() -> None:
        player.run_in_shell()

    ctx.player_thread = threading.Thread(target=_run, daemon=True, name="PlayerThread")
    ctx.player_thread.start()
    print(theme.green(f"  Playing: {units_dir}"))
    print(theme.dim("  Controls: /pause  /next  /prev  /stop  /ask  /summary"))


def cmd_pause(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /pause — pause playback"""
    if not _require_player(ctx):
        return
    assert ctx.player is not None
    if ctx.player._state != "PLAYING":
        print(theme.yellow("  Not currently playing."))
        return
    ctx.player._pause()
    print(theme.cyan("  Paused."))


def cmd_resume(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /resume — resume playback"""
    if not _require_player(ctx):
        return
    assert ctx.player is not None
    if ctx.player._state != "PAUSED":
        print(theme.yellow("  Not paused."))
        return
    ctx.player._resume()
    print(theme.green("  Resumed."))


def cmd_stop(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /stop — stop playback and unload the player"""
    if not _require_player(ctx):
        return
    assert ctx.player is not None
    ctx.player._quit()
    if ctx.player_thread:
        ctx.player_thread.join(timeout=3.0)
    ctx.player = None
    ctx.player_thread = None
    print(theme.cyan("  Stopped."))


def cmd_next(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /next — jump to the next unit"""
    if not _require_player(ctx):
        return
    assert ctx.player is not None
    ctx.player._next_unit()


def cmd_prev(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /prev — jump to the previous unit"""
    if not _require_player(ctx):
        return
    assert ctx.player is not None
    ctx.player._prev_unit()


def cmd_replay(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /replay — replay the current unit from the beginning"""
    if not _require_player(ctx):
        return
    assert ctx.player is not None
    ctx.player._replay_unit()


def cmd_ask(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /ask [question text]
    If question is provided inline, skips the prompt. Pauses audio while answering."""
    if not _require_player(ctx, require_unit=True):
        return
    assert ctx.player is not None

    was_playing = ctx.player._state == "PLAYING"
    if was_playing:
        ctx.player._pause()
        time.sleep(0.05)

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

    ctx.player._ask_question_from_shell(question)


def cmd_summary(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /summary — print the current unit summary and memory hook"""
    if not _require_player(ctx, require_unit=True):
        return
    assert ctx.player is not None
    ctx.player._print_summary()


def cmd_status(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /status — show player state, current unit, elapsed time, Q&A count"""
    if not ctx.player:
        print(theme.dim("  No active session."))
        return
    p = ctx.player
    state_icons = {
        "PLAYING": theme.green("▶ Playing"),
        "PAUSED": theme.yellow("⏸ Paused"),
        "STOPPED": theme.dim("■ Stopped"),
        "ASKING": theme.cyan("? Asking"),
        "ANSWERING": theme.cyan("⟳ Answering"),
    }
    state_str = state_icons.get(p._state, p._state)
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
