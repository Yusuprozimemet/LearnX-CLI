import argparse
import asyncio
import io
import json
import logging
import shutil
import sys
from dataclasses import asdict
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tutor.player.player import TutorPlayer

from tutor import inspector
from tutor.audio import audio_builder
from tutor.config import preflight
from tutor.constants import (
    DEFAULT_DIFFICULTY,
    DEFAULT_DURATION_MIN,
    DEFAULT_FORMAT,
    DEFAULT_SUBJECT,
    WPM,
)
from tutor.exceptions import TutorError
from tutor.generation import assembler, curriculum, dialogue
from tutor.infra import llm
from tutor.ingestion import chunker, doc_analyzer, summarizer
from tutor.models import Chunk, DialogueLine, DocProfile, TeachingUnit


def main() -> None:
    # Force UTF-8 output on Windows so LLM-generated unicode (≠, →, etc.) doesn't crash.
    # Done here (not at module level) so pytest's stdout capture isn't affected.
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    # Detect "play" subcommand before building the main parser — argparse
    # cannot handle a positional that is either a subcommand or a file path.
    if len(sys.argv) > 1 and sys.argv[1] == "play":
        _run_play()
        return

    parser = argparse.ArgumentParser(prog="tutor", description="Tutor AI — Java audio sessions")
    parser.add_argument("input", nargs="?", help="Path to input .md file")
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

    args = parser.parse_args()
    _setup_logging(args)

    try:
        cmd_generate(args)
    except TutorError as e:
        print(f"\n✗ {e}", file=sys.stderr)
        sys.exit(1)


def _run_play() -> None:
    parser = argparse.ArgumentParser(prog="tutor play")
    parser.add_argument("audio_file")
    parser.add_argument("--provider", default="groq")
    parser.add_argument("--no-qa", action="store_true", dest="no_qa")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args(sys.argv[2:])
    _setup_logging(args)
    try:
        cmd_play(args)
    except TutorError as e:
        print(f"\n✗ {e}", file=sys.stderr)
        sys.exit(1)


def cmd_generate(args: argparse.Namespace) -> None:
    mode = _mode(args)
    config = preflight(args.input, args.provider, mode)
    llm_fn = partial(llm.chat, provider=args.provider, config=config)

    if args.no_cache:
        cache_dir = Path(".tutor_cache")
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
            print("Cache cleared (all summaries and dialogues will be regenerated).")

    profile = doc_analyzer.analyze(args.input)
    chunks = chunker.chunk(Path(args.input).read_text(encoding="utf-8"), profile)

    if not args.inspect:
        chunks = summarizer.summarize_all(chunks, llm_fn)
        _save_chunks(chunks, args.output)

    if args.inspect:
        _run_inspect(args, profile, chunks)
        return

    if args.subject not in ("java", "general"):
        print(f"Warning: --subject {args.subject!r} is not supported yet; proceeding as 'general'.")

    units = curriculum.plan(chunks, profile, args.duration, llm_fn, args.difficulty, args.topic)
    if args.units:
        units = units[: args.units]

    if args.dry_run:
        inspector.report_curriculum(units, chunks, args.duration)
        return

    all_lines = [dialogue.generate(u, chunks, args.fmt, llm_fn, args.difficulty) for u in units]
    doc_title = Path(args.input).stem.replace("-", " ").replace("_", " ").title()
    script = assembler.assemble(units, all_lines, args.fmt, doc_title)
    _print_duration_estimate(script)

    if args.script_only:
        _run_script_only(script)
        return

    _run_audio(args, units, script)

    if getattr(args, "play", False):
        cmd_play(args)


def _run_inspect(args: argparse.Namespace, profile: DocProfile, chunks: list[Chunk]) -> None:
    inspector.report_ingestion(profile, chunks)
    if args.show_summaries:
        for c in chunks:
            print(f"\n--- {c.chunk_id} ---\n{c.summary}")


def _run_script_only(script: list[DialogueLine]) -> None:
    for line in script:
        print(f"{line.speaker}: {line.text}")


def _save_chunks(chunks: list[Chunk], output_path: str) -> None:
    chunks_path = Path(output_path).parent / "tutorial.chunks.json"
    with open(chunks_path, "w", encoding="utf-8") as f:
        json.dump([asdict(c) for c in chunks], f, indent=2, ensure_ascii=False)


def _run_audio(
    args: argparse.Namespace, units: list[TeachingUnit], script: list[DialogueLine]
) -> None:
    script_path = Path(args.output).with_suffix(".script.txt")
    units_dir = str(Path(args.output).parent / "tutorial_units")

    with open(script_path, "w", encoding="utf-8") as f:
        for line in script:
            f.write(f"{line.speaker}: {line.text}\n")
    print(f"Script saved: {script_path}")
    print("Generating audio — this takes 2–4 minutes for a 20-min session...")

    asyncio.run(audio_builder.build(script, args.output, units_dir))

    units_json_path = Path(args.output).parent / "tutorial.units.json"
    with open(units_json_path, "w", encoding="utf-8") as f:
        json.dump([asdict(u) for u in units], f, indent=2, ensure_ascii=False)

    print("\nDone.")
    print(f"  Audio:  {args.output}")
    print(f"  Units:  {units_dir}/")
    print(f"  Script: {script_path}")
    print(f"  Meta:   {units_json_path}")


def cmd_play(args: argparse.Namespace) -> None:
    player = _build_player(args)
    player.run()


def _build_player(args: argparse.Namespace) -> "TutorPlayer":
    """Build and return a configured TutorPlayer without starting it."""
    import json
    from datetime import datetime
    from functools import partial as _partial

    from tutor.config import load_config
    from tutor.exceptions import PlayerError
    from tutor.infra import llm as _llm
    from tutor.models import Chunk, SessionLog, TeachingUnit
    from tutor.player.player import TutorPlayer

    _log = logging.getLogger(__name__)

    if hasattr(args, "audio_file"):
        audio_path = Path(args.audio_file)
        units_dir = audio_path if audio_path.is_dir() else audio_path.parent / "tutorial_units"
    else:
        units_dir = Path(args.output).parent / "tutorial_units"

    if not units_dir.exists():
        raise PlayerError(
            f"tutorial_units/ not found at {units_dir}.\n  Run generation first or use /generate."
        )

    unit_files = sorted(units_dir.glob("*.mp3"))
    if not unit_files:
        raise PlayerError(f"No .mp3 files found in {units_dir}")

    units_json = units_dir.parent / "tutorial.units.json"
    if units_json.exists():
        with open(units_json, encoding="utf-8") as f:
            raw_units = json.load(f)
        for u in raw_units:
            u.setdefault("prerequisite_concepts", [])
        units = [TeachingUnit(**u) for u in raw_units]
    else:
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

    chunks_path = units_dir.parent / "tutorial.chunks.json"
    if chunks_path.exists():
        with open(chunks_path, encoding="utf-8") as f:
            raw_chunks = json.load(f)
        chunks = [Chunk(**c) for c in raw_chunks]
    else:
        chunks = []
        _log.warning("tutorial.chunks.json not found — Q&A will work without source context")

    no_qa = getattr(args, "no_qa", False)
    provider = getattr(args, "provider", "groq")
    if no_qa:
        llm_fn = None
    else:
        try:
            config = load_config()
            llm_fn = _partial(_llm.chat, provider=provider, config=config)
        except Exception:
            llm_fn = None
            _log.warning("Could not load config for Q&A — Q&A will be unavailable")

    session = SessionLog(
        source_file=str(getattr(args, "audio_file", getattr(args, "output", "unknown"))),
        session_start=datetime.utcnow().isoformat(),
        format="tutor-student",
        duration_minutes=20,
    )

    return TutorPlayer(
        unit_files=[str(f) for f in unit_files],
        units=units,
        chunks=chunks,
        session=session,
        llm_fn=llm_fn,
        no_qa=no_qa,
    )


def _make_generate_parser() -> argparse.ArgumentParser:
    """Return an ArgumentParser for the /generate shell command."""
    parser = argparse.ArgumentParser(prog="generate", add_help=False)
    parser.add_argument("input", nargs="?")
    parser.add_argument("--output", default="tutorial.mp3")
    parser.add_argument("--provider", default="groq")
    parser.add_argument("--duration", type=int, default=DEFAULT_DURATION_MIN)
    parser.add_argument("--format", default=DEFAULT_FORMAT, dest="fmt")
    parser.add_argument("--difficulty", default=DEFAULT_DIFFICULTY)
    parser.add_argument("--units", type=int, default=None)
    parser.add_argument("--subject", default=DEFAULT_SUBJECT)
    parser.add_argument("--topic", default=None)
    parser.add_argument("--script-only", action="store_true", dest="script_only")
    parser.add_argument("--dry-run", action="store_true", dest="dry_run")
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument("--show-summaries", action="store_true", dest="show_summaries")
    parser.add_argument("--no-cache", action="store_true", dest="no_cache")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--debug", action="store_true")
    return parser


def _mode(args: argparse.Namespace) -> str:
    if getattr(args, "inspect", False):
        return "inspect"
    if getattr(args, "dry_run", False):
        return "dry-run"
    if getattr(args, "script_only", False):
        return "script-only"
    return "generate"  # triggers ffmpeg check in preflight


def _print_duration_estimate(script: list[DialogueLine]) -> None:
    total_words = sum(len(line.text.split()) for line in script)
    dialogue_secs = (total_words / WPM) * 60
    silence_secs = 80
    total_secs = int(dialogue_secs + silence_secs)
    mins, secs = divmod(total_secs, 60)
    print("\n=== Duration Estimate ===")
    print(f"Script words:  {total_words:,}")
    print(f"Estimated:     ~{mins}m {secs:02d}s (incl. pauses)")


def _setup_logging(args: argparse.Namespace) -> None:
    if getattr(args, "debug", False):
        level = logging.DEBUG
        logging.basicConfig(
            level=level,
            filename="tutor.log",
            format="%(asctime)s %(name)s %(levelname)s %(message)s",
        )
    elif getattr(args, "verbose", False):
        level = logging.INFO
        logging.basicConfig(level=level, format="%(levelname)s %(message)s")
    else:
        logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")


if __name__ == "__main__":
    main()
