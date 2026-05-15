# Day 19 (v5) — SpecResult Tracking, Branch Management, Consolidated Report

## Goal

After day1's sequential loop runs each spec, this day adds:

1. A `SpecResult` dataclass that records per-spec outcome and timing
2. Per-spec git branch creation (`sandbox/v5-day1`, `sandbox/v5-day2`, …)
3. A consolidated report printed after all specs complete

```
── v5 Execution Summary ─────────────────────────────────────
  day1   ✓ DONE     22 min
  day2   ✗ FAILED   34 min
  day3   ✓ DONE     18 min
─────────────────────────────────────────────────────────────
  3/3 specs attempted · 2 done · 1 failed · Total: 74 min
```

Status is `DONE` when the container session exits 0, `FAILED` otherwise.
MERGE READY/NEEDS FIXES parsing is a v10 responsibility — not done here.

---

## Done (merge gate)

```powershell
py -m pytest scripts/tests/test_learnx_dk.py -v
py -m ruff check scripts/
py -m ruff format --check scripts/
```

Report: paste gate output. List each acceptance criterion.
Stop: do not merge — wait for human review.

---

## Data boundary

```
Modifies (existing):
  scripts/learnx_dk.py                ← add SpecResult, _spec_branch_name(),
                                        _checkout_spec_branch(), update
                                        run_yolo_version(), add _print_version_report()
  scripts/tests/test_learnx_dk.py     ← add 5 new tests

Does NOT touch:
  tutor/                    ← application code unchanged
  scripts/run_review.py     ← review pipeline unchanged
  .claude/agents/           ← review agents unchanged
```

---

## Change 1 — `SpecResult` dataclass

Add at module level (after the imports, before constants):

```python
from dataclasses import dataclass

@dataclass
class SpecResult:
    spec_name: str        # stem of spec file, e.g. "day1"
    status: str           # "DONE" | "FAILED"
    duration_s: float     # wall-clock seconds for this spec's full yolo run
    branch: str           # branch created for this spec, e.g. "sandbox/v5-day1"
```

---

## Change 2 — `_spec_branch_name()`

```python
def _spec_branch_name(version: str, spec_stem: str) -> str:
    """Return the sandbox branch name for one spec in a version run."""
    return f"sandbox/{version}-{spec_stem}"
```

Examples: `_spec_branch_name("v5", "day1")` → `"sandbox/v5-day1"`

---

## Change 3 — `_checkout_spec_branch()`

```python
def _checkout_spec_branch(branch: str, dry_run: bool) -> None:
    """Checkout main then create a fresh branch for this spec."""
    cmds = [
        ["git", "checkout", "main"],
        ["git", "checkout", "-b", branch],
    ]
    if dry_run:
        for cmd in cmds:
            print(" ".join(cmd))
        return
    for cmd in cmds:
        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            print(f"[version] warning: '{' '.join(cmd)}' exited {result.returncode}")
```

If `git checkout -b` fails (branch already exists), print a warning and continue —
the spec run still proceeds. The human must delete stale sandbox branches before
a clean version run.

---

## Change 4 — `_print_version_report()`

```python
def _print_version_report(results: list[SpecResult], version: str) -> None:
    width = 60
    print(f"\n{'─' * width}")
    print(f"  {version} Execution Summary")
    print(f"{'─' * width}")
    for r in results:
        icon = "✓" if r.status == "DONE" else "✗"
        mins = int(r.duration_s / 60)
        print(f"  {r.spec_name:<12}  {icon} {r.status:<8}  {mins} min")
    print(f"{'─' * width}")
    total_mins = int(sum(r.duration_s for r in results) / 60)
    done = sum(1 for r in results if r.status == "DONE")
    failed = len(results) - done
    print(
        f"  {len(results)}/{len(results)} specs attempted · "
        f"{done} done · {failed} failed · Total: {total_mins} min"
    )
```

---

## Change 5 — Update `run_yolo_version()`

Replace the loop body from day1 with result tracking:

```python
def run_yolo_version(
    project_dir: pathlib.Path,
    home_dir: pathlib.Path,
    version: str,
    extra_args: list[str],
    dry_run: bool,
) -> None:
    import time
    specs_dir = project_dir / "specs"
    specs = _discover_specs(specs_dir, version)
    if not specs:
        print(f"[version] no spec files found in specs/{version}/")
        return

    print(f"\n[version] {version} — {len(specs)} spec(s) found")
    results: list[SpecResult] = []

    for spec in specs:
        branch = _spec_branch_name(version, spec.stem)
        print(f"\n[version] ── spec: {spec.name}  branch: {branch} ──")
        _checkout_spec_branch(branch, dry_run)

        t0 = time.monotonic()
        run_yolo(project_dir, home_dir, spec_path=spec, extra_args=extra_args, dry_run=dry_run)
        duration_s = time.monotonic() - t0

        # dry_run: treat every spec as DONE (no real process ran)
        status = "DONE" if dry_run else "DONE"
        results.append(SpecResult(spec.stem, status, duration_s, branch))

    _print_version_report(results, version)
```

Note: in v5 all completed specs are marked "DONE" regardless of subprocess exit code.
Capturing and inspecting exit codes is a v8 (resilience) responsibility.

---

## New tests — add to `scripts/tests/test_learnx_dk.py`

```python
from scripts.learnx_dk import (
    SpecResult,
    _checkout_spec_branch,
    _print_version_report,
    _spec_branch_name,
)


def test_spec_result_fields():
    r = SpecResult(spec_name="day1", status="DONE", duration_s=120.0, branch="sandbox/v5-day1")
    assert r.spec_name == "day1"
    assert r.status == "DONE"
    assert r.duration_s == 120.0
    assert r.branch == "sandbox/v5-day1"


def test_spec_branch_name():
    assert _spec_branch_name("v5", "day1") == "sandbox/v5-day1"
    assert _spec_branch_name("v5", "day10") == "sandbox/v5-day10"


def test_checkout_spec_branch_dry_run(capsys):
    _checkout_spec_branch("sandbox/v5-day1", dry_run=True)
    out = capsys.readouterr().out
    assert "git checkout main" in out
    assert "sandbox/v5-day1" in out


def test_print_version_report_shows_all_specs(capsys):
    results = [
        SpecResult("day1", "DONE", 60.0, "sandbox/v5-day1"),
        SpecResult("day2", "FAILED", 120.0, "sandbox/v5-day2"),
    ]
    _print_version_report(results, "v5")
    out = capsys.readouterr().out
    assert "day1" in out
    assert "day2" in out
    assert "✓" in out
    assert "✗" in out


def test_run_yolo_version_dry_run_shows_branch_names(tmp_path, dirs, capsys):
    project, home = dirs
    ver_dir = tmp_path / "specs" / "v5"
    ver_dir.mkdir(parents=True)
    (ver_dir / "day1.md").write_text("# day1")
    run_yolo_version(tmp_path, home, "v5", extra_args=[], dry_run=True)
    out = capsys.readouterr().out
    assert "sandbox/v5-day1" in out
```

---

## Acceptance criteria

- [ ] `SpecResult` dataclass has fields: `spec_name`, `status`, `duration_s`, `branch`
- [ ] `_spec_branch_name("v5", "day1")` returns `"sandbox/v5-day1"`
- [ ] `_checkout_spec_branch()` dry-run prints `git checkout main` then `git checkout -b <branch>`
- [ ] `_checkout_spec_branch()` non-dry continues if git exits non-zero (prints warning, no crash)
- [ ] `run_yolo_version()` creates one `SpecResult` per spec
- [ ] `run_yolo_version()` calls `_checkout_spec_branch()` before each `run_yolo()`
- [ ] `_print_version_report()` prints spec names, ✓/✗ icons, duration in minutes, total summary
- [ ] dry-run end-to-end: version run prints branch names, spec names, and summary — no subprocess
- [ ] `test_spec_result_fields` passes
- [ ] `test_spec_branch_name` passes
- [ ] `test_checkout_spec_branch_dry_run` passes
- [ ] `test_print_version_report_shows_all_specs` passes
- [ ] `test_run_yolo_version_dry_run_shows_branch_names` passes
- [ ] All pre-existing `test_learnx_dk.py` tests still pass (no regression)
- [ ] ruff clean
