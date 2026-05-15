from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeAlias

from tutor.cli import theme
from tutor.cli.playback_commands import (
    cmd_ask,
    cmd_next,
    cmd_pause,
    cmd_play,
    cmd_prev,
    cmd_replay,
    cmd_resume,
    cmd_status,
    cmd_stop,
    cmd_summary,
)
from tutor.cli.shell_context import ShellContext  # re-exported for callers

log = logging.getLogger(__name__)

AUDIO_DIR = Path("audio")

CommandFn: TypeAlias = Callable[[list[str], ShellContext], None]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_generate_args(tokens: list[str]) -> argparse.Namespace | None:
    from tutor.tutor import _make_generate_parser

    parser = _make_generate_parser()
    try:
        return parser.parse_args(tokens)
    except SystemExit:
        return None


def _apply_log_level(args: argparse.Namespace) -> None:
    if getattr(args, "debug", False):
        logging.getLogger().setLevel(logging.DEBUG)
    elif getattr(args, "verbose", False):
        logging.getLogger().setLevel(logging.INFO)


def _session_name(input_path: str) -> str:
    """Derive a safe folder name from the input file path, e.g. week2/3.md → week2_3."""
    return (
        Path(input_path).with_suffix("").as_posix().replace("/", "_").replace("\\", "_").lstrip("_")
    )


def _read_meta(path: Path) -> dict[str, Any]:
    """Read tutorial.meta.json. Returns empty dict on any error."""
    try:
        result: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return result
    except Exception:
        return {}


def _format_duration(seconds: Any) -> str:
    """Convert seconds to M:SS string. Returns blank string if seconds <= 0."""
    try:
        secs = float(seconds)
    except (TypeError, ValueError):
        return ""
    if secs <= 0:
        return ""
    m, s = divmod(int(secs), 60)
    return f"{m}:{s:02d}"


def _write_session_meta(output: Path, input_path: str) -> None:
    """Write tutorial.meta.json with source file, timestamp, and duration."""
    duration_s = 0.0
    full_mp3 = output.parent / "tutorial.mp3"
    if full_mp3.exists():
        try:
            from pydub import AudioSegment

            duration_s = len(AudioSegment.from_mp3(full_mp3)) / 1000.0
        except Exception:
            pass

    meta = {
        "source_file": input_path,
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "total_duration_s": duration_s,
    }
    (output.parent / "tutorial.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


def cmd_generate(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /generate <file.md> [--duration N] [--difficulty LEVEL]
              [--format FORMAT] [--topic TEXT] [--units N] [--no-cache]
              [--script-only] [--dry-run] [--provider groq|openrouter]
              [--verbose] [--debug]
    Two expert hosts (ALEX and MAYA) walk through the document step by step.
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

    if not any(t.startswith("--output") for t in tokens) and args.input:
        session = _session_name(args.input)
        if getattr(args, "explain", False):
            session = session + "_explain"
        args.output = str(AUDIO_DIR / session / "tutorial.mp3")

    if (
        args.input
        and not getattr(args, "dry_run", False)
        and not getattr(args, "inspect", False)
        and not getattr(args, "script_only", False)
    ):
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    from tutor import tutor as _tutor
    from tutor.exceptions import TutorError

    try:
        _tutor.cmd_generate(args)
        output = Path(getattr(args, "output", "tutorial.mp3"))
        ctx.last_units_dir = output.parent / "tutorial_units"
        if (
            not getattr(args, "dry_run", False)
            and not getattr(args, "inspect", False)
            and not getattr(args, "script_only", False)
        ):
            session = _session_name(args.input) if args.input else ""
            if getattr(args, "explain", False):
                session = session + "_explain"
            ctx.current_session = session
            if args.input:
                _write_session_meta(output, str(args.input))
            print(theme.green(f"\n  Generation complete. Session: {theme.bold(session)}"))
            print(theme.dim(f"  Saved to: {output.parent}/"))
            print(theme.green("  Type /play to start listening.\n"))
    except TutorError as e:
        print(theme.red(f"\n  Error: {e}\n"))
    except Exception as e:
        log.exception("Unexpected error in /generate")
        print(theme.red(f"\n  Unexpected error: {e}\n"))


def cmd_sessions(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /sessions — list all audio sessions"""
    from tutor.cli.video_commands import VIDEO_DIR

    if not AUDIO_DIR.exists():
        print(theme.dim("  No sessions yet. Use /generate to create one."))
        return

    sessions = sorted(
        d for d in AUDIO_DIR.iterdir() if d.is_dir() and (d / "tutorial_units").exists()
    )
    if not sessions:
        print(theme.dim("  No sessions yet. Use /generate to create one."))
        return

    print()
    for s in sessions:
        units = list((s / "tutorial_units").glob("unit_*.mp3"))
        meta = _read_meta(s / "tutorial.meta.json")
        has_mp4 = (VIDEO_DIR / s.name / "full_session.mp4").exists()

        dur_str = _format_duration(meta.get("total_duration_s", 0))
        date_str = (meta.get("generated_at", "") or "")[:10]
        badge = theme.green("  [video]") if has_mp4 else "         "

        print(
            f"  {theme.cyan(s.name):<22}"
            f"  {len(units):>2} units"
            f"  {dur_str:>6}"
            f"{badge}"
            f"  {theme.dim(date_str)}"
        )

    print(theme.dim("\n  Play: /play <name>   Video: /video <name>"))
    print()


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
{theme.bold("─── AUDIO PIPELINE ─────────────────────────────────────────────────────────")}

  {theme.cyan("/generate")} <file.md> [flags]   Parse notes → generate dialogue → synthesise MP3s
  {theme.cyan("/sessions")}                      List all audio sessions in audio/
  {theme.cyan("/inspect")} <file.md>             Show ingestion report without running anything
  {theme.cyan("/dry-run")} <file.md> [flags]     Preview curriculum plan; skip dialogue and audio

  {theme.bold("/generate flags:")}
    --explain             Read-along mode: narrate document top-to-bottom (one unit per section)
    --conversation        Expert dialogue mode: ALEX and MAYA explain the document step by step (default)
    --duration N          Target length in minutes         (default: 20, conversation only)
    --difficulty LEVEL    beginner | intermediate | advanced (default: beginner, conversation only)
    --format FORMAT       tutor-student | dual-tutor        (default: tutor-student, conversation only)
                          tutor-student: ALEX (male) + MAYA (female) | dual-tutor: ALEX + SAM (both male)
    --topic TEXT          Force a specific concept into the curriculum (conversation only)
    --units N             Cap the number of teaching units  (conversation only)
    --provider NAME       groq | openrouter                 (default: groq)
    --no-cache            Ignore cached narrations/dialogues and regenerate
    --script-only         Print script only; skip audio synthesis
    --verbose             Show per-step progress logs
    --debug               Write DEBUG logs to tutor.log

{theme.bold("─── AUDIO PLAYBACK ──────────────────────────────────────────────────────────")}

  {theme.cyan("/play")} [session | path]         Load and play a session (MP3 units)
  {theme.cyan("/pause")}                         Pause playback
  {theme.cyan("/resume")}                        Resume from pause
  {theme.cyan("/stop")}                          Stop and unload the player
  {theme.cyan("/next")}                          Skip to next unit
  {theme.cyan("/prev")}                          Go back to previous unit
  {theme.cyan("/replay")}                        Restart the current unit from the beginning
  {theme.cyan("/status")}                        Show player state, current unit, time, Q&A count
  {theme.cyan("/ask")} [question]                Ask a question about the current unit (LLM-powered)
  {theme.cyan("/summary")}                       Print the current unit's summary and memory hook

{theme.bold("─── VIDEO PIPELINE ──────────────────────────────────────────────────────────")}

  {theme.cyan("/video")} [session]               Render slides + subtitles → assemble MP4
                           Requires a completed /generate session.
                           Output → video/<session>/full_session.mp4
  {theme.cyan("/vsessions")}                     List sessions that have a completed video

{theme.bold("─── SHELL ───────────────────────────────────────────────────────────────────")}

  {theme.cyan("/help")} [command]                Show this help, or detail for one command
  {theme.cyan("/clear")}                         Clear the terminal
  {theme.cyan("/quit")}                          Exit LearnX

{theme.bold("─── EXAMPLES ────────────────────────────────────────────────────────────────")}

  {theme.bold("1. Generate and listen (expert dialogue):")}
    /generate week3/1.md --provider openrouter
    /play week3_1                              (load the session)
    /next                                      (move to next concept)
    /ask why does == fail for Strings?         (ask anything mid-listen)
    /summary                                   (print the memory hook for this unit)
    /replay                                    (restart current unit)
    /stop

  {theme.bold("2. Adjust difficulty or focus:")}
    /generate week3/1.md --difficulty intermediate --provider openrouter
    /generate week3/1.md --topic "HashMap internals" --provider openrouter
    /generate week3/1.md --units 3 --provider openrouter

  {theme.bold("3. Two male expert hosts instead of ALEX + MAYA:")}
    /generate week3/1.md --format dual-tutor --provider openrouter

  {theme.bold("4. Preview before generating (no LLM calls for audio):")}
    /inspect week3/1.md                        (show chunk breakdown)
    /dry-run week3/1.md                        (show planned units, no audio)

  {theme.bold("5. Read-along (ALEX narrates the document top to bottom):")}
    /generate week3/1.md --explain
    /play week3_1_explain

  {theme.bold("6. Render a video from an existing session:")}
    /generate week3/1.md --provider openrouter (generate audio first)
    /video week3_1                             (render slides + subtitles → MP4)
    /vsessions                                 (list completed videos)

  {theme.bold("7. See all sessions:")}
    /sessions
"""
    print(lines)


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

COMMAND_MAP: dict[str, CommandFn | None] = {
    "/generate": cmd_generate,
    "/gen": cmd_generate,
    "/sessions": cmd_sessions,
    "/play": cmd_play,
    "/pause": cmd_pause,
    "/resume": cmd_resume,
    "/stop": cmd_stop,
    "/next": cmd_next,
    "/prev": cmd_prev,
    "/back": cmd_prev,
    "/replay": cmd_replay,
    "/ask": cmd_ask,
    "/summary": cmd_summary,
    "/status": cmd_status,
    "/inspect": cmd_inspect,
    "/dry-run": cmd_dryrun,
    "/dryrun": cmd_dryrun,
    "/clear": cmd_clear,
    "/help": cmd_help,
    "/?": cmd_help,
    "/quit": None,
    "/exit": None,
    "/q": None,
}
