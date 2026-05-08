import logging
import os
from pathlib import Path

import edge_tts
from pydub import AudioSegment

from tutor.constants import RATE_COTUTOR, RATE_STUDENT, RATE_TUTOR, VOICE_COTUTOR, VOICE_STUDENT, VOICE_TUTOR
from tutor.exceptions import TTSError
from tutor.models import DialogueLine, RenderedSegment

log = logging.getLogger(__name__)

VOICE_MAP: dict[str, str] = {
    "ALEX": VOICE_TUTOR,
    "MAYA": VOICE_STUDENT,
    "SAM": VOICE_COTUTOR,
}

RATE_MAP: dict[str, str] = {
    "ALEX": RATE_TUTOR,
    "MAYA": RATE_STUDENT,
    "SAM": RATE_COTUTOR,
}


async def render_segment(line: DialogueLine, out_dir: str, idx: int) -> RenderedSegment:
    voice = VOICE_MAP.get(line.speaker, VOICE_TUTOR)
    rate = RATE_MAP.get(line.speaker, RATE_TUTOR)
    out_path = str(Path(out_dir) / f"seg_{line.unit_number:03d}_{idx:04d}.mp3")

    try:
        communicate = edge_tts.Communicate(line.text, voice, rate=rate)
        await communicate.save(out_path)
    except Exception as e:
        raise TTSError(f"TTS failed for line {idx}: {e}") from e

    if os.path.getsize(out_path) == 0:
        raise TTSError(f"TTS returned empty file for line {idx}: {line.text[:60]}")

    try:
        audio = AudioSegment.from_mp3(out_path)
        duration_ms = len(audio)
    except Exception as e:
        raise TTSError(f"Could not read rendered segment {out_path}: {e}") from e

    return RenderedSegment(line=line, audio_path=out_path, duration_ms=duration_ms)
