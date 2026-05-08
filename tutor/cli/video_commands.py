"""
Shell command handlers for the video pipeline.
Separate from commands.py so the audio pipeline file stays under 400 lines.
"""
import logging
from functools import partial
from pathlib import Path

from tutor.cli import theme
from tutor.cli.commands import AUDIO_DIR, ShellContext, _session_name

log = logging.getLogger(__name__)

VIDEO_DIR = Path("video")


def cmd_video(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /video [session-name]
    Generate MP4 video for a session. Requires /generate to have run first."""
    if not tokens:
        if ctx.current_session:
            session = ctx.current_session
        else:
            print(theme.red("  Usage: /video <session-name>"))
            return
    else:
        session = tokens[0]

    audio_session_dir = AUDIO_DIR / session
    try:
        _assert_audio_ready(audio_session_dir)
    except Exception as e:
        print(theme.red(f"  Error: {e}"))
        return

    mp4_path = VIDEO_DIR / session / "full_session.mp4"
    if mp4_path.exists():
        if not _confirm_overwrite(mp4_path):
            print(theme.dim("  Skipped."))
            return

    try:
        _run_video_pipeline(session, ctx)
    except KeyboardInterrupt:
        print(theme.yellow("\n  Cancelled."))
    except Exception as e:
        print(theme.red(f"\n  Error: {e}\n"))
        log.exception("Video pipeline failed for session %s", session)


def cmd_vsessions(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /vsessions — list sessions that have a completed video."""
    if not VIDEO_DIR.exists():
        print(theme.dim("  No video sessions yet. Use /video <session> to create one."))
        return

    sessions = sorted(
        d for d in VIDEO_DIR.iterdir()
        if d.is_dir() and (d / "full_session.mp4").exists()
    )
    if not sessions:
        print(theme.dim("  No completed videos yet. Use /video <session-name>."))
        return

    print()
    for s in sessions:
        mp4 = s / "full_session.mp4"
        size_mb = mp4.stat().st_size / 1_048_576
        print(f"  {theme.cyan(s.name):<30} {theme.green('[mp4]')}  {size_mb:.0f} MB")
    print(theme.dim("\n  Play with your video player: vlc video/<session>/full_session.mp4"))
    print()


def _run_video_pipeline(session: str, ctx: ShellContext) -> None:
    """Resolve paths and run the full visual pipeline."""
    from tutor.visual import run_visual_pipeline
    from tutor.config import load_config
    from tutor.infra import llm as _llm

    config    = load_config()
    provider  = "groq"
    llm_fn    = partial(_llm.chat, provider=provider, config=config)
    video_dir = VIDEO_DIR / session
    video_dir.mkdir(parents=True, exist_ok=True)

    audio_dir = AUDIO_DIR / session
    units = list((audio_dir / "tutorial_units").glob("unit_*.mp3"))
    print(f"\n  Resolving session {theme.bold(session)}...")
    print(f"  Found {len(units)} units. Starting visual pipeline.")

    result = run_visual_pipeline(
        session, audio_dir, video_dir, llm_fn, difficulty="beginner"
    )
    ctx.last_video = result
    ctx.current_session = session


def _assert_audio_ready(audio_session_dir: Path) -> None:
    """Raise ValueError if the audio session is not ready."""
    if not audio_session_dir.exists():
        raise ValueError(
            f"Session '{audio_session_dir.name}' not found in {AUDIO_DIR}/.\n"
            "  Run /generate first to produce audio."
        )
    units_json = audio_session_dir / "tutorial.units.json"
    if not units_json.exists():
        raise ValueError(
            f"tutorial.units.json not found in {audio_session_dir}.\n"
            "  The audio pipeline must complete before running /video."
        )
    mp3s = list((audio_session_dir / "tutorial_units").glob("unit_*.mp3"))
    if not mp3s:
        raise ValueError(
            f"No MP3 files found in {audio_session_dir / 'tutorial_units'}.\n"
            "  Run /generate (without --script-only) to produce audio."
        )


def _confirm_overwrite(mp4_path: Path) -> bool:
    """Prompt if full_session.mp4 already exists. Returns True to proceed."""
    try:
        answer = input("  Session already has a video. Regenerate? [y/N]: ").strip().lower()
        return answer == "y"
    except (EOFError, KeyboardInterrupt):
        return False
