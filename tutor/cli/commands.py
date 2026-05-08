import argparse
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from tutor.cli import theme

log = logging.getLogger(__name__)

AUDIO_DIR = Path("audio")


@dataclass
class ShellContext:
    player: object = None                          # TutorPlayer | None
    player_thread: threading.Thread | None = None
    last_units_dir: Path | None = None
    current_session: str | None = None
    last_video: Path | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _parse_generate_args(tokens: list[str]):
    from tutor.tutor import _make_generate_parser
    parser = _make_generate_parser()
    try:
        return parser.parse_args(tokens)
    except SystemExit:
        return None


def _apply_log_level(args) -> None:
    import logging as _logging
    if getattr(args, "debug", False):
        _logging.getLogger().setLevel(_logging.DEBUG)
    elif getattr(args, "verbose", False):
        _logging.getLogger().setLevel(_logging.INFO)


def _session_name(input_path: str) -> str:
    """Derive a safe folder name from the input file path, e.g. week2/3.md → week2_3."""
    return Path(input_path).with_suffix("").as_posix().replace("/", "_").replace("\\", "_").lstrip("_")


def _resolve_units_dir(token: str) -> Path | None:
    """Resolve a token to a tutorial_units directory.

    Accepts:
      - a session name  (e.g. "week2_3")  → audio/week2_3/tutorial_units/
      - a direct path to tutorial_units/  → used as-is
      - a path to any file inside audio/  → parent/tutorial_units/
    """
    p = Path(token)

    # Direct path that exists
    if p.exists():
        return p if p.is_dir() else p.parent / "tutorial_units"

    # Session name: look in audio/<name>/tutorial_units/
    candidate = AUDIO_DIR / token / "tutorial_units"
    if candidate.exists():
        return candidate

    return None


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def cmd_generate(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /generate <file.md> [--duration N] [--difficulty LEVEL]
              [--format FORMAT] [--topic TEXT] [--units N] [--no-cache]
              [--script-only] [--dry-run] [--provider groq|openrouter]
              [--verbose] [--debug]
    Output is saved to audio/<session>/ automatically."""
    if not tokens:
        print(theme.red("  Error: /generate requires a file path."))
        print(theme.dim("  Example: /generate notes.md --difficulty intermediate"))
        return

    args = _parse_generate_args(tokens)
    if args is None:
        print(theme.red("  Error: could not parse arguments."))
        return

    _apply_log_level(args)

    # Auto-route output into audio/<session>/ unless user specified --output
    if not any(t.startswith("--output") for t in tokens) and args.input:
        session = _session_name(args.input)
        args.output = str(AUDIO_DIR / session / "tutorial.mp3")

    # Ensure the output parent directory exists
    if args.input and not getattr(args, "dry_run", False) \
            and not getattr(args, "inspect", False) \
            and not getattr(args, "script_only", False):
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    from tutor import tutor as _tutor
    from tutor.exceptions import TutorError
    try:
        _tutor.cmd_generate(args)
        output = Path(getattr(args, "output", "tutorial.mp3"))
        ctx.last_units_dir = output.parent / "tutorial_units"
        if not getattr(args, "dry_run", False) \
                and not getattr(args, "inspect", False) \
                and not getattr(args, "script_only", False):
            session = _session_name(args.input) if args.input else ""
            ctx.current_session = session
            print(theme.green(f"\n  Generation complete. Session: {theme.bold(session)}"))
            print(theme.dim(f"  Saved to: {output.parent}/"))
            print(theme.green("  Type /play to start listening.\n"))
    except TutorError as e:
        print(theme.red(f"\n  Error: {e}\n"))
    except Exception as e:
        log.exception("Unexpected error in /generate")
        print(theme.red(f"\n  Unexpected error: {e}\n"))


def cmd_sessions(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /sessions — list all generated audio sessions in the audio/ folder"""
    from tutor.cli.video_commands import VIDEO_DIR

    if not AUDIO_DIR.exists():
        print(theme.dim("  No sessions yet. Use /generate to create one."))
        return

    sessions = sorted(
        d for d in AUDIO_DIR.iterdir()
        if d.is_dir() and (d / "tutorial_units").exists()
    )
    if not sessions:
        print(theme.dim("  No sessions yet. Use /generate to create one."))
        return

    print()
    for s in sessions:
        units = list((s / "tutorial_units").glob("*.mp3"))
        mp3 = s / "tutorial.mp3"
        size = f"{mp3.stat().st_size // 1024} KB" if mp3.exists() else "—"
        has_mp4 = (VIDEO_DIR / s.name / "full_session.mp4").exists()
        badge   = theme.green("  [mp4]") if has_mp4 else ""
        print(f"  {theme.cyan(s.name):<30} {len(units)} units   {size}{badge}")
    print(theme.dim(f"\n  Play with: /play <session-name>"))
    print(theme.dim("  Generate video: /video <session-name>"))
    print()


def cmd_play(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /play [session-name | path] [--no-qa] [--provider groq|openrouter]
    session-name: folder name under audio/ (see /sessions)"""
    # Resolve units_dir
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

    # Resume if already paused
    if ctx.player and ctx.player._state == "PAUSED":
        ctx.player._resume()
        print(theme.green("  Resumed."))
        return

    if ctx.player and ctx.player._state == "PLAYING":
        print(theme.yellow("  Already playing. Use /pause, /next, /stop."))
        return

    # Clear any finished player
    if ctx.player and ctx.player._state == "STOPPED":
        if ctx.player_thread:
            ctx.player_thread.join(timeout=1.0)
        ctx.player = None
        ctx.player_thread = None

    from tutor.tutor import _build_player
    from tutor.exceptions import TutorError

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
    if ctx.player._state != "PLAYING":
        print(theme.yellow("  Not currently playing."))
        return
    ctx.player._pause()
    print(theme.cyan("  Paused."))


def cmd_resume(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /resume — resume playback"""
    if not _require_player(ctx):
        return
    if ctx.player._state != "PAUSED":
        print(theme.yellow("  Not paused."))
        return
    ctx.player._resume()
    print(theme.green("  Resumed."))


def cmd_stop(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /stop — stop playback and unload the player"""
    if not _require_player(ctx):
        return
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
    ctx.player._next_unit()


def cmd_prev(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /prev — jump to the previous unit"""
    if not _require_player(ctx):
        return
    ctx.player._prev_unit()


def cmd_replay(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /replay — replay the current unit from the beginning"""
    if not _require_player(ctx):
        return
    ctx.player._replay_unit()


def cmd_ask(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /ask [question text]
    If question is provided inline, skips the prompt. Pauses audio while answering."""
    if not _require_player(ctx, require_unit=True):
        return

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
    ctx.player._print_summary()


def cmd_status(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /status — show player state, current unit, elapsed time, Q&A count"""
    if not ctx.player:
        print(theme.dim("  No active session."))
        return
    p = ctx.player
    state_icons = {
        "PLAYING":   theme.green("▶ Playing"),
        "PAUSED":    theme.yellow("⏸ Paused"),
        "STOPPED":   theme.dim("■ Stopped"),
        "ASKING":    theme.cyan("? Asking"),
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


def cmd_inspect(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /inspect <file.md> [--show-summaries]"""
    if not tokens:
        print(theme.red("  Error: /inspect requires a file path."))
        return
    args = argparse.Namespace(
        input=tokens[0],
        provider="groq",
        no_cache=False,
        inspect=True,
        show_summaries="--show-summaries" in tokens,
        output="tutorial.mp3",
        dry_run=False,
        script_only=False,
        play=False,
        subject="java",
        difficulty="beginner",
        duration=20,
        topic=None,
        units=None,
        fmt="tutor-student",
    )
    from tutor import tutor as _tutor
    from tutor.exceptions import TutorError
    try:
        _tutor.cmd_generate(args)
    except TutorError as e:
        print(theme.red(f"  Error: {e}"))


def cmd_dryrun(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /dry-run <file.md> [--difficulty LEVEL] [--duration N] [--topic TEXT]"""
    if not tokens:
        print(theme.red("  Error: /dry-run requires a file path."))
        return
    args = _parse_generate_args([tokens[0], "--dry-run"] + tokens[1:])
    if args is None:
        return
    from tutor import tutor as _tutor
    from tutor.exceptions import TutorError
    try:
        _tutor.cmd_generate(args)
    except TutorError as e:
        print(theme.red(f"  Error: {e}"))


def cmd_clear(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /clear — clear the terminal"""
    import os
    os.system("cls" if os.name == "nt" else "clear")


def cmd_help(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /help [command] — list all commands, or show detail for one command"""
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

    lines = f"""
{theme.bold("Available commands")}

  {theme.cyan("/generate")} <file.md> [flags]   Generate audio → saved to audio/<session>/
  {theme.cyan("/sessions")}                      List all generated sessions
  {theme.cyan("/play")} [session | path]         Play a session (or resume if paused)
  {theme.cyan("/pause")}                         Pause playback
  {theme.cyan("/resume")}                        Resume playback
  {theme.cyan("/stop")}                          Stop and unload the player
  {theme.cyan("/next")}                          Jump to next unit
  {theme.cyan("/prev")}                          Jump to previous unit
  {theme.cyan("/replay")}                        Replay current unit from the start
  {theme.cyan("/ask")} [question]                Ask a question about the current unit
  {theme.cyan("/summary")}                       Print unit summary and memory hook
  {theme.cyan("/status")}                        Show player state, unit, time, Q&A count
  {theme.cyan("/inspect")} <file.md>             Show ingestion report (no LLM calls)
  {theme.cyan("/dry-run")} <file.md> [flags]     Preview curriculum without generating audio
  {theme.cyan("/video")} [session]               Generate MP4 video (needs /generate first)
  {theme.cyan("/vsessions")}                     List sessions that have a completed video
  {theme.cyan("/clear")}                         Clear the terminal
  {theme.cyan("/help")} [command]                Show this help or detail for one command
  {theme.cyan("/quit")}                          Exit LearnX

{theme.bold("/generate flags:")}
  --duration N          Target session length in minutes  (default: 20)
  --difficulty LEVEL    beginner | intermediate | advanced (default: beginner)
  --format FORMAT       tutor-student | dual-tutor        (default: tutor-student)
  --topic TEXT          Force a specific concept into the curriculum
  --units N             Cap the number of teaching units
  --provider NAME       groq | openrouter                 (default: groq)
  --no-cache            Clear cached summaries and regenerate
  --script-only         Print script; skip audio generation
  --dry-run             Preview curriculum; skip dialogue and audio
  --verbose             Show per-step progress logs
  --debug               Write DEBUG logs to tutor.log

{theme.bold("Examples:")}
  /generate notes.md
  /generate week2/3.md --difficulty intermediate --topic "HashMap internals"
  /sessions
  /play week2_3
  /ask what is the difference between == and .equals()?
  /dry-run notes.md --difficulty advanced
"""
    print(lines)


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

COMMAND_MAP: dict[str, object] = {
    "/generate": cmd_generate,
    "/gen":      cmd_generate,
    "/sessions": cmd_sessions,
    "/play":     cmd_play,
    "/pause":    cmd_pause,
    "/resume":   cmd_resume,
    "/stop":     cmd_stop,
    "/next":     cmd_next,
    "/prev":     cmd_prev,
    "/back":     cmd_prev,
    "/replay":   cmd_replay,
    "/ask":      cmd_ask,
    "/summary":  cmd_summary,
    "/status":   cmd_status,
    "/inspect":  cmd_inspect,
    "/dry-run":  cmd_dryrun,
    "/dryrun":   cmd_dryrun,
    "/clear":    cmd_clear,
    "/help":     cmd_help,
    "/?":        cmd_help,
    "/quit":     None,
    "/exit":     None,
    "/q":        None,
}
