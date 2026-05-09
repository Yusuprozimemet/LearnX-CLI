import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from tutor.exceptions import ConfigError


@dataclass
class Config:
    groq_api_key: str = ""
    openrouter_api_key: str = ""
    default_provider: str = "groq"


def load_config() -> Config:
    load_dotenv(Path(__file__).parent / ".env")
    return Config(
        groq_api_key=os.getenv("GROQ_API_KEY", ""),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
    )


def preflight(input_path: str, provider: str, mode: str) -> Config:
    config = load_config()

    if mode not in ("inspect", "dry-run", "script-only"):
        if input_path is None:
            raise ConfigError(
                "No input file specified.\n  Usage: python tutor.py <input.md> [options]"
            )

    if input_path is not None:
        p = Path(input_path)
        if not p.exists():
            raise ConfigError(
                f"Input file not found: {input_path}\n  Check the path and try again."
            )
        if p.suffix.lower() != ".md":
            raise ConfigError(
                f"Input file must be a .md file, got: {p.suffix}\n  Only Markdown files are supported."
            )

    if provider == "groq" and not config.groq_api_key:
        raise ConfigError(
            "GROQ_API_KEY not set.\n"
            "  Add it to tutor/.env: GROQ_API_KEY=gsk_...\n"
            "  Get a free key at: console.groq.com"
        )

    if provider == "openrouter" and not config.openrouter_api_key:
        raise ConfigError(
            "OPENROUTER_API_KEY not set.\n"
            "  Add it to tutor/.env: OPENROUTER_API_KEY=sk-or-...\n"
            "  Sign up at: openrouter.ai"
        )

    if mode not in ("script-only", "dry-run", "inspect") and input_path:
        out_parent = Path(input_path).parent
        if not os.access(out_parent, os.W_OK):
            raise ConfigError(
                f"Output directory is not writable: {out_parent}\n"
                "  Check permissions or specify a different --output path."
            )

    if mode == "generate":
        _check_ffmpeg()

    return config


def _check_ffmpeg() -> None:
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    # PATH doesn't have ffmpeg — probe common Windows install layouts.
    if sys.platform == "win32":
        candidates: list[Path] = [
            Path("C:/ffmpeg/bin/ffmpeg.exe"),
            *Path("C:/ffmpeg").glob("*/bin/ffmpeg.exe"),
            Path("C:/Program Files/ffmpeg/bin/ffmpeg.exe"),
            *Path("C:/Program Files/ffmpeg").glob("*/bin/ffmpeg.exe"),
            Path("C:/tools/ffmpeg/bin/ffmpeg.exe"),
        ]
        for candidate in candidates:
            if candidate.exists():
                _inject_ffmpeg(candidate.parent)
                return

    raise ConfigError(
        "ffmpeg not found in PATH.\n"
        "  Install with: winget install ffmpeg\n"
        "  Or add its bin\\ folder to your system PATH and restart the terminal."
    )


def _inject_ffmpeg(bin_dir: Path) -> None:
    """Add a discovered ffmpeg directory to the process PATH so pydub finds it."""
    os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")
    # Patch pydub's runtime converter path if pydub is already imported.
    try:
        import pydub

        pydub.AudioSegment.converter = str(bin_dir / "ffmpeg.exe")
        pydub.AudioSegment.ffmpeg = str(bin_dir / "ffmpeg.exe")
        pydub.AudioSegment.ffprobe = str(bin_dir / "ffprobe.exe")
    except Exception:
        pass
