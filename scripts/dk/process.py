import subprocess
import threading
import time


def _extract_int_flag(args: list[str], flag: str) -> tuple[int | None, list[str]]:
    """Pop --flag N from args. Return (int_value_or_None, remaining_args)."""
    if flag not in args:
        return None, args
    idx = args.index(flag)
    try:
        val = int(args[idx + 1])
        return val, args[:idx] + args[idx + 2 :]
    except (IndexError, ValueError):
        return None, args


def _is_rate_limited(last_lines: list[str], patterns: list[str]) -> bool:
    """Return True if any pattern appears (case-insensitive) in the last output lines."""
    text = "\n".join(last_lines).lower()
    return any(p.lower() in text for p in patterns)


def _run_with_timeout(
    cmd: list[str],
    session_timeout_s: float,
    idle_timeout_s: float,
) -> tuple[int, list[str], bool]:
    """Run cmd non-interactively with output streaming and two kill triggers.

    Returns:
        returncode   — process exit code (-9 or similar if killed)
        last_lines   — last 200 stdout+stderr lines (for rate-limit detection)
        timed_out    — True if killed by session or idle timeout
    """
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )

    ring: list[str] = []
    last_output_at = [time.monotonic()]
    timed_out = [False]

    def _reader() -> None:
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = raw.decode(errors="replace").rstrip()
            print(line, flush=True)
            ring.append(line)
            if len(ring) > 200:
                ring.pop(0)
            last_output_at[0] = time.monotonic()

    def _watchdog() -> None:
        deadline = time.monotonic() + session_timeout_s
        while proc.poll() is None:
            now = time.monotonic()
            if idle_timeout_s > 0 and (now - last_output_at[0]) > idle_timeout_s:
                print(
                    f"\n[resilience] idle timeout "
                    f"({idle_timeout_s / 60:.0f} min) — killing session",
                    flush=True,
                )
                timed_out[0] = True
                proc.kill()
                return
            if now > deadline:
                print(
                    f"\n[resilience] session timeout "
                    f"({session_timeout_s / 60:.0f} min) — killing session",
                    flush=True,
                )
                timed_out[0] = True
                proc.kill()
                return
            time.sleep(2)

    t_read = threading.Thread(target=_reader, daemon=True)
    t_watch = threading.Thread(target=_watchdog, daemon=True)
    t_read.start()
    t_watch.start()
    proc.wait()
    t_read.join(timeout=5)

    return proc.returncode, ring, timed_out[0]
