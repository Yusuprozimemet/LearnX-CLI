# Day 16 — Full Pipeline Integration

## Goal

Wire the timing data (Day 13), segment plan (Day 14), and HTML slide renderer
(Day 15) into a single end-to-end pipeline. Rewrite `beat_timer.py` to derive
slide durations from `SlideSegment` objects. Update `subtitle_writer.py` to use
exact offsets when the timing file is present. Update `tutor/visual/__init__.py`
to orchestrate the v3 6-step flow.

**Backward compatibility is a hard requirement.** Sessions generated before v3
(no `tutorial.timing.json`, no `tutorial.segments.json`) must still produce a
correct video by falling back to proportional estimation.

---

## Done (merge gate)

```powershell
py -m pytest tutor/tests/visual/ -v   # scoped — all green
py -m pytest                          # full suite — 0 failures
py -m ruff check tutor/               # 0 errors
py -m ruff format --check tutor/      # 0 formatting issues
```

Report: list each acceptance criterion below with pass/fail. Paste gate output.
Stop: do not merge to main — wait for human review.

---

## Data boundary

```
Reads (new, optional):
  audio/<session>/tutorial.timing.json       ← from Day 13; absent for pre-v3 sessions

Reads (always):
  audio/<session>/tutorial.units.json
  audio/<session>/tutorial_units/unit_*.mp3
  video/<session>/slides/*.png               ← from Day 15

Writes (unchanged):
  video/<session>/subtitles.srt
  video/<session>/full_session.mp4
```

No LLM calls, no Pillow calls in `beat_timer.py`, `subtitle_writer.py`, or
`__init__.py`.

---

## Part A — Beat Timer (`tutor/visual/beat_timer.py`)

The existing `compute_slide_timings()` takes
`(slides, script_lines, line_start_offsets, visuals, unit_durations_s)` —
the v2 signature. This function is renamed to `_compute_slide_timings_v2()`
(private) to preserve its logic for the regression test. A new public
`compute_slide_timings_v3()` replaces it for the v3 pipeline.

### Constants (add alongside existing)

```python
MIN_SLIDE_DURATION = 3.0   # seconds — already exists, keep unchanged
TITLE_DURATION     = 4.0   # seconds — already exists as TITLE_CARD_DURATION
OUTRO_DURATION     = 6.0   # seconds — already exists as OUTRO_CARD_DURATION
```

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
    Return [(png_path, duration_seconds), ...] in video order, ready for the
    ffmpeg concat script. Prepends title card (4.0 s) and appends outro (6.0 s).

    Duration source per segment:
      timing_json present  → _exact_duration()
      timing_json absent   → _proportional_duration()

    Minimum per-segment: MIN_SLIDE_DURATION (3.0 s).
    """
```

### Private helpers

```python
def _exact_duration(
    seg:         SlideSegment,
    unit_timing: list[dict],   # list of TimingEntry dicts for this unit
) -> float:
    """
    Look up timing entries for lines_start and lines_end in unit_timing.
    start_ms = unit_timing[seg.lines_start]["start_ms"]
    end_ms   = unit_timing[seg.lines_end]["end_ms"]
    Return max((end_ms - start_ms) / 1000.0, MIN_SLIDE_DURATION).
    If either entry index is missing: fall back to _proportional_duration().
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

### Renamed private function (regression guard)

```python
def _compute_slide_timings_v2(
    slides: list[Path],
    script_lines: list[DialogueLine],
    line_start_offsets: list[float],
    visuals: list[VisualSpec],
    unit_durations_s: list[float],
) -> list[tuple[Path, float]]:
    # identical to the current compute_slide_timings() body — no logic changes
    ...
```

### File size

`beat_timer.py` is currently ~152 lines. After this change: approximately
200 lines — under 400.

---

## Part B — Subtitle Writer (`tutor/visual/subtitle_writer.py`)

Two public functions gain an optional `timing_json` parameter. Default is `None`,
which preserves v2 behaviour exactly — no callers break.

### Updated signatures

```python
def build_srt(
    all_lines:        list[DialogueLine],
    unit_durations_s: list[float],
    timing_json:      dict | None = None,
) -> str:
    """
    Build the SRT string for the full session.
    If timing_json provided: use exact start_ms/end_ms per line.
    If timing_json is None: use WPM estimation (existing behaviour, unchanged).
    """

def get_line_start_offsets(
    all_lines:        list[DialogueLine],
    unit_durations_s: list[float],
    timing_json:      dict | None = None,
) -> list[float]:
    """
    Return session-global start offset in seconds for each line in all_lines.
    If timing_json provided: use exact offsets.
    If timing_json is None: use WPM estimation (existing behaviour, unchanged).
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
      1. Build unit_start[u] = sum of (unit_durations_s[u-1] + SILENCE_UNIT_MS/1000)
         for units before u. Include the inter-unit silence in the cumulative cursor
         so subtitle timestamps align with the concatenated video.
      2. For each line in all_lines, look up timing_json["units"][str(unit_num)].
         session_start = unit_start[unit_num] + entry["start_ms"] / 1000
      3. Lines not in timing_json (intro, outro) fall back to WPM estimation.
    """
```

**Key:** `timing_json["units"]` keys are plain string integers (`"1"`, `"2"`, …)
matching Day 13's output format.

### File size

`subtitle_writer.py` is currently ~130 lines. After additions: approximately
170 lines — under 400.

---

## Part C — Pipeline orchestration (`tutor/visual/__init__.py`)

`run_visual_pipeline()` is updated to the v3 6-step flow. The function signature
is unchanged so all existing callers (`/video` command, tests) continue to work.

### New private helper

```python
def _load_timing_json(audio_dir: Path) -> dict | None:
    """
    Load tutorial.timing.json. Returns None if absent, unreadable, or version != 1.
    Logs a warning on parse failure; does not raise.
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
    session:    str,
    audio_dir:  Path,
    video_dir:  Path,
    llm_fn:     Callable,
    difficulty: str  = "beginner",
    no_cache:   bool = False,
) -> Path:
    from tutor.generation.visual_planner  import plan_visuals
    from tutor.generation.segment_planner import plan_segments
    from tutor.visual.slide_renderer      import render_all_slides
    from tutor.visual.subtitle_writer     import build_srt
    from tutor.visual.beat_timer          import compute_slide_timings_v3
    from tutor.visual.video_assembler     import assemble_session

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

    print("  [3/6] Rendering slides...")
    title_spec = next(v for v in visuals if v.slide_type == "title_card")
    outro_spec  = next(v for v in visuals if v.slide_type == "outro")
    slide_paths = render_all_slides(
        title_spec, outro_spec, segments_by_unit, slides_dir, session
    )

    print("  [4/6] Building SRT subtitles...")
    timing_json = _load_timing_json(audio_dir)
    all_lines   = _load_all_lines(units_json)
    srt_text    = build_srt(all_lines, unit_durations, timing_json)
    srt_path    = video_dir / "subtitles.srt"
    srt_path.write_text(srt_text, encoding="utf-8")

    print("  [5/6] Computing slide timings...")
    title_path = slide_paths[0]
    outro_path = slide_paths[-1]
    slide_timings = compute_slide_timings_v3(
        title_path, outro_path, segments_by_unit, timing_json, unit_durations
    )

    print("  [6/6] Assembling video...")
    result  = assemble_session(
        video_dir, audio_dir / "tutorial_units", slide_timings, unit_mp3s, srt_path
    )
    total_s = sum(dur for _, dur in slide_timings)
    m, s    = divmod(int(total_s), 60)
    print(f"\n  ✓  {result}  ({m}:{s:02d})")
    return result
```

### Private helper extracted

```python
def _get_unit_mp3s(audio_dir: Path) -> list[Path]:
    """
    Return unit MP3s matching the pattern unit_NN.mp3 (teaching units, sorted).
    Excludes unit_00_intro and unit_99_outro.
    Extracted for reuse and testability.
    """
```

### File size

`__init__.py` is currently ~186 lines. After v3 integration: approximately
240 lines — under 400.

---

## Backward compatibility matrix

| Session state | Timing precision | Slide count | Outcome |
|---|---|---|---|
| v3 session (timing.json present) | Exact (±0 ms) | 8–15/unit | Full v3 |
| v3 session (no timing.json) | Proportional (±5–10 s) | 8–15/unit | v3 slides, v2 timing |
| Pre-v3 session (re-run `/video`) | Proportional | 8–15/unit | New segments generated; v2 timing |

In all cases `/video` completes successfully.

---

## Acceptance criteria

- [ ] Step counter prints `[1/6]` through `[6/6]` to stdout in order
- [ ] Final summary line prints path and duration `(M:SS)` format
- [ ] New session with timing.json: subtitle timestamps within ±100 ms of audio
- [ ] Pre-v3 session (no timing.json): `/video` completes without error or exception
- [ ] `_load_timing_json()` returns `None` for absent file, corrupt JSON, and `version != 1`
- [ ] `beat_timer.py` stays under 400 lines; `_compute_slide_timings_v2()` callable (regression)
- [ ] `subtitle_writer.py` stays under 400 lines; v2 callers without `timing_json` unchanged
- [ ] `__init__.py` stays under 400 lines
- [ ] `timing_json["units"]` keys read as plain string integers (`"1"`, `"2"`, …)
- [ ] Inter-unit silence (`SILENCE_UNIT_MS`) included in cumulative offset for subtitles

---

## Tests — `tutor/tests/visual/test_beat_timer.py`

Extend the existing test file — do not replace it.

- `test_exact_duration_from_timing_json` — segment spanning 3240 ms → 3.24 s
- `test_exact_duration_uses_lines_start_and_end` — segment covering lines 2–4 reads correct entries
- `test_proportional_fallback_when_timing_absent` — `timing_json=None` → proportional result
- `test_min_slide_duration_enforced` — 0.5 s segment → clamped to 3.0 s
- `test_title_duration_is_4_seconds`
- `test_outro_duration_is_6_seconds`
- `test_all_segments_present_in_output` — output count = 2 + sum of segment counts
- `test_v2_function_still_callable` — call `_compute_slide_timings_v2()` with stub args; assert no exception

## Tests — `tutor/tests/visual/test_subtitle_writer.py`

Extend the existing test file.

- `test_exact_offsets_from_timing_json` — line with known `start_ms` gets correct timestamp
- `test_fallback_when_timing_absent` — `timing_json=None` → same result as v2
- `test_inter_unit_silence_included` — unit 2 start = unit_1_duration + SILENCE_UNIT_MS/1000
- `test_intro_lines_fall_back_to_estimation` — lines with `unit_number=0` not in timing_json get estimated offset

## Tests — `tutor/tests/visual/test_pipeline_integration.py`

New test file. Uses mocked LLM, stub Playwright (or `@pytest.mark.slow`), stub ffmpeg.

- `test_run_visual_pipeline_six_steps_printed` — capture stdout; assert `[1/6]` through `[6/6]`
- `test_run_visual_pipeline_no_timing_json` — timing.json absent; pipeline completes without error
- `test_load_timing_json_returns_none_for_absent_file`
- `test_load_timing_json_returns_none_for_wrong_version` — `version: 2` → `None`
- `test_load_timing_json_returns_none_for_corrupt_json`
- `test_output_path_is_under_video_dir` — result path starts with `video/<session>/` `@slow`
