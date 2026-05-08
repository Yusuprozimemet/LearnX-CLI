import sys

from tutor.cli.logo import print_welcome
from tutor.cli.commands import COMMAND_MAP, ShellContext
from tutor.cli import theme


def _build_prompt(ctx: ShellContext) -> str:
    p = ctx.player
    if p is None or p._state == "STOPPED":
        return f"{theme.CYAN}LearnX{theme.RESET} > "
    icon = {"PLAYING": "▶", "PAUSED": "⏸", "ASKING": "?", "ANSWERING": "⟳"}.get(p._state, "·")
    if p._current_idx < len(p.units):
        unit = p.units[p._current_idx]
        concept = unit.concept[:22]
        idx_str = f"{p._current_idx + 1}/{len(p.units)}"
        return f"{theme.CYAN}LearnX{theme.RESET} [{icon} {idx_str}  {concept}] > "
    return f"{theme.CYAN}LearnX{theme.RESET} [{icon}] > "


def run_shell() -> None:
    _setup_utf8()
    _prime_ffmpeg()
    print_welcome()
    ctx = ShellContext()

    while True:
        try:
            line = input(_build_prompt(ctx)).strip()
        except (KeyboardInterrupt, EOFError):
            print()
            _graceful_exit(ctx)
            break

        if not line:
            continue

        # Bare text while a session is active → route as /ask
        if not line.startswith("/") and ctx.player and ctx.player._state not in ("STOPPED", None):
            from tutor.cli.commands import cmd_ask
            cmd_ask(line.split(), ctx)
            continue

        parts = line.split()
        cmd = parts[0].lower() if parts else ""
        tokens = parts[1:]

        if cmd not in COMMAND_MAP:
            print(theme.yellow(f"  Unknown command: {cmd}  — type /help for a list."))
            continue

        handler = COMMAND_MAP[cmd]
        if handler is None:
            _graceful_exit(ctx)
            break

        handler(tokens, ctx)


def _graceful_exit(ctx: ShellContext) -> None:
    if ctx.player and ctx.player._state not in ("STOPPED",):
        ctx.player._quit()
        if ctx.player_thread:
            ctx.player_thread.join(timeout=2.0)
    print(theme.dim("  Goodbye!\n"))


def _prime_ffmpeg() -> None:
    """Inject ffmpeg into PATH before pydub is imported so its warning never fires."""
    try:
        from tutor.config import _check_ffmpeg
        _check_ffmpeg()
    except Exception:
        pass


def _setup_utf8() -> None:
    if hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer"):
        import io
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
