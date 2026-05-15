# Day 18 (v5) — Version Flag and Sequential Spec Execution

## Goal

Add `--version v5` to `learnx_dk.py` so a single command discovers every spec file
in `specs/v5/` and runs them sequentially through the existing `run_yolo()` flow —
no human interaction required between specs.

```powershell
python scripts/learnx_dk.py --mode yolo --version v5
```

This day implements the discovery and execution loop only. Result tracking and the
consolidated report come in day2.

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
  scripts/learnx_dk.py                ← add --version flag, _discover_specs(),
                                        run_yolo_version(), update main()
  scripts/tests/test_learnx_dk.py     ← update test_parse_mode_long_form for
                                        5-tuple, add 5 new tests

Does NOT touch:
  tutor/                    ← application code unchanged
  scripts/run_review.py     ← review pipeline unchanged
  .claude/agents/           ← review agents unchanged
```

---

## Change 1 — Extend `_parse()` to return a 5-tuple

### Current signature

```python
def _parse(argv: list[str]) -> tuple[str, bool, pathlib.Path | None, list[str]]:
    # returns: mode, dry_run, spec, rest
```

### New signature

```python
def _parse(argv: list[str]) -> tuple[str, bool, pathlib.Path | None, str | None, list[str]]:
    # returns: mode, dry_run, spec, version, rest
```

Add `version: str | None = None` to the local variables. Parse `--version v5` and
`--version=v5` the same way `--spec` is parsed. If both `--version` and `--spec` are
present in the same invocation, print an error and `sys.exit(1)`:

```
error: --version and --spec are mutually exclusive
```

Update `main()` to unpack 5 fields:

```python
mode, dry_run, spec, version, extra = _parse(argv)
```

---

## Change 2 — Add `_discover_specs()`

```python
import re

def _discover_specs(specs_dir: pathlib.Path, version: str) -> list[pathlib.Path]:
    """Return spec .md files in specs/{version}/ sorted by embedded day number."""
    version_dir = specs_dir / version
    if not version_dir.is_dir():
        print(f"error: specs directory not found: {version_dir}")
        sys.exit(1)
    files = list(version_dir.glob("*.md"))
    def _key(p: pathlib.Path) -> tuple[int, str]:
        m = re.search(r"(\d+)", p.stem)
        return (int(m.group(1)) if m else 0, p.stem)
    return sorted(files, key=_key)
```

Numeric sort ensures `day1 < day2 < day10` (not `day1 < day10 < day2`).

---

## Change 3 — Add `run_yolo_version()`

```python
def run_yolo_version(
    project_dir: pathlib.Path,
    home_dir: pathlib.Path,
    version: str,
    extra_args: list[str],
    dry_run: bool,
) -> None:
    specs_dir = project_dir / "specs"
    specs = _discover_specs(specs_dir, version)
    if not specs:
        print(f"[version] no spec files found in specs/{version}/")
        return

    print(f"\n[version] {version} — {len(specs)} spec(s) found")
    for spec in specs:
        print(f"\n[version] ── spec: {spec.name} ──")
        run_yolo(project_dir, home_dir, spec_path=spec, extra_args=extra_args, dry_run=dry_run)
```

---

## Change 4 — Dispatch in `main()`

After parsing, when `version` is set, call `run_yolo_version()` regardless of mode:

```python
if version:
    run_yolo_version(project_dir, home_dir, version, extra, dry_run)
    return
```

Place this dispatch before the existing `if mode == "supervised":` block.

---

## New and updated tests

### Update existing test (broken by 5-tuple)

```python
# Before (4-tuple unpack — will fail after the signature change):
def test_parse_mode_long_form():
    mode, _, _, _ = _parse(["--mode=container"])
    assert mode == "container"

# After (5-tuple unpack):
def test_parse_mode_long_form():
    mode, _, _, _, _ = _parse(["--mode=container"])
    assert mode == "container"
```

### New tests — add to `scripts/tests/test_learnx_dk.py`

```python
from scripts.learnx_dk import _discover_specs, run_yolo_version


def test_parse_version_flag():
    _, _, _, version, _ = _parse(["--mode", "yolo", "--version", "v5"])
    assert version == "v5"


def test_parse_version_equals_form():
    _, _, _, version, _ = _parse(["--version=v5"])
    assert version == "v5"


def test_version_and_spec_mutually_exclusive():
    with pytest.raises(SystemExit) as exc:
        _parse(["--version", "v5", "--spec", "specs/v5/day1.md"])
    assert exc.value.code == 1


def test_discover_specs_numeric_sort(tmp_path):
    ver_dir = tmp_path / "specs" / "v5"
    ver_dir.mkdir(parents=True)
    for name in ("day10.md", "day2.md", "day1.md"):
        (ver_dir / name).write_text(f"# {name}")
    result = _discover_specs(tmp_path / "specs", "v5")
    assert [p.name for p in result] == ["day1.md", "day2.md", "day10.md"]


def test_discover_specs_missing_dir_exits(tmp_path):
    with pytest.raises(SystemExit) as exc:
        _discover_specs(tmp_path / "specs", "v99")
    assert exc.value.code == 1


def test_run_yolo_version_dry_run_prints_each_spec(tmp_path, dirs, capsys):
    project, home = dirs
    ver_dir = tmp_path / "specs" / "v5"
    ver_dir.mkdir(parents=True)
    (ver_dir / "day1.md").write_text("# day1")
    (ver_dir / "day2.md").write_text("# day2")
    run_yolo_version(tmp_path, home, "v5", extra_args=[], dry_run=True)
    out = capsys.readouterr().out
    assert "day1.md" in out
    assert "day2.md" in out
```

---

## Acceptance criteria

- [ ] `_parse()` returns a 5-tuple `(mode, dry_run, spec, version, rest)`
- [ ] `--version v5` and `--version=v5` both parse to `version == "v5"`
- [ ] `--version` and `--spec` together exit 1 with a clear error message
- [ ] `_discover_specs()` returns files sorted numerically: `day1 < day2 < day10`
- [ ] `_discover_specs()` exits 1 when `specs/{version}/` does not exist
- [ ] `run_yolo_version()` prints each spec name before running it
- [ ] `run_yolo_version()` dry-run prints spec names and docker command per spec, no subprocess
- [ ] `main()` routes to `run_yolo_version()` when `--version` is set
- [ ] `test_parse_version_flag` passes
- [ ] `test_parse_version_equals_form` passes
- [ ] `test_version_and_spec_mutually_exclusive` passes
- [ ] `test_discover_specs_numeric_sort` passes
- [ ] `test_discover_specs_missing_dir_exits` passes
- [ ] `test_run_yolo_version_dry_run_prints_each_spec` passes
- [ ] All pre-existing `test_learnx_dk.py` tests still pass (no regression)
- [ ] ruff clean
