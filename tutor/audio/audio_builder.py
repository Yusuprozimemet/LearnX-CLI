import asyncio
import logging
import shutil
from pathlib import Path

from pydub import AudioSegment
from tqdm import tqdm

from tutor.audio.tts_renderer import render_segment
from tutor.constants import (
    SILENCE_BREATH_MS,
    SILENCE_TURN_MS,
    SILENCE_UNIT_MS,
    TTS_SEMAPHORE_LIMIT,
)
from tutor.models import DialogueLine, RenderedSegment

log = logging.getLogger(__name__)


async def build(lines: list[DialogueLine], out_path: str, units_dir: str) -> None:
    """
    Entry point from tutor.py via asyncio.run(audio_builder.build(...)).
    This is the single sync→async crossing point for the entire pipeline.
    """
    tmp_dir = str(Path(out_path).parent / ".tts_tmp")
    Path(tmp_dir).mkdir(parents=True, exist_ok=True)
    Path(units_dir).mkdir(parents=True, exist_ok=True)

    segments = await _render_all(lines, tmp_dir)
    _assemble(segments, out_path, units_dir)
    _cleanup_tmp(tmp_dir)
    log.info("Audio saved: %s", out_path)


async def _render_all(lines: list[DialogueLine], tmp_dir: str) -> list[RenderedSegment]:
    semaphore = asyncio.Semaphore(TTS_SEMAPHORE_LIMIT)
    results: list[RenderedSegment | None] = [None] * len(lines)

    with tqdm(total=len(lines), desc="Generating audio", unit="seg") as pbar:
        async def render_one(idx: int, line: DialogueLine) -> None:
            async with semaphore:
                results[idx] = await render_segment(line, tmp_dir, idx)
                pbar.update(1)

        await asyncio.gather(*[render_one(i, line) for i, line in enumerate(lines)])

    return [r for r in results if r is not None]


def _assemble(segments: list[RenderedSegment], out_path: str, units_dir: str) -> None:
    unit_groups: dict[int, list[RenderedSegment]] = {}
    for seg in segments:
        unit_num = seg.line.unit_number
        unit_groups.setdefault(unit_num, []).append(seg)

    # Sort: intro (0) first, then units (1..N), outro (-1) last
    sorted_keys = sorted(unit_groups.keys(), key=lambda x: 999 if x == -1 else x)

    unit_audio: list[AudioSegment] = []
    for unit_num in sorted_keys:
        group = unit_groups[unit_num]
        combined = _concat_with_silence(group)

        if unit_num == 0:
            unit_label = "unit_00_intro"
        elif unit_num == -1:
            unit_label = "unit_99_outro"
        else:
            unit_label = f"unit_{unit_num:02d}"

        unit_path = str(Path(units_dir) / f"{unit_label}.mp3")
        combined.export(unit_path, format="mp3")
        log.info("Saved unit: %s", unit_path)

        unit_audio.append(combined)
        if unit_num != -1:
            unit_audio.append(AudioSegment.silent(duration=SILENCE_UNIT_MS))

    full_audio = sum(unit_audio, AudioSegment.empty())
    full_audio.export(out_path, format="mp3")
    log.info("Saved full audio: %s (%d segments)", out_path, len(segments))


def _concat_with_silence(segments: list[RenderedSegment]) -> AudioSegment:
    result = AudioSegment.empty()
    prev_speaker: str | None = None

    for seg in segments:
        audio = AudioSegment.from_mp3(seg.audio_path)
        if prev_speaker is None:
            pass
        elif prev_speaker == seg.line.speaker:
            result += AudioSegment.silent(duration=SILENCE_BREATH_MS)
        else:
            result += AudioSegment.silent(duration=SILENCE_TURN_MS)
        result += audio
        prev_speaker = seg.line.speaker

    return result


def _cleanup_tmp(tmp_dir: str) -> None:
    shutil.rmtree(tmp_dir, ignore_errors=True)
