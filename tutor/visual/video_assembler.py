"""
ffmpeg wrappers for assembling slides + audio into MP4 videos.
No Pillow, no LLM, no audio processing here — only subprocess calls.
"""

import logging
import subprocess
from pathlib import Path

from tutor.exceptions import VideoError

log = logging.getLogger(__name__)

ENCODE_PRESET = "medium"
ENCODE_CRF = "23"
AUDIO_BITRATE = "128k"
TITLE_DURATION = "4"
OUTRO_DURATION = "6"
SCALE_FILTER = (
    "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2"
)


def assemble_session(
    session_dir: Path,
    audio_dir: Path,
    slide_timings: list[tuple[Path, float]],
    unit_mp3s: list[Path],
    srt_path: Path,
) -> Path:
    """
    Full pipeline: renders per-unit MP4s then concatenates into full_session.mp4.
    Returns path to full_session.mp4.
    """
    # Collect special slides
    title_entry = next(((p, d) for p, d in slide_timings if "_title" in p.stem), None)
    outro_entry = next(((p, d) for p, d in slide_timings if "_outro" in p.stem), None)

    # Group remaining slides by unit
    unit_entries: dict[int, list[tuple[Path, float]]] = {}
    for p, d in slide_timings:
        stem = p.stem
        if "_title" in stem or "_outro" in stem:
            continue
        try:
            unit_idx = int(stem[:2])
        except ValueError:
            continue
        unit_entries.setdefault(unit_idx, []).append((p, d))

    unit_mp4s: list[Path] = []
    total_steps = 2 + len(unit_mp3s) + 2  # title, N units, concat, subtitles
    step = 0

    # Title card
    step += 1
    print(f"  [{step}/{total_steps}] Generating title card video...")
    if title_entry:
        title_mp4 = _build_title_video(title_entry[0], session_dir / "unit_00_title.mp4")
        unit_mp4s.append(title_mp4)

    # Per-unit videos
    for mp3_idx, mp3 in enumerate(unit_mp3s, start=1):
        step += 1
        entries = unit_entries.get(mp3_idx, [])
        unit_name = mp3.stem
        print(
            f"  [{step}/{total_steps}] Rendering unit {mp3_idx}/{len(unit_mp3s)} — {unit_name}..."
        )
        out = session_dir / f"unit_{mp3_idx:02d}.mp4"
        _build_unit_video(entries, mp3, out)
        unit_mp4s.append(out)

    # Outro card
    if outro_entry:
        outro_mp4 = _build_outro_video(outro_entry[0], session_dir / "unit_99_outro.mp4")
        unit_mp4s.append(outro_mp4)

    # Concatenate
    step += 1
    print(f"  [{step}/{total_steps}] Concatenating full session...")
    nosub = session_dir / "full_session_nosub.mp4"
    _concat_unit_videos(unit_mp4s, nosub)

    # Embed subtitles (skip if SRT is empty)
    step += 1
    print(f"  [{step}/{total_steps}] Embedding subtitles...")
    final = session_dir / "full_session.mp4"
    if srt_path.exists() and srt_path.stat().st_size > 20:
        _embed_subtitles(nosub, srt_path, final)
    else:
        log.warning("SRT is empty — copying video without subtitle track")
        nosub.rename(final)

    size_mb = final.stat().st_size / 1_048_576
    print(f"  OK  {final}  ({size_mb:.0f} MB)")
    return final


def _build_title_video(title_slide: Path, output: Path) -> Path:
    _run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(title_slide),
            "-t",
            TITLE_DURATION,
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-c:v",
            "libx264",
            "-preset",
            ENCODE_PRESET,
            "-crf",
            ENCODE_CRF,
            "-c:a",
            "aac",
            "-b:a",
            AUDIO_BITRATE,
            "-pix_fmt",
            "yuv420p",
            "-vf",
            SCALE_FILTER,
            "-shortest",
            str(output),
        ]
    )
    return output


def _build_unit_video(
    slides_with_dur: list[tuple[Path, float]],
    mp3: Path,
    output: Path,
) -> Path:
    if not slides_with_dur:
        log.warning("No slides for %s — skipping", mp3.name)
        return output

    script_path = output.with_suffix(".concat.txt")
    _write_concat_script(slides_with_dur, script_path)

    _run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(script_path),
            "-i",
            str(mp3),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-preset",
            ENCODE_PRESET,
            "-crf",
            ENCODE_CRF,
            "-c:a",
            "aac",
            "-b:a",
            AUDIO_BITRATE,
            "-ar",
            "44100",
            "-ac",
            "2",
            "-af",
            "volume=5dB",
            "-pix_fmt",
            "yuv420p",
            "-vf",
            SCALE_FILTER,
            "-shortest",
            str(output),
        ]
    )
    return output


def _build_outro_video(outro_slide: Path, output: Path) -> Path:
    _run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(outro_slide),
            "-t",
            OUTRO_DURATION,
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-c:v",
            "libx264",
            "-preset",
            ENCODE_PRESET,
            "-crf",
            ENCODE_CRF,
            "-c:a",
            "aac",
            "-b:a",
            AUDIO_BITRATE,
            "-pix_fmt",
            "yuv420p",
            "-vf",
            SCALE_FILTER,
            "-shortest",
            str(output),
        ]
    )
    return output


def _concat_unit_videos(unit_mp4s: list[Path], output: Path) -> Path:
    list_path = output.parent / "unit_list.txt"
    lines = ["ffconcat version 1.0"] + [f"file '{p.name}'" for p in unit_mp4s]
    list_path.write_text("\n".join(lines), encoding="utf-8")

    _run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-c",
            "copy",
            str(output),
        ]
    )
    return output


def _embed_subtitles(video: Path, srt: Path, output: Path) -> Path:
    _run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-i",
            str(srt),
            "-c",
            "copy",
            "-c:s",
            "mov_text",
            "-metadata:s:s:0",
            "language=eng",
            str(output),
        ]
    )
    return output


def _write_concat_script(entries: list[tuple[Path, float]], script_path: Path) -> None:
    lines = ["ffconcat version 1.0"]
    for path, dur in entries:
        abs_path = str(path.resolve()).replace("\\", "/")
        lines.append(f"file '{abs_path}'")
        lines.append(f"duration {dur:.3f}")
    # Repeat last file without duration (ffmpeg concat requirement)
    if entries:
        abs_last = str(entries[-1][0].resolve()).replace("\\", "/")
        lines.append(f"file '{abs_last}'")
    script_path.write_text("\n".join(lines), encoding="utf-8")


def _run_ffmpeg(args: list[str]) -> None:
    log.debug("Running: %s", " ".join(args))
    result = subprocess.run(args, capture_output=True, timeout=600)
    if result.returncode != 0:
        err = result.stderr.decode("utf-8", errors="replace")[-500:]
        raise VideoError(f"ffmpeg failed (exit {result.returncode}):\n{err}")
