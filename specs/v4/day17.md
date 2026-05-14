# Day 17 — Video Pipeline Bug Fixes (P1 + P2 + P3)

## Goal

Three bugs identified at the end of v3 work have never been fixed.
This day resolves all three so that `/generate week3/1.md` followed by `/video`
produces a watchable MP4 with audible voice and correctly timed dark-themed slides.

| Bug | File | Symptom |
|-----|------|---------|
| P2 — timing inflation | `tutor/visual/beat_timer.py` | Slide durations over-counted by `(n_lines-1) × SILENCE_TURN_MS` per segment |
| P1 — silent audio after concat | `tutor/visual/video_assembler.py` | Audio stream present in ffprobe but voice not heard during playback |
| P3 — slides unverified | acceptance test | Dark-themed slides never confirmed after the CSS `page.goto()` fix in day16 extra |

---

## Done (merge gate)

```powershell
py -m pytest tutor/tests/visual/ -v
py -m pytest tutor/tests/ --ignore=tutor/tests/e2e/ -m "not slow" -v
py -m ruff check tutor/
py -m ruff format --check tutor/

# Manual acceptance test — run after gate is green
python -m tutor generate week3/1.md --output audio/week3_1
python -m tutor video week3_1
# Then verify:
#   1. Open video/week3_1/full_session.mp4 in VLC — voice must be audible
#   2. Open any PNG in video/week3_1/slides/ — dark background, readable text
#   3. ffprobe -show_streams video/week3_1/full_session.mp4 — audio bit_rate > 0
```

Report: paste gate output. List each acceptance criterion.
Stop: do not merge — wait for human review.

---

## Data boundary

```
Modifies (existing):
  tutor/visual/beat_timer.py          ← fix _exact_duration() (P2)
  tutor/visual/video_assembler.py     ← fix _concat_unit_videos() (P1)
  tutor/tests/visual/test_beat_timer.py         ← add 2 tests for P2 fix
  tutor/tests/visual/test_video_assembler.py    ← add 1 test for P1 fix

Does NOT touch:
  tutor/audio/            ← audio pipeline unchanged
  tutor/generation/       ← LLM pipeline unchanged
  tutor/visual/slide_renderer.py      ← renderer unchanged
  week3/                  ← test fixture, read-only
```

---

## Fix P2 — Timing inflation in `_exact_duration` (`beat_timer.py`)

### Root cause

```python
# Current code — WRONG: over-counts by (n_lines - 1) × SILENCE_TURN_MS
adjusted_ms = (end_ms - start_ms) + n_lines * SILENCE_TURN_MS
```

The raw span `end_ms - start_ms` already includes `(n_lines - 1)` inter-line
silences — they are captured between each `end_ms[i]` and `start_ms[i+1]` in
`timing.json`. Only one trailing silence (after the last line of the segment)
is missing from the raw span.

### Fix (one line)

```python
# Correct — only trailing silence is missing from the raw timing span
adjusted_ms = (end_ms - start_ms) + SILENCE_TURN_MS
```

Location: `tutor/visual/beat_timer.py`, function `_exact_duration()`.

### New tests — add to `tutor/tests/visual/test_beat_timer.py`

```python
def test_exact_duration_single_line_adds_one_turn_silence():
    """Single line: duration = (end - start) + 1 × SILENCE_TURN_MS."""
    seg = SlideSegment(unit_index=1, segment_index=0, lines_start=0, lines_end=0, ...)
    unit_timing = [{"start_ms": 0, "end_ms": 2000}]
    dur = _exact_duration(seg, unit_timing)
    expected_ms = (2000 - 0) + SILENCE_TURN_MS
    assert abs(dur - expected_ms / 1000.0) < 0.001


def test_exact_duration_multi_line_still_adds_one_turn_silence():
    """5-line segment: only 1 trailing silence added, not 5."""
    seg = SlideSegment(unit_index=1, segment_index=0, lines_start=0, lines_end=4, ...)
    unit_timing = [
        {"start_ms": 0,    "end_ms": 1000},
        {"start_ms": 1500, "end_ms": 2500},
        {"start_ms": 3000, "end_ms": 4000},
        {"start_ms": 4500, "end_ms": 5500},
        {"start_ms": 6000, "end_ms": 7000},
    ]
    dur = _exact_duration(seg, unit_timing)
    expected_ms = (7000 - 0) + SILENCE_TURN_MS   # raw span + 1 trailing silence
    assert abs(dur - expected_ms / 1000.0) < 0.001
```

---

## Fix P1 — Silent audio after concat (`video_assembler.py`)

### Root cause

`_concat_unit_videos` uses `-c copy` which copies the AAC bitstream without
re-encoding. When the title and outro unit MP4s (which contain a silent
`anullsrc` audio stream) are concatenated with real-audio unit MP4s, timestamp
discontinuities can cause players to lose the audio track or present silence.

`-c copy` is safe only when all input streams share identical codec parameters
and continuous timestamps. After mixing `anullsrc`-sourced silent audio with
real TTS audio, timestamps are not continuous.

### Fix

Re-encode audio during concat. Replace the single `-c copy` flag with explicit
codec flags:

```python
# Before
"-c", "copy",

# After
"-c:v", "copy",
"-c:a", "aac",
"-b:a", AUDIO_BITRATE,
"-ar", "44100",
"-ac", "2",
```

This re-encodes only the audio (video is still copied) which normalises
timestamps and codec parameters across the concatenated stream.

Location: `tutor/visual/video_assembler.py`, function `_concat_unit_videos()`.

### New test — add to `tutor/tests/visual/test_video_assembler.py`

```python
def test_concat_unit_videos_re_encodes_audio(tmp_path):
    """_concat_unit_videos must NOT use bare -c copy — audio must be re-encoded."""
    import inspect
    from tutor.visual.video_assembler import _concat_unit_videos
    src = inspect.getsource(_concat_unit_videos)
    # Bare "-c", "copy" would copy audio without re-encoding
    assert '"-c", "copy"' not in src, (
        "_concat_unit_videos must re-encode audio (use -c:v copy + -c:a aac), "
        "not bare -c copy, to fix timestamp discontinuities after concat"
    )
    assert '"-c:a", "aac"' in src
```

---

## Acceptance criteria

- [ ] `_exact_duration` uses `+ SILENCE_TURN_MS` (not `+ n_lines * SILENCE_TURN_MS`)
- [ ] `test_exact_duration_single_line_adds_one_turn_silence` passes
- [ ] `test_exact_duration_multi_line_still_adds_one_turn_silence` passes — confirms no per-line multiplication
- [ ] `_concat_unit_videos` uses `-c:v copy` + `-c:a aac` instead of bare `-c copy`
- [ ] `test_concat_unit_videos_re_encodes_audio` passes
- [ ] Full pytest suite green (excluding slow and e2e)
- [ ] ruff clean
- [ ] **Manual:** `python -m tutor generate week3/1.md` completes without error
- [ ] **Manual:** `python -m tutor video week3_1` completes without error
- [ ] **Manual:** `full_session.mp4` plays with audible voice in VLC
- [ ] **Manual:** slide PNGs show dark background with readable text (P3 verified)
- [ ] **Manual:** `ffprobe -show_streams full_session.mp4` shows audio `bit_rate > 0`
