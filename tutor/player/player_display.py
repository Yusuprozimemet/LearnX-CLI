import sys
import logging
from tutor.models import TeachingUnit
from tutor.constants import PLAYER_BAR_WIDTH

log = logging.getLogger(__name__)

BORDER = "━" * 56
COMMANDS_PLAYING = "  [space] pause   [?] ask   [n] next   [b] prev   [q] quit"
COMMANDS_PAUSED  = "  [space] resume   [?] ask   [n] next   [b] prev   [r] replay   [s] summary   [q] quit"

_first_render = True


def render_status(
    unit: TeachingUnit,
    unit_idx: int,
    total_units: int,
    elapsed_s: int,
    total_s: int,
    state: str,
) -> None:
    """Redraw the status bar in-place using ANSI escape codes. Does not scroll."""
    global _first_render
    if not _first_render:
        clear_status()
    _first_render = False

    bar = _progress_bar(elapsed_s, total_s)
    elapsed_fmt = _fmt_time(elapsed_s)
    total_fmt = _fmt_time(total_s)
    state_tag = "  ⏸ PAUSED" if state == "PAUSED" else ""

    line1 = f"  {unit.concept} — Unit {unit_idx}/{total_units}{state_tag}"
    line2 = f"  {bar}  {elapsed_fmt} / {total_fmt}"
    cmds = COMMANDS_PAUSED if state in ("PAUSED", "ASKING") else COMMANDS_PLAYING

    sys.stdout.write(f"{BORDER}\n{line1}\n{line2}\n{BORDER}\n{cmds}\n")
    sys.stdout.flush()


def clear_status() -> None:
    """Move cursor up 5 lines and clear each line."""
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


def print_qa_disabled() -> None:
    print("\nQ&A disabled (--no-qa). Press [space] to resume.")


def print_thinking() -> None:
    print("\nThinking...", end="", flush=True)


def print_no_context() -> None:
    print("\n(No unit context available)")


def print_resume_hint() -> None:
    print("Press [space] to resume or [?] to ask another question.\n")


def print_question_header(topic: str, position_fmt: str) -> None:
    print(f"\n── Ask a question ──────────────────────────────────")
    print(f"Topic: {topic}  |  Position: {position_fmt}")
    print()


def print_cancelled() -> None:
    print(" (cancelled)")


def print_answer(answer: str, unit_concept: str) -> None:
    border = "─" * 56
    print(f"\n{border}")
    print(f"Answer:\n{answer}")
    suffix = border[len(unit_concept) + 10:]
    print(f"\n── Source: §{unit_concept} {suffix}")
    print()


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
