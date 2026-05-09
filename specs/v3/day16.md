# Day 16 — Pipeline Integration

## Goal

Wire the timing data (Day 13), segment plan (Day 14), and new slide renderers
(Day 15) into a single end-to-end pipeline. Rewrite `beat_timer.py` for
segment-based timing. Update `subtitle_writer.py` to use exact offsets when the
timing file is present. Update `tutor/visual/__init__.py` to orchestrate the v3
flow.

**Backward compatibility is a hard requirement.** Sessions generated before v3
(no `tutorial.timing.json`, no `tutorial.segments.json`) must still produce a
correct video. The v3 pipeline runs by default; it degrades gracefully to
proportional estimation when timing data is absent.

---

## Data boundary

```
Reads (new, optional):
  audio/<session>/tutorial.timing.json       ← from Day 13; absent for pre-v3 sessions
  video/<session>/tutorial.segments.json     ← from Day 14; generated on every /video run

Reads (unchanged):
  audio/<session>/tutorial.units.json
  audio/<session>/tutorial_units/unit_*.mp3
  video/<session>/slides/*.png               ← from Day 15

Writes (unchanged):
  video/<session>/subtitles.srt
  video/<session>/full_session.mp4
```

No LLM calls, no Pillow in `beat_timer.py` or `subtitle_writer.py`.

---

## Part A — Beat Timer (`tutor/visual/beat_timer.py`)

The v2 beat logic (hook/concept/memory detection by speaker pattern) is removed.
The new implementation maps each `SlideSegment` to an exact or proportional
duration.

**The v2 function `compute_slide_timings()` is kept** with its original signature —
it is called by `run_visual_pipeline()` only when no segment plan is available
(pre-v3 session fallback). New code must not break it.

### New public function

```python
def compute_slide_timings_v3(
    title_path:       Path,
    outro_path:       Path,
    segments_by_unit: dict[int, list[SlideSegment]],
    timing_json:      dict | None,
    unit_durations_s: list[float],
) -> list[tuple[Path, float]]:
    """
    Return [(png_path, duration_seconds), …] in video order, suitable for the
    ffmpeg concat script. Prepends title card and appends outro with fixed durations.

    Duration source:
      - timing_json present  → _exact_duration() for each segment
      - timing_json absent   → _proportional_duration() for each segment

    Minimum per-slide: MIN_SLIDE_DURATION (3.0 s).
    Title card: TITLE_DURATION (4.0 s). Outro: OUTRO_DURATION (6.0 s).
    """
```

### Private functions

```python
def _exact_duration(
    seg:         SlideSegment,
    unit_timing: list[dict],  # list of TimingEntry dicts for this unit
) -> float:
    """
    Look up timing entries for lines_start and lines_end in unit_timing.
    Return max(end_ms - start_ms, MIN_SLIDE_DURATION * 1000) / 1000.
    If either entry is missing: fall back to _proportional_duration().
    """

def _proportional_duration(
    seg:              SlideSegment,
    unit_duration_s:  float,
    total_lines:      int,
) -> float:
    """
    Segment covers (lines_end - lines_start + 1) / total_lines of unit duration.
    Return max(computed, MIN_SLIDE_DURATION).
    """
```

### Constants

```python
MIN_SLIDE_DURATION = 3.0    # seconds
TITLE_DURATION     = 4.0    # seconds — fixed regardless of timing data
OUTRO_DURATION     = 6.0    # seconds — fixed regardless of timing data
```

### File size

`beat_timer.py` is currently ~120 lines. After this rewrite: approximately
150 lines — well under 400.

---

## Part B — Subtitle Writer (`tutor/visual/subtitle_writer.py`)

Two functions gain an optional `timing_json` parameter. Default is `None`
(preserves v2 behaviour exactly).

### Updated signatures

```python
def build_srt(
    all_lines:        list[DialogueLine],
    unit_durations_s: list[float],
    timing_json:      dict | None = None,
) -> str:
    """
    Build the SRT string for the full session.
    If timing_json provided: use exact start_ms/end_ms per line for timestamps.
    If timing_json is None: use WPM estimation (existing behaviour).
    """

def get_line_start_offsets(
    all_lines:        list[DialogueLine],
    unit_durations_s: list[float],
    timing_json:      dict | None = None,
) -> list[float]:
    """
    Return session-global start offset in seconds for each line in all_lines.
    If timing_json provided: use exact offsets.
    If timing_json is None: use WPM estimation (existing behaviour).
    """
```

### New private function

```python
def _exact_line_offsets(
    all_lines:        list[DialogueLine],
    unit_durations_s: list[float],
    timing_json:      dict,
) -> list[float]:
    """
    Compute session-global start time for each line using timing_json.

    Algorithm:
      1. Compute unit_start[u] = sum of unit_durations_s[0..u-1] for each unit u.
         (Unit_start includes inter-unit silence gaps, consistent with how the
          ffmpeg concat script works.)
      2. For each line in all_lines, look up its entry in timing_json["units"][str(unit_num)].
         session_start = unit_start[unit_num] + entry["start_ms"] / 1000
      3. Lines with no entry (intro/outro) fall back to WPM estimation.
    """
```

**Important:** inter-unit silence (`SILENCE_UNIT_MS`) is NOT included in
`unit_durations_s` — that list contains only the MP3 play duration. The assembly
adds silence between units. To keep subtitles aligned with the concatenated video,
`_exact_line_offsets()` must add the same inter-unit gaps:

```python
unit_start = 0.0
for unit_num in sorted_unit_nums:
    # ... process unit lines ...
    unit_start += unit_durations_s[unit_idx] + SILENCE_UNIT_MS / 1000
```

### File size

`subtitle_writer.py` is currently ~110 lines. After these additions: approximately
140 lines — under 400.

---

## Part C — Pipeline integration (`tutor/visual/__init__.py`)

`run_visual_pipeline()` is updated to run the v3 flow. The v3 flow always attempts
to use segment-based slides; timing.json presence only affects timing precision.

### New helper

```python
def _load_timing_json(audio_dir: Path) -> dict | None:
    """
    Load tutorial.timing.json. Returns None if the file is absent,
    unreadable, or has version != 1.
    """
    path = audio_dir / "tutorial.timing.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if data.get("version") == 1 else None
    except Exception:
        log.warning("Could not parse tutorial.timing.json — using estimated timing")
        return None
```

### Updated `run_visual_pipeline()`

```python
def run_visual_pipeline(
    session:   str,
    audio_dir: Path,
    video_dir: Path,
    llm_fn:    Callable,
    difficulty: str = "beginner",
    no_cache:  bool = False,
) -> Path:
    from tutor.generation.visual_planner   import plan_visuals
    from tutor.generation.segment_planner  import plan_segments
    from tutor.visual.slide_compositor     import compose_all_v3
    from tutor.visual.subtitle_writer      import build_srt, get_line_start_offsets
    from tutor.visual.beat_timer           import compute_slide_timings_v3
    from tutor.visual.video_assembler      import assemble_session

    units_json     = audio_dir / "tutorial.units.json"
    doc_title      = _doc_title_from_units(units_json)
    unit_mp3s      = _get_unit_mp3s(audio_dir)
    unit_durations = [_mp3_duration(mp3) for mp3 in unit_mp3s]
    slides_dir     = video_dir / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)

    print("\n  [1/6] Generating visual specs (title card + outro)...")
    visuals = plan_visuals(
        units_json, doc_title, session, llm_fn, difficulty, video_dir, no_cache
    )

    print("  [2/6] Planning dialogue segments...")
    segments_by_unit = plan_segments(units_json, video_dir, llm_fn, no_cache)

    print("  [3/6] Compositing slides...")
    title_spec = visuals[0]    # slide_type == "title_card"
    outro_spec  = visuals[-1]  # slide_type == "outro"
    slide_paths = compose_all_v3(
        title_spec, outro_spec, segments_by_unit, slides_dir, session
    )

    print("  [4/6] Building SRT subtitles...")
    timing_json  = _load_timing_json(audio_dir)
    all_lines    = _load_all_lines(units_json)
    srt_text     = build_srt(all_lines, unit_durations, timing_json)
    srt_path     = video_dir / "subtitles.srt"
    srt_path.write_text(srt_text, encoding="utf-8")

    print("  [5/6] Computing slide timings...")
    title_path = slide_paths[0]
    outro_path = slide_paths[-1]
    slide_timings = compute_slide_timings_v3(
        title_path, outro_path, segments_by_unit, timing_json, unit_durations
    )

    print("  [6/6] Assembling video...")
    result = assemble_session(
        video_dir, audio_dir / "tutorial_units", slide_timings, unit_mp3s, srt_path
    )
    total_s = sum(dur for _, dur in slide_timings)
    m, s = divmod(int(total_s), 60)
    print(f"\n  ✓  {result}  ({m}:{s:02d})")
    return result
```

### Private helper extracted

```python
def _get_unit_mp3s(audio_dir: Path) -> list[Path]:
    """
    Return unit MP3s matching ^unit_\d+$ (teaching units only, sorted).
    Extracted from inline code for reuse and testability.
    """
```

### File size

`__init__.py` is currently 186 lines. After v3 integration: approximately
230 lines — under 400.

---

## Integration contract

The six pipeline steps communicate only through files and in-memory return values:

| Step | Produces | Consumed by |
|---|---|---|
| 1. `plan_visuals()` | `VisualSpec` list (memory) + `tutorial.visuals.json` | Step 3 |
| 2. `plan_segments()` | `dict[int, list[SlideSegment]]` (memory) + `tutorial.segments.json` | Steps 3, 5 |
| 3. `compose_all_v3()` | PNG paths (memory) + `slides/*.png` (disk) | Step 5 |
| 4. `build_srt()` | `subtitles.srt` (disk) | Step 6 |
| 5. `compute_slide_timings_v3()` | `list[(Path, float)]` (memory) | Step 6 |
| 6. `assemble_session()` | `full_session.mp4` (disk) | user |

No step reaches back into a previous step's output files. Each step's interface
is its function signature.

---

## Backward compatibility matrix

| Session state | Timing precision | Slide count | Behaviour |
|---|---|---|---|
| v3 session (timing.json + segments.json) | Exact (±0 ms) | 8–15/unit | Full v3 |
| v3 session (no timing.json) | Proportional (±5–10 s) | 8–15/unit | v3 slides, v2 timing |
| Pre-v3 session (re-run `/video`) | Proportional (±5–10 s) | 8–15/unit | v3 slides generated fresh |

In all cases `/video` completes successfully. The user only needs to re-run
`/generate` to gain exact timing on an old session.

---

## Acceptance criteria

- [ ] New session: `tutorial.timing.json` used by `/video`; subtitle timestamps exact
- [ ] Pre-v3 session (no timing.json): `/video` completes without error
- [ ] Slide durations within ±100ms of actual audio when timing.json present
- [ ] SRT timestamps within ±100ms of audio when timing.json present
- [ ] Step counter prints `[1/6]` through `[6/6]` to stdout
- [ ] Final summary line prints path and duration `(M:SS)`
- [ ] `beat_timer.py` stays under 400 lines; v2 `compute_slide_timings()` callable
- [ ] `subtitle_writer.py` stays under 400 lines; v2 callers without timing_json unchanged
- [ ] `__init__.py` stays under 400 lines
- [ ] No step imports from another step's module (only via function arguments)

## Tests — `tutor/tests/visual/test_beat_timer.py`

Extend existing test file — do not replace it.

- `test_exact_duration_from_timing_json` — segment spanning 3240ms → 3.24s
- `test_proportional_fallback_when_timing_absent`
- `test_min_slide_duration_enforced` — 0.5s segment → clamped to 3.0s
- `test_title_duration_is_4_seconds`
- `test_outro_duration_is_6_seconds`
- `test_all_segments_present_in_output` — output count = 2 + sum of segment counts
- `test_v2_compute_slide_timings_still_callable` — regression guard

## Tests — `tutor/tests/visual/test_subtitle_writer.py`

Extend existing test file.

- `test_exact_offsets_from_timing_json` — line with known start_ms gets correct timestamp
- `test_fallback_offsets_when_timing_absent` — same result as v2 when timing_json=None
- `test_unit_start_offsets_cumulative` — unit 2 starts at unit_1_duration + SILENCE_UNIT_MS/1000
- `test_intro_lines_not_in_timing_json_get_estimated_offset`

## Tests — `tutor/tests/visual/test_pipeline_integration.py`

New test file.

- `test_run_visual_pipeline_v3_end_to_end` — mocked LLM + real Pillow + stub ffmpeg; asserts mp4 path returned
- `test_run_visual_pipeline_no_timing_json` — timing.json absent; pipeline completes
- `test_six_progress_steps_printed` — capture stdout; assert "[1/6]" through "[6/6]"
- `test_output_in_video_dir` — result path is under `video/<session>/`
