# Day 3 — Pre-commit Hooks + Session Metadata

## Goal

Two independent improvements delivered together because both are small:

1. **Pre-commit hooks** — catch lint and format errors at commit time, before they
   reach CI. Moves feedback from "push → CI fail → fix → push again" to "commit → fix immediately".

2. **Session metadata** — `tutorial.meta.json` gains `generated_at` and
   `total_duration_s`. The `/sessions` command shows duration, video status, and
   date instead of just name and file size.

---

## Part A — Pre-commit hooks

### File — `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.10
    hooks:
      - id: ruff
        args: ["--fix"]
      - id: ruff-format
```

**Two hooks, one tool:**
- `ruff` — runs lint checks with `--fix` to auto-correct fixable issues (unused imports,
  wrong quote style, etc.)
- `ruff-format` — applies Black-compatible formatting

**Why only ruff, not mypy:**
mypy on the full codebase takes 10–20 seconds. Pre-commit hooks run synchronously at
every commit. A 20-second pause on every `git commit` discourages committing frequently.
mypy runs in CI where the delay is acceptable. Pre-commit is for fast, zero-friction checks.

**Why not `trailing-whitespace` or `end-of-file-fixer`:**
`ruff format` already handles these. No need for separate hooks that duplicate work.

### Developer setup — one-time command

```bash
pip install pre-commit    # already in [dev] deps
pre-commit install        # installs the git hook into .git/hooks/pre-commit
```

After `pre-commit install`, the hooks run automatically on every `git commit`.
Running `pre-commit run --all-files` verifies the current working tree.

### README addition

Add to the existing **Setup** section, under a new `### Development` sub-heading:

```markdown
### Development

```bash
pip install -e .[dev]
pre-commit install
```

After `pre-commit install`, ruff runs automatically on every commit.
```

### What does NOT go in pre-commit

| Hook | Reason excluded |
|---|---|
| mypy | Too slow — 10–20 s per run; run manually before PRs, not on every commit |
| pytest | Far too slow for a commit hook; run locally before pushing |
| `check-json` / `check-yaml` | No significant JSON/YAML authoring in this repo |
| `detect-secrets` | No secrets committed; `.env` is in `.gitignore` |

---

## Part B — Session metadata

### Problem

`/sessions` currently shows:
```
  week2_3                        4 units   12345 KB  [mp4]
```

The user cannot tell how long a session is, or when it was generated without
checking the filesystem. `tutorial.meta.json` is already written at the end of
`/generate` but contains only `{"source_file": "..."}`.

### `tutorial.meta.json` — new fields

```json
{
  "source_file": "week2/3.md",
  "generated_at": "2026-05-09T14:32:11",
  "total_duration_s": 1574.3
}
```

**`generated_at`** — ISO 8601 local datetime, no timezone suffix (the tool runs
locally; timezone information adds no value here). Format: `datetime.now().isoformat(timespec="seconds")`.

**`total_duration_s`** — sum of all unit MP3 durations in seconds. Computed by
reading `tutorial.mp3` with pydub immediately before writing meta.json.

### Change in `tutor/cli/commands.py` — `cmd_generate()`

The meta.json write already happens at line 141. Extend it:

```python
# Current
meta = {"source_file": str(args.input)}

# New
import datetime

duration_s = 0.0
full_mp3 = output.parent / "tutorial.mp3"
if full_mp3.exists():
    try:
        from pydub import AudioSegment
        duration_s = len(AudioSegment.from_mp3(full_mp3)) / 1000.0
    except Exception:
        pass   # non-critical; 0.0 is a safe fallback

meta = {
    "source_file": str(args.input),
    "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
    "total_duration_s": duration_s,
}
```

`pydub` is already a runtime dependency — no new import needed at module level.
The `try/except` ensures meta.json is always written even if duration parsing fails.

### `/sessions` — updated output format

**Target output:**
```
  week2_3        4 units   26:14   [video]   2026-05-09
  week3_1        3 units   18:42             2026-05-07
  week4_tutorial 2 units    9:05             2026-05-08
```

**Column layout:**
- Session name — left-aligned, cyan, padded to 22 characters
- Unit count — right-aligned in 9 chars (`N units`)
- Duration — right-aligned in 8 chars, format `MM:SS` (blank if unknown)
- Video badge — `[video]` in green, 9 chars (blank if no video)
- Date — `YYYY-MM-DD` from `generated_at` (blank if missing)

### Change in `cmd_sessions()` — `tutor/cli/commands.py`

```python
def cmd_sessions(tokens: list[str], ctx: ShellContext) -> None:
    """Usage: /sessions — list all audio sessions"""
    from tutor.cli.video_commands import VIDEO_DIR
    import json as _json

    if not AUDIO_DIR.exists():
        print(theme.dim("  No sessions yet. Use /generate to create one."))
        return

    sessions = sorted(
        d for d in AUDIO_DIR.iterdir()
        if d.is_dir() and (d / "tutorial_units").exists()
    )
    if not sessions:
        print(theme.dim("  No sessions yet. Use /generate to create one."))
        return

    print()
    for s in sessions:
        units    = list((s / "tutorial_units").glob("unit_*.mp3"))
        meta     = _read_meta(s / "tutorial.meta.json")
        has_mp4  = (VIDEO_DIR / s.name / "full_session.mp4").exists()

        dur_str  = _format_duration(meta.get("total_duration_s", 0))
        date_str = (meta.get("generated_at", "") or "")[:10]    # "YYYY-MM-DD"
        badge    = theme.green("  [video]") if has_mp4 else "         "

        print(
            f"  {theme.cyan(s.name):<22}"
            f"  {len(units):>2} units"
            f"  {dur_str:>6}"
            f"{badge}"
            f"  {theme.dim(date_str)}"
        )

    print(theme.dim(f"\n  Play: /play <name>   Video: /video <name>"))
    print()


def _read_meta(path: Path) -> dict:
    """Read tutorial.meta.json. Returns empty dict on any error."""
    try:
        return _json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _format_duration(seconds: float) -> str:
    """Convert seconds to M:SS string. Returns blank string if seconds <= 0."""
    if seconds <= 0:
        return ""
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"
```

`_read_meta()` and `_format_duration()` are extracted as private helpers.
They are new functions, not modifications to existing logic, so they do not
risk breaking anything.

**Backward compatibility:** Sessions generated before this change have no
`generated_at` or `total_duration_s` in their meta.json. The `.get(..., 0)`
and `[:10]` slicing handle the missing-key case — they show blank fields,
not an error.

---

## Acceptance criteria

### Pre-commit

- [ ] `.pre-commit-config.yaml` exists with `ruff` and `ruff-format` hooks
- [ ] `pre-commit run --all-files` passes on the current codebase
- [ ] Setup instructions (`pre-commit install`) added to README
- [ ] mypy is NOT in pre-commit hooks

### Session metadata

- [ ] `generated_at` (ISO 8601 string) written to `tutorial.meta.json` after `/generate`
- [ ] `total_duration_s` (float, seconds) written to `tutorial.meta.json` after `/generate`
- [ ] Duration derived from `tutorial.mp3` via pydub, not estimated from word count
- [ ] `/sessions` output shows duration, video badge, and date
- [ ] `/sessions` does not crash on sessions that predate this change (missing fields)
- [ ] `_read_meta()` returns `{}` on any read/parse error — never raises
- [ ] `_format_duration(0)` returns `""` (blank, not "0:00")

## Tests — `tutor/tests/cli/test_commands.py`

New test file (or extend existing if one exists).

- `test_read_meta_returns_empty_on_missing_file`
- `test_read_meta_returns_empty_on_invalid_json`
- `test_format_duration_zero_returns_blank`
- `test_format_duration_correct_formatting` — 3674.0 → "61:14"
- `test_sessions_output_handles_missing_meta` — session without meta.json renders without error

## Verification commands

```bash
# Pre-commit
pre-commit install
pre-commit run --all-files

# Session metadata (manual)
# After running /generate on a test file, inspect the output:
python -c "import json; print(json.load(open('audio/<session>/tutorial.meta.json')))"
# Verify: generated_at and total_duration_s are present

# /sessions output
# Launch learnx and run /sessions — verify duration and date columns appear
```
