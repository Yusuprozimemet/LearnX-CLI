# Day 29 (v10) — Wire Two-Phase Review into run_review.py main()

## Goal

Connect `run_phase1()` and `run_phase2()` (built in day1) to the execution flow:

- `run_review.py main()` calls `run_phase1()`, checks `had_findings`, then
  conditionally calls `run_phase2()`.
- A `--no-two-phase` CLI flag allows overriding the `devloop.toml` setting per run.
- The existing `main()` single-pass behaviour is fully replaced; the old
  `build_review_command()` call remains available for tests and backwards compat
  but is no longer the primary path.

---

## Done (merge gate)

```powershell
py -m pytest scripts/tests/test_learnx_dk.py -v
py -m pytest scripts/tests/test_review_agents.py -v
py -m ruff check scripts/
py -m ruff format --check scripts/
```

Report: paste gate output. List each acceptance criterion.
Stop: do not merge — wait for human review.

---

## Data boundary

```
Modifies (existing):
  scripts/run_review.py                   ← rewrite main() to call run_phase1/2;
                                            add --no-two-phase flag; load config
  scripts/tests/test_review_agents.py     ← add 4 new tests; update
                                            test_review_dry_run_does_not_call_subprocess

Does NOT touch:
  .claude/agents/         ← agent files created in day1, unchanged
  devloop.toml            ← unchanged
  scripts/learnx_dk.py    ← unchanged (two_phase config already flows through)
  tutor/                  ← unchanged
```

---

## Change 1 — Rewrite `run_review.py main()`

Replace the current `main()` with the two-phase orchestrator:

```python
def main(argv: list[str] | None = None) -> None:
    if argv is None:
        argv = sys.argv[1:]

    dry_run = "--dry-run" in argv
    no_two_phase = "--no-two-phase" in argv
    remaining = [a for a in argv if a not in ("--dry-run", "--no-two-phase")]

    spec_path: pathlib.Path | None = None
    if "--spec" in remaining:
        idx = remaining.index("--spec")
        spec_path = pathlib.Path(remaining[idx + 1])
        remaining = remaining[:idx] + remaining[idx + 2:]

    agents_dir: str | None = None
    if "--agents-dir" in remaining:
        idx = remaining.index("--agents-dir")
        agents_dir = remaining[idx + 1]
        remaining = remaining[:idx] + remaining[idx + 2:]

    project_dir = pathlib.Path.cwd()
    home_dir = pathlib.Path.home()

    # Resolve agents_dir from CLI > config > default
    config = _load_config(project_dir)
    if agents_dir is None:
        agents_dir = config["review"]["agents_dir"]

    # Determine whether phase 2 is enabled
    two_phase = config["review"].get("two_phase", True) and not no_two_phase

    if dry_run:
        cmd = build_review_command(project_dir, home_dir, spec_path, remaining,
                                   agents_dir=agents_dir)
        print(" ".join(cmd))
        if two_phase:
            print("# [two-phase] phase 2 would run if phase 1 finds issues")
        return

    # ── Phase 1 ──────────────────────────────────────────────────────────────
    print("\n── Phase 1 (issue discovery) ──")
    _rc1, phase1_output, had_findings = run_phase1(
        project_dir, home_dir, spec_path, agents_dir, remaining
    )

    # ── Phase 2 (conditional) ────────────────────────────────────────────────
    if two_phase and had_findings:
        print("\n── Phase 2 (fix verification) ──")
        run_phase2(project_dir, home_dir, phase1_output, agents_dir, remaining)
    elif two_phase and not had_findings:
        print("\n[review] phase 1 clean — skipping phase 2")
    else:
        print("\n[review] two-phase disabled — phase 1 only")
```

### Why `had_findings` controls phase 2

`had_findings` is `True` when the phase 1 output contains `"NEEDS FIXES"`. The
existing `REVIEW_PROMPT_TEMPLATE` already instructs Claude to output either
`"MERGE READY"` or `"NEEDS FIXES"` — no prompt change required. Phase 2 is skipped
when phase 1 is clean, saving the cost of a second Claude session.

### Backwards compatibility

`build_review_command()` is kept unchanged. Tests that call it directly still pass.
The old single-pass `main()` flow is gone; `--dry-run` now prints the phase 1
command and a note about phase 2.

---

## Change 2 — Add `_load_config` import to `run_review.py`

`run_review.py` already imports from `learnx_dk`. Add `_load_config` and `_DEFAULTS`:

```python
from scripts.learnx_dk import (   # noqa: E402
    _DEFAULTS,
    _load_config,
    _to_posix,
    build_command,
)
```

Remove the now-unused `IMAGE`, `WORKSPACE` imports if they were still present.

---

## Updated test — `test_review_dry_run_does_not_call_subprocess`

The test previously checked that `subprocess.run` is not called on `--dry-run`.
The logic is unchanged but `main()` now also prints a phase 2 note — update:

```python
def test_review_dry_run_does_not_call_subprocess(dirs, capsys):
    with patch("scripts.run_review.pathlib.Path.cwd", return_value=dirs[0]), \
         patch("scripts.run_review.pathlib.Path.home", return_value=dirs[1]), \
         patch("scripts.run_review._load_config", return_value=_DEFAULTS), \
         patch("scripts.run_review.subprocess.run") as mock_run:
        main(["--dry-run"])
    mock_run.assert_not_called()
```

---

## New tests — add to `scripts/tests/test_review_agents.py`

```python
from scripts.run_review import run_phase1, run_phase2
from scripts.learnx_dk import _DEFAULTS


def test_main_dry_run_shows_phase2_note(dirs, capsys):
    with patch("scripts.run_review.pathlib.Path.cwd", return_value=dirs[0]), \
         patch("scripts.run_review.pathlib.Path.home", return_value=dirs[1]), \
         patch("scripts.run_review._load_config", return_value=_DEFAULTS):
        main(["--dry-run"])
    out = capsys.readouterr().out
    assert "phase 2" in out.lower()


def test_main_no_two_phase_flag_skips_phase2(dirs, capsys):
    """--no-two-phase disables phase 2 regardless of config."""
    with patch("scripts.run_review.pathlib.Path.cwd", return_value=dirs[0]), \
         patch("scripts.run_review.pathlib.Path.home", return_value=dirs[1]), \
         patch("scripts.run_review._load_config", return_value=_DEFAULTS), \
         patch("scripts.run_review.run_phase1",
               return_value=(0, "NEEDS FIXES\nsome output", True)) as p1, \
         patch("scripts.run_review.run_phase2") as p2:
        main(["--no-two-phase"])
    p1.assert_called_once()
    p2.assert_not_called()


def test_main_skips_phase2_when_phase1_clean(dirs, capsys):
    """Phase 2 is not called when phase 1 output contains MERGE READY."""
    with patch("scripts.run_review.pathlib.Path.cwd", return_value=dirs[0]), \
         patch("scripts.run_review.pathlib.Path.home", return_value=dirs[1]), \
         patch("scripts.run_review._load_config", return_value=_DEFAULTS), \
         patch("scripts.run_review.run_phase1",
               return_value=(0, "MERGE READY — no blocking issues", False)) as p1, \
         patch("scripts.run_review.run_phase2") as p2:
        main([])
    p1.assert_called_once()
    p2.assert_not_called()
    out = capsys.readouterr().out
    assert "skipping phase 2" in out


def test_main_calls_phase2_when_phase1_has_findings(dirs):
    """Phase 2 is called when phase 1 output contains NEEDS FIXES."""
    with patch("scripts.run_review.pathlib.Path.cwd", return_value=dirs[0]), \
         patch("scripts.run_review.pathlib.Path.home", return_value=dirs[1]), \
         patch("scripts.run_review._load_config", return_value=_DEFAULTS), \
         patch("scripts.run_review.run_phase1",
               return_value=(0, "NEEDS FIXES\nmissing test", True)) as p1, \
         patch("scripts.run_review.run_phase2",
               return_value=(0, "VERIFIED")) as p2:
        main([])
    p1.assert_called_once()
    p2.assert_called_once()
    # phase1_report is passed to phase2
    call_kwargs = p2.call_args
    assert "NEEDS FIXES" in call_kwargs.args[2]   # phase1_report positional arg
```

---

## Acceptance criteria

- [ ] `run_review.py main()` calls `run_phase1()` on every non-dry-run invocation
- [ ] `main()` calls `run_phase2()` only when `had_findings` is `True` and `two_phase` is enabled
- [ ] `main()` skips phase 2 and prints `"skipping phase 2"` when phase 1 is clean
- [ ] `--no-two-phase` flag forces single-pass behaviour regardless of `devloop.toml`
- [ ] `main()` loads `devloop.toml` via `_load_config()` to determine `two_phase`
- [ ] `main()` dry-run prints the phase 1 command and a phase 2 note; no subprocess called
- [ ] `run_phase2()` receives the phase 1 output text as `phase1_report`
- [ ] `test_review_dry_run_does_not_call_subprocess` still passes (updated for `_load_config` mock)
- [ ] `test_main_dry_run_shows_phase2_note` passes
- [ ] `test_main_no_two_phase_flag_skips_phase2` passes
- [ ] `test_main_skips_phase2_when_phase1_clean` passes
- [ ] `test_main_calls_phase2_when_phase1_has_findings` passes
- [ ] All pre-existing `test_review_agents.py` tests still pass
- [ ] All `test_learnx_dk.py` tests still pass
- [ ] ruff clean
