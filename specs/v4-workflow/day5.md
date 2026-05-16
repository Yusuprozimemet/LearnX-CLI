# Day 5 — E2E Smoke Test Suite

## Goal

Add a suite of end-to-end smoke tests that run the real LearnX pipeline on a small
committed test fixture and assert on the actual output files. These tests exist because
unit tests cannot catch the class of bugs that broke the presentation:

- Silent audio in the output video (passes all unit tests; ffprobe finds no audio stream)
- Slides render blank or broken (passes all unit tests; Playwright screenshot shows empty page)
- A/V sync drift (passes timing unit tests; actual audio and slide boundary diverge by seconds)
- Pipeline crashes on real markdown input (not caught by mocked unit tests)

E2E smoke tests are the second layer of the merge gate. They must pass alongside unit
tests before any merge to main.

---

## Done (merge gate — new, applies to all future spec days)

```powershell
# Unit tests (unchanged)
py -m pytest tutor/tests/ -v --ignore=tutor/tests/e2e/

# E2E smoke tests (new — must also pass)
py -m pytest tutor/tests/e2e/ -v

# Lint
py -m ruff check tutor/
py -m ruff format --check tutor/
```

Report: paste both pytest summaries. List each acceptance criterion with pass/fail.
Stop: do not merge to main — wait for human review.

---

## Data boundary

```
Creates (new):
  tutor/tests/e2e/__init__.py
  tutor/tests/e2e/fixtures/sample.md          ← tiny test document (< 300 words)
  tutor/tests/e2e/fixtures/README.md          ← explains what the fixture is and why it is small
  tutor/tests/e2e/test_pipeline_smoke.py      ← runs pipeline, checks output files exist
  tutor/tests/e2e/test_audio_quality.py       ← pydub silence detection + duration check
  tutor/tests/e2e/test_video_streams.py       ← ffprobe audio/video stream verification
  tutor/tests/e2e/test_slide_render.py        ← Playwright screenshot + blank-page detection
  tutor/tests/e2e/test_av_sync.py             ← timing.json vs audio duration drift check
  tutor/tests/e2e/README.md                   ← what E2E tests verify, how to run them

Does NOT touch:
  tutor/tests/     (unit tests — existing files unchanged)
  tutor/           (no application code changes)
  Dockerfile       (Day 1 already installed ffprobe and Playwright)
  scripts/         (no changes)
  .claude/         (no changes)
```

---

## Test fixture — `tutor/tests/e2e/fixtures/sample.md`

The fixture must be:
- Short: 2–3 paragraphs, under 300 words
- Self-contained: no external references, no images
- Deterministic: produces the same dialogue structure on every run
  (use `--seed` flag or mock the LLM with a fixture response if supported)
- Topic: something simple — "What is a variable in programming?" works well

```markdown
# What is a Variable?

A variable is a named container that holds a value in a computer program.
Think of it like a labeled box: you put something inside the box, give the
box a name, and later you can find what you stored by using that name.

For example, in Python you might write `age = 25`. This creates a variable
called `age` and stores the number 25 in it. Later, when your program needs
to know the age, it looks inside the `age` box and finds 25.

Variables can hold different types of data: numbers, text, lists, or more
complex structures. The type determines what operations you can perform on
the value — you can add two numbers, but you cannot add a number to a sentence.
```

This document is intentionally minimal. E2E tests are slow; they run the real LLM
and real audio pipeline. Keeping the fixture tiny keeps the suite under 3 minutes.

---

## Test files — required structure

### `tutor/tests/e2e/test_pipeline_smoke.py`

```python
"""Smoke test: full pipeline runs without crash and produces expected output files."""
import pathlib
import subprocess
import pytest

FIXTURE = pathlib.Path("tutor/tests/e2e/fixtures/sample.md")
OUTPUT  = pathlib.Path("/tmp/learnx_e2e_smoke")


@pytest.fixture(scope="module")
def pipeline_output():
    """Run the pipeline once for all tests in this module."""
    OUTPUT.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["python", "-m", "tutor", "generate", str(FIXTURE), "--output", str(OUTPUT)],
        capture_output=True, text=True, timeout=300,
    )
    return result, OUTPUT
```

Tests in this file:
- `test_pipeline_exits_zero` — `result.returncode == 0`; paste stderr on failure
- `test_mp3_exists_and_nonempty` — `tutorial.mp3` in output, size > 0
- `test_timing_json_exists` — `tutorial.timing.json` exists
- `test_timing_json_is_valid` — file is valid JSON with `"version"` and `"units"` keys
- `test_unit_mp3s_exist` — at least one `unit_*.mp3` file in `tutorial_units/`

### `tutor/tests/e2e/test_audio_quality.py`

```python
"""Audio quality: not silent, duration reasonable, correct sample rate."""
from pydub import AudioSegment
import pytest
```

Tests in this file:
- `test_audio_not_silent` — `audio.dBFS > -60`; fail message must include actual dBFS value
- `test_audio_duration_positive` — `len(audio) > 0` milliseconds
- `test_audio_duration_matches_fixture_length` — duration > 10_000ms (10 seconds minimum for a 3-paragraph fixture)
- `test_unit_audio_not_silent` — for each `unit_*.mp3`: dBFS > -60

### `tutor/tests/e2e/test_video_streams.py`

```python
"""Video stream verification: audio and video streams both present, durations non-zero."""
import json, subprocess
import pytest
```

Tests in this file (all require `tutorial.mp4` to exist — skip if not):
- `test_video_file_exists` — `tutorial.mp4` in output; skip test module if absent with `pytest.skip`
- `test_video_stream_present` — ffprobe finds at least one `video` stream
- `test_audio_stream_present` — ffprobe finds at least one `audio` stream; **this is the bug that was missed**
- `test_audio_stream_duration_nonzero` — audio stream duration > 0 seconds
- `test_audio_stream_not_muted` — audio bitrate > 0 (catches streams present but silent)

ffprobe call pattern:
```python
def ffprobe_streams(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error",
         "-show_entries", "stream=codec_type,duration,bit_rate",
         "-of", "json", str(path)],
        capture_output=True, text=True,
    )
    return json.loads(result.stdout)["streams"]
```

### `tutor/tests/e2e/test_slide_render.py`

```python
"""Slide render: Playwright loads HTML slides, page is not blank, no error messages."""
import pathlib
import pytest

SLIDE_DIR = pathlib.Path("/tmp/learnx_e2e_smoke/slides")
```

Skip the entire module if `SLIDE_DIR` does not exist (slides are optional depending on flags).

Tests in this file:
- `test_at_least_one_slide_exists` — `SLIDE_DIR` contains at least one `.html` file
- `test_slide_page_not_blank` — Playwright loads first slide, `page.content()` length > 500 characters
- `test_slide_has_visible_text` — `page.locator("body").inner_text().strip()` is non-empty
- `test_slide_no_error_messages` — page does not contain the text "Error" or "TypeError" in visible content
- `test_slide_screenshot_saved` — screenshot taken and saved to `/tmp/learnx_e2e_smoke/slide_01.png`; file size > 5000 bytes (not a blank image)

Playwright fixture pattern:
```python
@pytest.fixture(scope="module")
def browser_page():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        yield page
        browser.close()
```

### `tutor/tests/e2e/test_av_sync.py`

```python
"""A/V sync: audio duration vs timing.json total duration drift < 500ms."""
import json, pathlib
from pydub import AudioSegment
import pytest
```

Tests in this file:
- `test_timing_units_nonempty` — `timing["units"]` has at least one key
- `test_timing_end_matches_audio_duration` — absolute difference between last `end_ms` in timing and `len(AudioSegment.from_mp3(...))` is < 500ms
- `test_no_timing_gaps` — for every unit: `entry[i+1].start_ms - entry[i].end_ms` equals a known silence constant (BREATH or TURN gap); no unexplained gaps

---

## Known failure modes this suite catches

| Failure | Which test catches it |
|---------|----------------------|
| Silent audio in video (the loudnorm / encoding bug) | `test_audio_stream_present`, `test_audio_not_silent`, `test_audio_stream_not_muted` |
| Blank slides / CSS not loaded | `test_slide_page_not_blank`, `test_slide_has_visible_text`, `test_slide_screenshot_saved` |
| Pipeline crash on real markdown | `test_pipeline_exits_zero` |
| A/V drift from timing estimation | `test_timing_end_matches_audio_duration` |
| Video file has no audio stream | `test_audio_stream_present` |
| Slides render "Error" text | `test_slide_no_error_messages` |

---

## Acceptance criteria

- [ ] `tutor/tests/e2e/fixtures/sample.md` exists, is under 300 words, has 2–3 paragraphs
- [ ] `test_pipeline_smoke.py` exists with 5 test functions matching names above
- [ ] `test_audio_quality.py` exists with 4 test functions; `test_audio_not_silent` asserts dBFS > -60
- [ ] `test_video_streams.py` exists with 5 test functions; `test_audio_stream_present` is one of them
- [ ] `test_slide_render.py` exists with 5 test functions; module skipped gracefully when no slides
- [ ] `test_av_sync.py` exists with 3 test functions; drift threshold is 500ms
- [ ] `py -m pytest tutor/tests/e2e/ -v` runs without import errors when pipeline output exists
- [ ] `tutor/tests/e2e/README.md` exists and documents: what the tests verify, how to run them, why the fixture is small
- [ ] All existing unit tests still pass (`py -m pytest tutor/tests/ --ignore=tutor/tests/e2e/`)

---

## Tests

The acceptance criteria above are the tests for this day — they describe exactly what
functions must exist and what they must assert. There is no separate test file that tests
the E2E tests themselves; instead, run `py -m pytest tutor/tests/e2e/ -v` after
generating output with the fixture document, and verify each test name appears and passes.

If the pipeline requires a live LLM key to run, mock the LLM responses in a
`conftest.py` fixture that returns a fixed dialogue script for the sample.md input.
The E2E tests must be runnable in CI without a real API key.
