# E2E Smoke Tests

## What These Tests Verify

The unit test suite mocks all LLM and audio calls. These smoke tests run the **real
pipeline** on a small committed fixture and assert on actual output files. They exist
because several bugs passed all unit tests but were caught here:

| Bug | Caught by |
|-----|-----------|
| Silent audio in output video (loudnorm / encoding bug) | `test_audio_stream_present`, `test_audio_not_silent` |
| Blank slides / CSS not loaded | `test_slide_page_not_blank`, `test_slide_has_visible_text` |
| Pipeline crash on real markdown input | `test_pipeline_exits_zero` |
| A/V timing drift (estimation instead of actual) | `test_timing_end_matches_audio_duration` |
| Video file has no audio stream | `test_audio_stream_present` |

## How to Run

```powershell
# Windows (PowerShell)
py -m pytest tutor/tests/e2e/ -v           # E2E tests only
py -m pytest tutor/tests/ --ignore=tutor/tests/e2e/ -v   # unit tests only
py -m pytest tutor/tests/ -v               # full suite
py -m ruff check tutor/
py -m ruff format --check tutor/
```

```bash
# macOS / Linux
python -m pytest tutor/tests/e2e/ -v
python -m pytest tutor/tests/ --ignore=tutor/tests/e2e/ -v
python -m pytest tutor/tests/ -v
python -m ruff check tutor/
python -m ruff format --check tutor/
```

## Requirements

- **Internet connection** — TTS (edge-tts) runs for real; the LLM is mocked
- **ffmpeg + ffprobe** — must be on PATH or in a standard Windows install location;
  required by pydub (audio loading) and `test_video_streams.py` stream checks
- **Playwright Chromium** — required by `test_slide_render.py`;
  install with `playwright install chromium` (already done in Docker image)
- **No API key needed** — `GROQ_API_KEY` is injected as a dummy value by conftest.py

## Why the Fixture Is Small

`tutor/tests/e2e/fixtures/sample.md` is a 3-paragraph document (~100 words). E2E
tests are slow because they call real TTS. A single-unit run takes 30–60 seconds.
Keeping the fixture tiny keeps the full suite under 3 minutes.

## Output Location

Pipeline output is written to `<tempdir>/learnx_e2e_smoke/` (e.g. `/tmp/learnx_e2e_smoke/`
on Linux, `%TEMP%\learnx_e2e_smoke\` on Windows). The directory persists between runs
so you can inspect the output manually.

## Skipped Tests

- `test_video_streams.py` — all tests skip if `tutorial.mp4` is absent (video pipeline optional)
- `test_slide_render.py` — all tests skip if `slides/` directory is absent (visual pipeline optional)
