# Day 13 — Exact Timing Capture

## Goal

During audio assembly, record the exact millisecond start and end offset of every
dialogue line and write it to `tutorial.timing.json` in the audio session directory.
This gives every downstream step — subtitle writer, beat timer, slide sequencer —
deterministic, zero-estimation timestamps for every spoken line.

**No new dependencies.** The information already exists inside
`audio_builder._concat_with_silence()`: pydub's `len(AudioSegment)` returns the
exact duration in milliseconds, and the silence constants are fixed values.

The `build()` public API is unchanged. All modifications are internal.

---

## Data boundary

```
Writes (new):
  audio/<session>/tutorial.timing.json   ← written once during /generate

Reads (unchanged by this module):
  audio/<session>/tutorial_units/*.mp3
  audio/<session>/tutorial.mp3
```

`tutorial.timing.json` is written by the audio pipeline and read by the video
pipeline. It is never modified after `/generate` completes.

---

## New model — `tutor/models.py`

Add `TimingEntry` alongside the existing dataclasses. No existing models are changed.

```python
@dataclass
class TimingEntry:
    line_index: int    # 0-based within the unit (matches SlideSegment.lines_start/end)
    speaker:    str    # "ALEX" | "MAYA" | "SAM"
    text:       str    # dialogue line text — for cross-referencing only
    start_ms:   int    # offset from unit MP3 start, in milliseconds
    end_ms:     int    # exclusive end; end_ms - start_ms == len(audio) in ms
```

---

## `tutorial.timing.json` — format

```json
{
  "version": 1,
  "units": {
    "1": [
      {"line_index": 0, "speaker": "ALEX", "text": "What's the main difference...", "start_ms": 0,    "end_ms": 3240},
      {"line_index": 1, "speaker": "ALEX", "text": "Think of it this way...",        "start_ms": 3740, "end_ms": 7180},
      {"line_index": 2, "speaker": "MAYA", "text": "So an interface is like...",     "start_ms": 7680, "end_ms": 9520}
    ],
    "2": [...]
  }
}
```

**Rules:**
- Keys in `"units"` are unit numbers as strings (`"1"`, `"2"`, ...).
- Unit 0 (intro) and unit -1 (outro) are excluded — the video pipeline processes
  teaching units only.
- Offsets are **relative to each unit's MP3**, not the full-session audio. This
  matches how the video assembler processes units independently.
- `start_ms` of line N equals `end_ms` of line N-1 + silence gap. There are no
  overlaps; every millisecond in the unit MP3 is accounted for.
- `end_ms - start_ms` equals exactly `len(AudioSegment.from_mp3(seg.audio_path))`.

---

## Changes to `tutor/audio/audio_builder.py`

### `_concat_with_silence()` — capture timing alongside audio

**Current signature:**
```python
def _concat_with_silence(segments: list[RenderedSegment]) -> AudioSegment:
```

**New signature:**
```python
def _concat_with_silence(
    segments: list[RenderedSegment],
    capture_timing: bool = False,
) -> tuple[AudioSegment, list[TimingEntry]]:
```

When `capture_timing=False` (default), the second return value is an empty list —
zero overhead for intro/outro processing.

**Full algorithm:**
```python
def _concat_with_silence(segments, capture_timing=False):
    result      = AudioSegment.empty()
    entries: list[TimingEntry] = []
    cursor_ms   = 0
    prev_speaker: str | None = None

    for idx, seg in enumerate(segments):
        audio = AudioSegment.from_mp3(seg.audio_path)

        if prev_speaker is None:
            gap = 0
        elif prev_speaker == seg.line.speaker:
            gap = SILENCE_BREATH_MS
        else:
            gap = SILENCE_TURN_MS

        if gap:
            result    += AudioSegment.silent(duration=gap)
            cursor_ms += gap

        if capture_timing:
            entries.append(TimingEntry(
                line_index=idx,
                speaker=seg.line.speaker,
                text=seg.line.text,
                start_ms=cursor_ms,
                end_ms=cursor_ms + len(audio),
            ))

        result    += audio
        cursor_ms += len(audio)
        prev_speaker = seg.line.speaker

    return result, entries
```

### `_assemble()` — collect and write timing

Calls `_concat_with_silence(group, capture_timing=True)` for teaching units
(`unit_num >= 1`). Collects results into a dict keyed by unit number string,
then writes `tutorial.timing.json` before exporting full audio.

```python
def _assemble(segments, out_path, units_dir):
    unit_groups  = ...          # same grouping logic as before
    sorted_keys  = ...          # same sort order as before

    unit_timing: dict[str, list] = {}
    unit_audio:  list[AudioSegment] = []

    for unit_num in sorted_keys:
        group             = unit_groups[unit_num]
        is_teaching_unit  = unit_num >= 1
        combined, entries = _concat_with_silence(group, capture_timing=is_teaching_unit)

        if is_teaching_unit and entries:
            unit_timing[str(unit_num)] = [asdict(e) for e in entries]

        unit_label = (
            "unit_00_intro" if unit_num == 0
            else "unit_99_outro" if unit_num == -1
            else f"unit_{unit_num:02d}"
        )
        unit_path = str(Path(units_dir) / f"{unit_label}.mp3")
        combined.export(unit_path, format="mp3")
        log.info("Saved unit: %s", unit_path)

        unit_audio.append(combined)
        if unit_num != -1:
            unit_audio.append(AudioSegment.silent(duration=SILENCE_UNIT_MS))

    timing_path = Path(out_path).parent / "tutorial.timing.json"
    timing_path.write_text(
        json.dumps({"version": 1, "units": unit_timing}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info("Timing file written: %s (%d units)", timing_path, len(unit_timing))

    full_audio = sum(unit_audio, AudioSegment.empty())
    full_audio.export(out_path, format="mp3")
```

### New imports required in `audio_builder.py`

```python
import json
from dataclasses import asdict
from tutor.models import DialogueLine, RenderedSegment, TimingEntry
```

### File size

`audio_builder.py` is currently 105 lines. After this change: approximately
140 lines — well under the 400-line limit.

---

## Backward compatibility

- `build()` signature is unchanged. All existing callers compile without modification.
- Sessions generated before v3 have no `tutorial.timing.json`. The video pipeline
  checks for its presence before using it; absence triggers proportional fallback.
- Re-running `/generate` on an existing session overwrites the timing file.

---

## Acceptance criteria

- [ ] `tutorial.timing.json` written to `audio/<session>/` on every `/generate` run
- [ ] Teaching units 1..N present in `"units"` dict; unit 0 and -1 excluded
- [ ] `start_ms` of each entry equals previous `end_ms` + silence gap (no gaps, no overlaps)
- [ ] `end_ms - start_ms` equals `len(AudioSegment.from_mp3(seg.audio_path))`
- [ ] Silence gaps between turns match `SILENCE_TURN_MS`; same-speaker gaps match `SILENCE_BREATH_MS`
- [ ] JSON is valid UTF-8 with `"version": 1` at top level
- [ ] `audio_builder.py` stays under 400 lines
- [ ] All existing `build()` callers run without modification
- [ ] Timing file is not written if audio assembly raises an exception

## Tests — `tutor/tests/audio/test_audio_builder.py`

Extend the existing test file — do not create a new one.

- `test_timing_file_written_after_build` — assert `tutorial.timing.json` exists
- `test_timing_keys_match_teaching_units` — keys "1".."N" present; "0" and "-1" absent
- `test_timing_offsets_no_gaps_no_overlaps` — for each unit: entry[i].end_ms + gap == entry[i+1].start_ms
- `test_timing_duration_matches_pydub_len` — end_ms - start_ms equals actual pydub audio len
- `test_timing_version_field_is_1`
- `test_intro_excluded_from_timing` — unit 0 not a key
- `test_outro_excluded_from_timing` — unit -1 not a key
