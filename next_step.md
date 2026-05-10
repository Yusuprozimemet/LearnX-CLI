# Next Steps — LearnX v3 Status

## What We Have Done

### Day 13 — Exact Timing Capture
- Added `TimingEntry` dataclass to `tutor/models.py`
- Modified `_concat_with_silence()` in `tutor/audio/audio_builder.py` to record per-line
  `start_ms` / `end_ms` during TTS concatenation
- `_assemble()` writes `tutorial.timing.json` alongside the unit MP3s
- Keys are plain string integers (`"1"`, `"2"`, …) matching unit numbers

### Day 14 — Dialogue-Aware Visual Segment Planner
- New file: `tutor/generation/segment_planner.py`
- LLM assigns each dialogue line range to a visual type (key_insight, analogy, diagram, …)
- Writes `tutorial.segments.json`; caches per unit via MD5 hash of dialogue text
- `_fill_gaps()` ensures every line is covered by exactly one segment
- `_fallback_segments()` produces valid output without LLM on any error

### Day 15 — HTML Slide Renderer (Playwright + Jinja2)
- Deleted Pillow-based compositor; replaced with `tutor/visual/slide_renderer.py`
- Templates in `tutor/visual/templates/` (11 visual types + title_card + outro)
- CSS in `tutor/assets/html/slide_base.css` (dark theme, 1920 × 1080)
- JS stubs for highlight.js and mermaid
- Renders via headless Chromium (Playwright)

### Day 16 — Full Pipeline Integration
- `tutor/visual/__init__.py` rewritten as `run_visual_pipeline()` — 6-step pipeline:
  1. Plan visuals (title card + outro)
  2. Plan dialogue segments
  3. Render slides (Playwright)
  4. Build SRT subtitles
  5. Compute slide timings (v3 — exact from timing.json, proportional fallback)
  6. Assemble MP4 (per-unit videos concatenated)
- `beat_timer.py`: added `compute_slide_timings_v3()` and `_exact_duration()`
- `subtitle_writer.py`: added `timing_json` param for exact per-line offsets

### Day 16 Extra — Bug Fixes (current branch: `sandbox/day16`)
- **CSS loading**: `page.set_content()` → `page.goto("file:///tmp.html")` so Chromium
  can load CSS/JS from a `file://` origin (set_content gives null/opaque origin)
- **Fonts**: removed invalid 48-byte WOFF2 stubs; CSS now uses system font stack
  (`Segoe UI` / `Cascadia Code` / `Consolas`)
- **Template None rendering**: added `| default('')` and `{% if %}` guards in
  `analogy`, `comparison`, `decision_guide`, `diagram` templates
- **Timing gaps**: `_exact_duration()` adds `n_lines × SILENCE_TURN_MS` to account
  for inter-line silence baked into MP3 that was not counted per segment
- **`_load_unit_lines` fallback**: production `tutorial.units.json` has no `lines` field
  (only test fixtures do); added fallback to parse `tutorial.script.txt` using
  `tutorial.timing.json` line counts for accurate per-unit distribution

---

## Where We Stopped

- Branch: `sandbox/day16` — committed, not yet pushed or merged to `main`
- The full pipeline runs end-to-end: `/generate week2/2.md` → `/video week2_2`
  produces a ~7 MB, 8:12 MP4 with 4 unit slide stacks
- The CSS/font/None fixes were committed but the video has **not been regenerated yet**
  to verify the dark-themed slides visually
- The audio issue (no audible voice) is diagnosed but not resolved — see below

---

## Known Problems — To Fix

### P1 — No Audible Voice in Video (CRITICAL)
**Symptom:** The final MP4 has an AAC audio stream (confirmed by ffprobe: 116 kbps,
504 s), and the individual unit MP3 files contain real TTS speech. But the voice is
not heard during playback.

**What we know:**
- Total unit MP3 duration ≈ 495 s (unit_01: 68 s, unit_02: 147 s, unit_03: 142 s,
  unit_04: 138 s) — matches video length
- `_build_unit_video()` maps MP3 as `1:a:0` with `-af volume=5dB` and `-shortest`
- `_concat_unit_videos()` uses `-c copy` (no re-encode)
- `_embed_subtitles()` uses `-c copy`

**Possible causes (not yet investigated):**
1. The `-shortest` flag clips the unit video to the shorter of slides vs MP3. If the
   slide timings (now inflated by `n_lines × SILENCE_TURN_MS`) are much longer than
   the MP3, the MP3 is the shorter stream — which is correct, audio should play fully.
   But if the timing inflation makes some unit's slide total shorter than its MP3, the
   audio tail gets cut. Verify by comparing slide timing sums vs MP3 durations per unit.
2. The `ffconcat version 1.0` format used in `_write_concat_script` may interact with
   `-shortest` in an unexpected way — ffmpeg may stop video at the last `duration`
   entry and the audio can become desynchronised after `_concat_unit_videos`.
3. Codec/player issue: test with VLC. Windows Media Player can fail to play AAC audio
   in MP4 on some Windows 10 builds without a codec pack.
4. The `anullsrc` silent audio in title/outro MP4s may not match sample rate or channel
   layout of the unit MP4s, causing silent stream to override after concat.

**First steps:**
- Play `audio/week2_2/tutorial_units/unit_01.mp3` directly — confirm voice is there
- Open `video/week2_2/full_session.mp4` in VLC — check if VLC plays audio
- Run `ffprobe -show_streams` on `unit_01.mp4` (before concat) to verify audio stream

### P2 — Slide Timing Inflation May Be Over-Counted (MEDIUM)
**Problem:** `_exact_duration()` adds `n_lines × SILENCE_TURN_MS`. But the raw span
`end_ms[last] - start_ms[first]` already includes `(n_lines - 1)` inter-line silences
(they are captured between `end_ms[i]` and `start_ms[i+1]`). Only 1 trailing silence
(after the last line of the segment) is truly missing from the raw span.

**Effect:** Each segment's duration is inflated by `(n_lines - 1) × SILENCE_TURN_MS`
too much. For a 5-line segment that is 4 × 500 ms = 2 s of over-count. Across many
segments this may cause total slide duration >> MP3 duration.

**Fix (one line in `beat_timer._exact_duration`):**
```python
# Current (over-counts):
adjusted_ms = (end_ms - start_ms) + n_lines * SILENCE_TURN_MS

# Correct (only trailing silence is missing):
adjusted_ms = (end_ms - start_ms) + SILENCE_TURN_MS
```
Requires verifying what `start_ms` / `end_ms` actually represent in `timing.json`
(read `audio_builder._concat_with_silence` to confirm).

### P3 — Slides Not Visually Verified After CSS Fix (MEDIUM)
The `page.goto()` fix was committed but the video has not been regenerated.
Re-run `/video week2_2` (with `--no-cache` to force slide re-render) and open the
output PNGs in `video/week2_2/slides/` to confirm dark background and correct layout.

### P4 — `sandbox/day16` Not Merged to `main` (BLOCKER for Day 17+)
All v3 work lives on `sandbox/day16`. Until it is reviewed and merged, no new spec
day can start (per project rules: never branch sandbox/dayN off another sandbox branch).

---

## What To Do Next (In Order)

1. **Push `sandbox/day16`** to GitHub and open a PR against `main`
2. **Verify audio** — play unit MP3s directly, then test video in VLC; if VLC works,
   the issue is a Windows codec pack; if VLC is also silent, investigate ffmpeg mapping
3. **Fix timing inflation** (P2) — read `audio_builder.py` timing logic, then correct
   `_exact_duration()` to add only 1 × SILENCE_TURN_MS regardless of line count
4. **Regenerate video** after fixes to visually confirm dark slides and working audio
5. **Merge `sandbox/day16`** to `main` after review
6. **Day 17** — write and implement any remaining polish once main is clean
