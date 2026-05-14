---
name: product_check
description: Runs the LearnX pipeline on the test fixture and verifies audio, video, and slide output quality
---

You are checking whether the product works, not whether the code looks right.
Run the following steps in order and report the result of each.

## Step 1 — Run the pipeline on the test fixture

```bash
python -m tutor generate tutor/tests/e2e/fixtures/sample.md --output /tmp/learnx_check
```

Expected: exits 0, output directory contains tutorial.mp3, tutorial.mp4 (or slides).
If it crashes: paste the traceback. STOP — do not proceed to further steps.

## Step 2 — Verify audio stream in video

```bash
ffprobe -v error \
  -select_streams a:0 \
  -show_entries stream=codec_type,duration,bit_rate \
  -of json /tmp/learnx_check/tutorial.mp4
```

Expected: `codec_type` is `audio`, `duration` > 0.
FAIL if: no audio stream returned, or duration is 0 or null.

## Step 3 — Check audio is not silent

```python
from pydub import AudioSegment
audio = AudioSegment.from_mp3("/tmp/learnx_check/tutorial.mp3")
db_level = audio.dBFS
print(f"Audio level: {db_level:.1f} dBFS")
# Anything above -60 dBFS is audible
assert db_level > -60, f"Audio appears silent: {db_level:.1f} dBFS"
```

Expected: dBFS above -60.
FAIL if: dBFS is -inf or below -60 (silent or near-silent track).

## Step 4 — Screenshot HTML slides (if slides were generated)

```python
from playwright.sync_api import sync_playwright
import pathlib

slide_dir = pathlib.Path("/tmp/learnx_check/slides")
if slide_dir.exists():
    html_files = list(slide_dir.glob("*.html"))
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        for html in html_files[:3]:   # first 3 slides max
            page.goto(f"file://{html}")
            page.wait_for_load_state("networkidle")
            screenshot = f"/tmp/learnx_check/screenshot_{html.stem}.png"
            page.screenshot(path=screenshot)
            print(f"Screenshot saved: {screenshot}")
        browser.close()
```

After running: describe what the screenshots look like. Are slides blank? Is text visible?
Are there any error messages or broken layout?

## Step 5 — Check A/V sync (timing.json vs audio duration)

```python
import json
from pydub import AudioSegment
import pathlib

timing = json.loads(
    pathlib.Path("/tmp/learnx_check/tutorial.timing.json").read_text()
)
audio = AudioSegment.from_mp3("/tmp/learnx_check/tutorial.mp3")

last_unit = max(int(k) for k in timing["units"])
last_entry = timing["units"][str(last_unit)][-1]
timing_end_ms = last_entry["end_ms"]
audio_duration_ms = len(audio)
drift_ms = abs(audio_duration_ms - timing_end_ms)

print(f"Audio duration: {audio_duration_ms}ms")
print(f"Timing end:     {timing_end_ms}ms")
print(f"Drift:          {drift_ms}ms")
assert drift_ms < 500, f"A/V drift too large: {drift_ms}ms"
```

Expected: drift < 500ms.
FAIL if: drift >= 500ms (slides and audio will be noticeably out of sync).

## Report format

```
PIPELINE RUN: PASS / FAIL
AUDIO STREAM: PRESENT (Xs) / MISSING
SILENCE CHECK: {dBFS value} — PASS / FAIL
SLIDE SCREENSHOTS: [describe what you see for each slide]
A/V SYNC: {drift}ms — PASS / FAIL

OVERALL: PRODUCT WORKING / PRODUCT BROKEN
Blocking issues: [list or "none"]

Suggested fix notes:
[List any novel pipeline surprises — env issues, tool edge cases, encoding quirks —
that are NOT obvious from reading the code. Write "none" if nothing surprising happened.
Do NOT write to fixes/ — this is for the human to decide.]
```
