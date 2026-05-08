# Day 12 — Shell Integration & Polish

## Goal

Wire the v2 visual pipeline into the existing LearnX shell. Add a `/video` command,
a `--video` flag for `/generate`, and update `/sessions` to surface MP4 presence.

**The existing `tutor/cli/commands.py` and `tutor/tutor.py` are not modified**
(the file is already 487 lines and audio commands are working). Video-specific
shell commands live in a new `tutor/cli/video_commands.py`.

---

## Data boundary

```
/video reads:
  audio/<session>/tutorial.units.json    ← written by audio pipeline
  audio/<session>/tutorial_units/*.mp3   ← written by audio pipeline

/video writes:
  video/<session>/tutorial.visuals.json  ← visual spec
  video/<session>/slides/*.png           ← composited slides
  video/<session>/subtitles.srt
  video/<session>/*.mp4
```

The video pipeline never writes into `audio/<session>/`.
The audio pipeline is never called from `/video`.

---

## New file — `tutor/cli/video_commands.py`

Contains all video-related shell handlers. Under 400 lines.

```python
from pathlib import Path
from tutor.cli import theme
from tutor.cli.commands import ShellContext, AUDIO_DIR

VIDEO_DIR = Path("video")


def cmd_video(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /video [session-name]
    Generate MP4 video for a session. Requires /generate to have run first."""

def cmd_vsessions(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /vsessions — list sessions that have a completed video."""

def _run_video_pipeline(session: str) -> None:
    """Resolve paths and call run_visual_pipeline()."""

def _assert_audio_ready(audio_session_dir: Path) -> None:
    """Raise VideoError if tutorial.units.json or tutorial_units/*.mp3 are missing."""

def _confirm_overwrite(mp4_path: Path) -> bool:
    """Prompt if full_session.mp4 already exists. Returns True to proceed."""
```

### `cmd_video` behaviour

```
LearnX > /video week2_3

  Resolving session week2_3...
  Found 4 units. Starting visual pipeline.

  [1/4] Generating visual specs...
  [2/4] Rendering diagrams and compositing slides...
  [3/4] Building SRT subtitles...
  [4/4] Assembling video...
        [1/6] Generating title card video...
        [2/6] Rendering unit 1/4 — Interface vs Abstract Class...
        ...
        [6/6] Embedding subtitles...

  ✓  video/week2_3/full_session.mp4  (127 MB, 26:42)
```

If `video/<session>/full_session.mp4` already exists:
```
  Session already has a video. Regenerate? [y/N]:
```
If user types anything other than `y`: print `Skipped.` and return.

### `cmd_video` — infer session from context

If no session name is given, check `ctx.current_session`:
```python
def cmd_video(tokens, ctx):
    if not tokens:
        if ctx.current_session:
            session = ctx.current_session
        else:
            print(theme.red("  Usage: /video <session-name>"))
            return
    else:
        session = tokens[0]
    ...
```

---

## Pipeline entry point — `tutor/visual/__init__.py`

Created on Day 12. Makes `tutor/visual` a package and exposes the single entry
point used by both `/video` and `--video`:

```python
def run_visual_pipeline(
    session: str,
    audio_dir: Path,
    video_dir: Path,
    llm_fn,
    difficulty: str = "beginner",
    no_cache: bool = False,
) -> Path:
    """
    Full Day 8–11 pipeline for one session.
    Reads from audio_dir, writes to video_dir.
    Returns path to full_session.mp4.
    """
    import json
    from tutor.generation.visual_planner import plan_visuals
    from tutor.visual.diagram_renderer import render_diagram
    from tutor.visual.slide_compositor import compose_all
    from tutor.visual.subtitle_writer import build_srt, get_line_start_offsets
    from tutor.visual.beat_timer import compute_slide_timings
    from tutor.visual.video_assembler import assemble_session

    units_json = audio_dir / "tutorial.units.json"
    doc_title  = _doc_title_from_units(units_json)
    unit_mp3s  = sorted((audio_dir / "tutorial_units").glob("unit_*.mp3"))
    slides_dir = video_dir / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)

    # Step 1 — Visual specs
    print("\n  [1/4] Generating visual specs...")
    visuals = plan_visuals(units_json, doc_title, session, llm_fn, difficulty, video_dir, no_cache)

    # Step 2 — Diagrams + slides
    print("  [2/4] Rendering diagrams and compositing slides...")
    diagram_pngs = {}
    for v in visuals:
        if v.slide_type == "unit":
            png = render_diagram(v, slides_dir)
            diagram_pngs[v.unit_index] = png
    slide_paths = compose_all(visuals, diagram_pngs, slides_dir, session)

    # Step 3 — Subtitles
    print("  [3/4] Building SRT subtitles...")
    all_lines      = _load_all_lines(units_json)
    unit_durations = [_mp3_duration(mp3) for mp3 in unit_mp3s]
    srt_text       = build_srt(all_lines, unit_durations)
    srt_path       = video_dir / "subtitles.srt"
    srt_path.write_text(srt_text, encoding="utf-8")

    # Step 4 — Video
    print("  [4/4] Assembling video...")
    line_offsets  = get_line_start_offsets(all_lines, unit_durations)
    slide_timings = compute_slide_timings(slide_paths, all_lines, line_offsets, visuals, unit_durations)
    return assemble_session(video_dir, audio_dir / "tutorial_units", slide_timings, unit_mp3s, srt_path)
```

Private helpers in the same file (keep file under 150 lines):

```python
def _doc_title_from_units(units_json: Path) -> str:
def _load_all_lines(units_json: Path) -> list[DialogueLine]:
def _mp3_duration(path: Path) -> float:   # via ffprobe
def _format_duration(seconds: float) -> str:   # → "26:42"
```

---

## `--video` flag for `/generate`

`_make_generate_parser()` in `tutor/tutor.py` gains one new flag:

```python
parser.add_argument(
    "--video",
    action="store_true",
    default=False,
    help="Run full visual pipeline after audio generation",
)
```

In `cmd_generate()` in `tutor/cli/commands.py`, after `_tutor.cmd_generate(args)`:

```python
if getattr(args, "video", False):
    from tutor.visual import run_visual_pipeline
    from tutor.cli.video_commands import VIDEO_DIR
    from tutor.config import load_config
    from tutor.infra import llm as _llm
    from functools import partial
    session = _session_name(args.input)
    config  = load_config()
    llm_fn  = partial(_llm.chat, provider=args.provider, config=config)
    video_dir = VIDEO_DIR / session
    video_dir.mkdir(parents=True, exist_ok=True)
    run_visual_pipeline(
        session, AUDIO_DIR / session, video_dir, llm_fn, args.difficulty, args.no_cache
    )
```

This is the only change to `commands.py`. No new command handlers are added there.

---

## `/sessions` update

Add a `[mp4]` badge in the existing `cmd_sessions()`:

```python
# In cmd_sessions(), replace the print line:
has_mp4 = (VIDEO_DIR / s.name / "full_session.mp4").exists()
badge   = theme.green("  [mp4]") if has_mp4 else ""
print(f"  {theme.cyan(s.name):<30} {len(units)} units   {size}{badge}")
```

Also add to the footer:
```
  Generate video: /video <session-name>
```

This requires importing `VIDEO_DIR` from `video_commands` in `commands.py`.
That is the only additional import — no logic changes to `cmd_sessions`.

---

## `ShellContext` update

Add two fields to the existing `ShellContext` dataclass in `commands.py`:

```python
@dataclass
class ShellContext:
    player: object = None
    player_thread: threading.Thread | None = None
    last_units_dir: Path | None = None
    current_session: str | None = None   # ← new: set by cmd_generate and cmd_play
    last_video: Path | None = None       # ← new: set after successful /video
```

`current_session` is set:
- In `cmd_generate`: `ctx.current_session = _session_name(args.input)` after success
- In `cmd_play`: `ctx.current_session = unit_token` when resolving a session name

---

## `COMMAND_MAP` update — `shell.py`

In `tutor/cli/shell.py`, add video commands to the dispatch map at startup:

```python
from tutor.cli.video_commands import cmd_video, cmd_vsessions

# Add to COMMAND_MAP import or patch at the bottom of shell.py:
from tutor.cli.commands import COMMAND_MAP
COMMAND_MAP["/video"]     = cmd_video
COMMAND_MAP["/vsessions"] = cmd_vsessions
```

This avoids touching `commands.py`'s COMMAND_MAP definition. Shell wires them in.

---

## Asset bundling — fonts

Required files (must be committed to repo):
```
tutor/assets/fonts/
  Inter-Regular.ttf
  Inter-Bold.ttf
  JetBrainsMono-Regular.ttf
  JetBrainsMono-Bold.ttf
```

Source:
- Inter: fonts.google.com/specimen/Inter — download family, extract TTFs
- JetBrains Mono: jetbrains.com/lp/mono — download, extract TTFs

Both SIL OFL 1.1 licensed — safe to commit to a public repo.

`tutor/assets/__init__.py` — path helpers:
```python
from pathlib import Path
ASSETS_DIR = Path(__file__).parent
FONTS_DIR  = ASSETS_DIR / "fonts"
LOGO_PATH  = ASSETS_DIR / "logo_small.png"   # optional; drawn programmatically if absent
```

---

## `/help` update

Add two entries to the `/help` output in `cmd_help()`:

```
  /video [session]    Generate MP4 video for a session (needs /generate first)
  /vsessions          List sessions that have a completed video
```

---

## Complete file layout after Day 12

```
tutor/
  models.py               ← add VisualSpec (Day 8)
  exceptions.py           ← add VideoError (Day 8)
  llm_config.toml         ← add visual call type (Day 8)
  assets/
    __init__.py
    fonts/
      Inter-Regular.ttf
      Inter-Bold.ttf
      JetBrainsMono-Regular.ttf
      JetBrainsMono-Bold.ttf
    logo_small.png        ← optional
  generation/
    visual_planner.py     ← Day 8 (new)
  visual/
    __init__.py           ← Day 12 (run_visual_pipeline entry point)
    diagram_renderer.py   ← Day 9
    slide_theme.py        ← Day 10 (constants + font loading)
    slide_draw.py         ← Day 10 (draw primitives)
    slide_compositor.py   ← Day 10 (compose_* functions)
    subtitle_writer.py    ← Day 11
    beat_timer.py         ← Day 11
    video_assembler.py    ← Day 11
  cli/
    commands.py           ← existing (2 tiny additions: current_session field, VIDEO_DIR badge)
    video_commands.py     ← Day 12 (new: /video, /vsessions)
    shell.py              ← existing + 4-line COMMAND_MAP patch

audio/<session>/          ← written by audio pipeline (unchanged)
video/<session>/          ← written by visual pipeline (new)
```

---

## Acceptance criteria

- [ ] `/video week2_3` runs full pipeline and prints step progress
- [ ] `/generate week2/3.md --video` runs audio then video in sequence
- [ ] `/sessions` shows `[mp4]` badge for sessions with `full_session.mp4`
- [ ] `/video` with no argument uses `ctx.current_session` if set
- [ ] Missing `tutorial.units.json` → `VideoError`, printed cleanly, no traceback
- [ ] `KeyboardInterrupt` during video → "Cancelled." message, no crash
- [ ] Font files committed under `tutor/assets/fonts/`
- [ ] `/help` shows `/video` and `/vsessions` entries
- [ ] `video_commands.py` < 400 lines
- [ ] `tutor/visual/__init__.py` < 150 lines
- [ ] No changes to audio pipeline behaviour — all existing tests still pass
- [ ] End-to-end: `/generate week2/3.md --video` produces playable `full_session.mp4`

## Tests — `tutor/tests/cli/test_video_commands.py`

- `test_cmd_video_missing_units_json` — audio session dir exists but no units JSON → VideoError
- `test_cmd_video_infers_session_from_context` — ctx.current_session set, no arg → uses it
- `test_cmd_video_unknown_session` — session not in audio/ → error message, no crash
- `test_cmd_video_prompts_before_overwrite` — full_session.mp4 exists → confirm prompt
- `test_generate_with_video_flag_calls_pipeline` — mock run_visual_pipeline, assert called
- `test_sessions_shows_mp4_badge` — session with full_session.mp4 in video/ → "[mp4]" in output
- `test_sessions_no_badge_without_mp4` — no MP4 → no badge
