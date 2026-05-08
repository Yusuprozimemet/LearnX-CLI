# Day 11 — Subtitle Writer + Video Assembler

## Goal

Combine the slide PNGs from Day 10 with the MP3 audio files from the audio pipeline
into MP4 video files. Add a subtitle track derived from the dialogue script.
Use only ffmpeg (already installed) — no moviepy, no OpenCV.

**This module is split across three files** to stay under the 400-line limit:

| File | Responsibility | ~Lines |
|---|---|---|
| `tutor/visual/subtitle_writer.py` | Dialogue script → SRT string | ~110 |
| `tutor/visual/beat_timer.py` | Slide timing from line offsets | ~120 |
| `tutor/visual/video_assembler.py` | ffmpeg command wrappers | ~200 |

---

## Data boundary

```
Reads:
  audio/<session>/tutorial_units/unit_*.mp3   ← audio input (read-only)
  video/<session>/slides/*.png                ← slide PNGs from Day 10

Writes:
  video/<session>/subtitles.srt
  video/<session>/unit_01.mp4 ... unit_N.mp4
  video/<session>/full_session.mp4
```

No LLM calls, no Pillow, no units JSON in these three files.

---

## Output structure

```
video/<session>/
  subtitles.srt
  unit_01.mp4
  unit_02.mp4
  ...
  unit_N.mp4
  full_session.mp4
```

---

## Part A — Subtitle Writer (`subtitle_writer.py`)

### SRT format

```
1
00:00:00,000 --> 00:00:04,215
ALEX: What's the main difference between an interface and an abstract class?

2
00:00:04,715 --> 00:00:08,923
MAYA: An interface is like a blueprint and an abstract class is like a contract.
```

Rules:
- Each `DialogueLine` is one subtitle entry
- Timestamps are cumulative across all units in the session
- A 500ms gap (`SILENCE_TURN_MS`) is added between turns
- A 1 200ms gap (`SILENCE_UNIT_MS`) is added between units
- Speaker name prefixed: `ALEX: ` / `MAYA: ` / `SAM: `
- Max 60 characters per subtitle line — wrap with `\n` if longer
- Minimum display duration: 1.5 seconds regardless of word count

### Timing algorithm

```python
WPM = 130   # matches constants.py

def build_srt(
    all_lines: list[DialogueLine],
    unit_durations_s: list[float],
) -> str:
    """
    all_lines: flat list across all units, in order
    unit_durations_s: actual MP3 duration per unit (for scaling)
    Returns: complete SRT string ready to write to disk
    """
```

Algorithm:
1. Compute estimated duration: `max(words / WPM * 60, 1.5)`
2. Between turns: add `SILENCE_TURN_MS / 1000`
3. After last line of each unit: add `SILENCE_UNIT_MS / 1000`
4. If unit's estimated total differs from actual MP3 duration by > 10%,
   scale all line durations for that unit proportionally
5. Format each entry as SRT with `HH:MM:SS,mmm` timestamps

### Module API

```python
def build_srt(all_lines: list[DialogueLine], unit_durations_s: list[float]) -> str:
def get_line_start_offsets(all_lines: list[DialogueLine], unit_durations_s: list[float]) -> list[float]:
    """Same pass as build_srt but returns start time in seconds per line.
    Used by beat_timer.py to assign slide transitions."""
def _line_duration(text: str) -> float:
def _scale_unit_lines(durations: list[float], actual_s: float) -> list[float]:
def _format_timestamp(seconds: float) -> str:   # → "00:01:23,456"
def _wrap_subtitle(speaker: str, text: str, max_chars: int = 60) -> str:
```

`get_line_start_offsets()` runs the same timing logic as `build_srt()` without
formatting — avoids duplicating the calculation in `beat_timer.py`.

---

## Part B — Beat Timer (`beat_timer.py`)

Slides do not change on every subtitle line. They change at **beats**: meaningful
transitions in the dialogue structure.

### Beat map

| Slide | Trigger |
|---|---|
| Title card | Session start (t=0) |
| Hook slide | Offset of first ALEX line in unit |
| Concept slide | Offset of first MAYA line in unit |
| Memory slide | Offset of last ALEX line in unit |
| Outro card | After last line of last unit |

### Module API

```python
def compute_slide_timings(
    slides: list[Path],
    script_lines: list[DialogueLine],
    line_start_offsets: list[float],
    visuals: list[VisualSpec],
    unit_durations_s: list[float],
) -> list[tuple[Path, float]]:
    """
    Return [(slide_path, duration_seconds), ...] for the ffmpeg concat script.
    Minimum slide duration: 3.0 seconds.
    Title card: fixed 4.0 seconds.
    Outro card: fixed 6.0 seconds.
    """
```

Algorithm per unit:
1. Hook slide starts at offset of line 0 of the unit (always ALEX)
2. Concept slide starts at offset of first MAYA line of the unit
3. Memory slide starts at offset of last ALEX line of the unit.
   If not detectable: `unit_start + unit_duration * 0.8`
4. Each slide's duration = next slide's start − this slide's start
5. If computed duration < 3.0 s: extend this slide and shift all subsequent
   timings forward. The audio track ends first; the last slide holds.

---

## Part C — Video Assembler (`video_assembler.py`)

### Per-unit MP4

**Step 1 — concat script** (ffmpeg concat demuxer format):

```
ffconcat version 1.0
file '../slides/02_hook.png'
duration 6.31
file '../slides/02_concept.png'
duration 38.44
file '../slides/02_memory.png'
duration 9.25
file '../slides/02_memory.png'
```

Last file appears twice with no duration (ffmpeg concat demuxer requirement).

**Step 2 — combine slides + audio:**

```bash
ffmpeg -y \
  -f concat -safe 0 -i slides/unit_02_concat.txt \
  -i audio/unit_02.mp3 \
  -c:v libx264 -preset medium -crf 23 \
  -c:a aac -b:a 128k \
  -pix_fmt yuv420p \
  -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2" \
  unit_02.mp4
```

- `-crf 23`: quality/size balance (lower = better quality)
- `-preset medium`: use `fast` for dev, `medium` for release
- `-pix_fmt yuv420p`: required for QuickTime / Windows Media Player compatibility
- `-vf scale+pad`: guarantees exactly 1920×1080 even if slide PNG is slightly off

**Step 3 — normalize audio loudness:**

```bash
ffmpeg -y -i unit_02.mp4 -af loudnorm=I=-16:TP=-1.5:LRA=11 unit_02_norm.mp4
```

Single-pass loudnorm (two-pass deferred to v3).

### Title and outro cards

Generated with silent audio since they have no corresponding MP3:

```bash
ffmpeg -y \
  -loop 1 -i slides/00_title.png -t 4 \
  -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100 \
  -c:v libx264 -preset medium -crf 23 \
  -c:a aac -b:a 128k \
  -pix_fmt yuv420p \
  -shortest \
  unit_title.mp4
```

Same command for outro, with `-t 6`.

### Full session MP4

**Step 1 — unit list file:**

```
ffconcat version 1.0
file 'unit_00_title.mp4'
file 'unit_01.mp4'
file 'unit_02.mp4'
...
file 'unit_99_outro.mp4'
```

**Step 2 — concatenate (no re-encode):**

```bash
ffmpeg -y -f concat -safe 0 -i unit_list.txt -c copy full_session_nosub.mp4
```

**Step 3 — embed SRT subtitle track:**

```bash
ffmpeg -y \
  -i full_session_nosub.mp4 \
  -i subtitles.srt \
  -c copy -c:s mov_text \
  -metadata:s:s:0 language=eng \
  full_session.mp4
```

`mov_text` is the subtitle codec for MP4 containers — selectable in VLC, QuickTime,
Windows Media Player via the "CC" button.

### Module API

```python
def assemble_session(
    session_dir: Path,           # video/<session>/
    audio_dir: Path,             # audio/<session>/tutorial_units/
    slide_timings: list[tuple[Path, float]],
    unit_mp3s: list[Path],
    srt_path: Path,
) -> Path:
    """Full pipeline: units → MP4s → full_session.mp4. Returns full_session.mp4."""

def _build_title_video(title_slide: Path, output: Path) -> Path:
def _build_unit_video(
    slides_with_dur: list[tuple[Path, float]],
    mp3: Path,
    output: Path,
) -> Path:
def _build_outro_video(outro_slide: Path, output: Path) -> Path:
def _concat_unit_videos(unit_mp4s: list[Path], output: Path) -> Path:
def _embed_subtitles(video: Path, srt: Path, output: Path) -> Path:
def _normalize_audio(video: Path, output: Path) -> Path:
def _write_concat_script(entries: list[tuple[Path, float]], script_path: Path) -> None:
def _run_ffmpeg(args: list[str]) -> None:
    """Run ffmpeg. Raises VideoError on non-zero exit. Streams stderr to log."""
```

### Progress output

Each step prints a progress line to stdout:

```
  [1/6] Generating title card video...
  [2/6] Rendering unit 1/4 — Interface vs Abstract Class...
  [3/6] Rendering unit 2/4 — Pass-by-Value...
  [4/6] Rendering unit 3/4 — String == vs .equals()...
  [5/6] Concatenating full session...
  [6/6] Embedding subtitles...
  ✓  video/week2_3/full_session.mp4  (127 MB, 26:42)
```

---

## Acceptance criteria

- [ ] SRT has correct sequential numbering and HH:MM:SS,mmm timestamps
- [ ] Subtitle lines max 60 chars (with `\n` wrap for longer)
- [ ] Beat timing: hook to first ALEX line, concept to first MAYA line
- [ ] Slide minimum duration 3.0 seconds enforced
- [ ] Per-unit MP4 is 1920×1080, H.264, AAC audio
- [ ] `-pix_fmt yuv420p` present in all encode commands
- [ ] Full session MP4 plays from start to end without stuttering
- [ ] Subtitle track selectable in VLC
- [ ] Output files written to `video/<session>/`, not `audio/<session>/`
- [ ] `full_session.mp4` < 500 MB for a 20-minute session
- [ ] No file in `tutor/visual/` exceeds 400 lines
- [ ] Progress printed per step

## Tests — `tutor/tests/visual/test_subtitle_writer.py`

- `test_srt_numbering_sequential`
- `test_timestamp_format_correct` — "00:01:23,456"
- `test_line_wrap_at_60_chars`
- `test_unit_scaling_when_duration_mismatch` — estimated vs actual differs 15% → scaled
- `test_get_line_start_offsets_matches_srt_timestamps`

## Tests — `tutor/tests/visual/test_beat_timer.py`

- `test_hook_slide_assigned_to_first_alex_line`
- `test_concept_slide_assigned_to_first_maya_line`
- `test_minimum_slide_duration_enforced`
- `test_title_card_fixed_4_seconds`
- `test_outro_card_fixed_6_seconds`

## Tests — `tutor/tests/visual/test_video_assembler.py`

- `test_concat_script_written_correctly`
- `test_ffmpeg_called_with_yuv420p`
- `test_slide_minimum_duration_enforced`
- `test_run_ffmpeg_raises_on_nonzero_exit`
- `test_output_paths_in_video_dir` — assert no paths point into audio/<session>/
