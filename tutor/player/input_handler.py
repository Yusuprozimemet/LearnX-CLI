import logging
import sys

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
        import threading

        import readchar

        result: list[str | None] = [None]

        def _read() -> None:
            result[0] = readchar.readchar()

        t = threading.Thread(target=_read, daemon=True)
        t.start()
        t.join(timeout=0.05)
        return result[0]
    except ImportError:
        log.warning(
            "readchar not installed — keyboard input unavailable on non-Windows. pip install readchar"
        )
        return None
