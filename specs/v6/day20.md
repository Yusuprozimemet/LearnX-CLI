# Day 20 (v6) — Docker as Default, --explore and --review Flags

## Goal

Retire the four-mode system (`supervised`, `assisted`, `container`, `yolo`) and
replace it with two flags:

| Flag | Effect |
|---|---|
| _(none)_ | Docker container session (new default) |
| `--explore` | Host session, read-only permissions — for questions, no code changes |
| `--review` | After the container session: run E2E + 5-agent review (replaces `--mode yolo`) |

```powershell
# Old → New
python scripts/learnx_dk.py                            → python scripts/learnx_dk.py --explore
python scripts/learnx_dk.py --mode container           → python scripts/learnx_dk.py
python scripts/learnx_dk.py --mode yolo --spec X       → python scripts/learnx_dk.py --spec X --review
python scripts/learnx_dk.py --mode yolo --version v5   → python scripts/learnx_dk.py --version v5 --review
```

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
  scripts/learnx_dk.py                ← retire old modes; add run_explore(),
                                        run_implement(); redesign _parse()
  scripts/tests/test_learnx_dk.py     ← delete 9 stale tests, update 8,
                                        add 4 new tests

Does NOT touch:
  tutor/                    ← application code unchanged
  scripts/run_review.py     ← review pipeline unchanged
  .claude/agents/           ← review agents unchanged
  README.md                 ← docs updated in day2
  CLAUDE.md                 ← docs updated in day2
```

---

## Change 1 — New `_parse()` returning a 6-tuple

### Remove

`MODES`, `BANNER`, `ASSISTED_PERMISSIONS`. Keep `SETTINGS_LOCAL` (still used by
`run_explore()`).

### New signature

```python
def _parse(argv: list[str]) -> tuple[bool, bool, bool, pathlib.Path | None, str | None, list[str]]:
    # returns: explore, review, dry_run, spec, version, rest
```

Parse rules:
- `--explore` sets `explore = True`
- `--review` sets `review = True`
- `--dry-run` sets `dry_run = True`
- `--spec <path>` / `--spec=<path>` sets `spec`
- `--version <v>` / `--version=<v>` sets `version`
- `--version` and `--spec` together still exit 1 (rule from v5, unchanged)
- Unknown flags (e.g. `--mode`) are passed through to `rest` without error — this
  preserves forward-compat for extra Claude flags like `--model opus`

### Remove from `main()`

```python
# Remove this block:
if mode not in MODES:
    print(f"error: unknown mode '{mode}'. ...")
    sys.exit(1)
```

---

## Change 2 — Add `EXPLORE_PERMISSIONS` and `run_explore()`

```python
EXPLORE_PERMISSIONS = {
    "permissions": {
        "allow": [
            "Read(*)", "Glob(*)", "Grep(*)",
            "Bash(git status*)", "Bash(git log*)", "Bash(git diff*)",
            "Bash(git branch*)",
        ]
    }
}


def run_explore(extra_args: list[str], dry_run: bool) -> None:
    """Run Claude on the host with read-only permissions — no Docker required."""
    cmd = ["claude"] + extra_args
    if dry_run:
        print(f"[writes {SETTINGS_LOCAL}]")
        print(" ".join(cmd))
        print(f"[deletes {SETTINGS_LOCAL}]")
        return
    SETTINGS_LOCAL.write_text(json.dumps(EXPLORE_PERMISSIONS, indent=2))
    try:
        subprocess.run(cmd, check=False)
    finally:
        if SETTINGS_LOCAL.exists():
            SETTINGS_LOCAL.unlink()
```

`run_explore()` is modelled on the old `run_assisted()`: write temp permissions,
run Claude, always delete the file on exit.

---

## Change 3 — Add `run_implement()`, remove `run_container()` and `run_yolo()`

`run_implement()` is the single Docker execution path. Without `--review` it is
equivalent to the old `run_container()`. With `--review` it runs the three steps
the old `run_yolo()` ran.

```python
def run_implement(
    project_dir: pathlib.Path,
    home_dir: pathlib.Path,
    spec: pathlib.Path | None,
    review: bool,
    extra_args: list[str],
    dry_run: bool,
) -> None:
    container_cmd = build_docker_command(project_dir, home_dir, extra_args)

    if dry_run:
        print("# Step 1 — container session")
        print(" ".join(container_cmd))
        if review:
            e2e_cmd = _build_e2e_command(project_dir)
            review_cmd = [_PY, "scripts/run_review.py"]
            if spec:
                review_cmd += ["--spec", spec.as_posix()]
            print("# Step 2 — E2E smoke tests (inside container)")
            print(" ".join(e2e_cmd))
            print("# Step 3 — review pipeline")
            print(" ".join(review_cmd))
        return

    print("\n[implement] starting container session...")
    subprocess.run(container_cmd, check=False)

    if review:
        print("\n[implement] running E2E smoke tests...")
        e2e_result = subprocess.run(_build_e2e_command(project_dir), check=False)

        review_cmd = [_PY, "scripts/run_review.py"]
        if spec:
            review_cmd += ["--spec", spec.as_posix()]
        print("\n[implement] running review pipeline...")
        subprocess.run(review_cmd, check=False)

        if e2e_result.returncode != 0:
            print("\n[implement] WARNING: E2E tests had failures — review findings carefully")
```

Delete `run_container()` and `run_yolo()` entirely.
Delete `run_supervised()` and `run_assisted()`.

---

## Change 4 — Update `run_yolo_version()` to call `run_implement()`

`run_yolo_version()` currently calls `run_yolo()` (removed). Add a `review` parameter
and call `run_implement()` instead:

```python
def run_yolo_version(
    project_dir: pathlib.Path,
    home_dir: pathlib.Path,
    version: str,
    review: bool,            # ← new parameter
    extra_args: list[str],
    dry_run: bool,
) -> None:
    ...
    for spec in specs:
        ...
        run_implement(project_dir, home_dir, spec=spec, review=review,
                      extra_args=extra_args, dry_run=dry_run)
        ...
```

---

## Change 5 — Update `main()`

```python
def main(argv: list[str] | None = None) -> None:
    if argv is None:
        argv = sys.argv[1:]

    explore, review, dry_run, spec, version, extra = _parse(argv)
    project_dir = pathlib.Path.cwd()
    home_dir = pathlib.Path.home()

    if explore:
        run_explore(extra, dry_run)
        return

    if version:
        run_yolo_version(project_dir, home_dir, version, review, extra, dry_run)
        return

    run_implement(project_dir, home_dir, spec, review, extra, dry_run)
```

Remove `_print_banner()` — the mode concept is gone, `run_implement()` and
`run_explore()` print their own status lines.

---

## Test changes

### DELETE these tests (test removed functionality)

```
test_default_mode_is_supervised
test_supervised_dry_run_no_docker
test_assisted_dry_run_shows_settings_write
test_assisted_writes_and_deletes_settings_local
test_assisted_cleans_up_on_exception
test_assisted_permissions_have_no_deny
test_assisted_permissions_allow_git_commit
test_unknown_mode_exits_1
test_parse_mode_long_form
```

### UPDATE these tests (function signatures changed)

```python
# test_dry_run_prints_command_no_subprocess
# Before: default is supervised (no docker). After: default is Docker.
def test_dry_run_prints_command_no_subprocess(dirs, capsys):
    project, home = dirs
    with patch("scripts.learnx_dk.pathlib.Path.cwd", return_value=project), \
         patch("scripts.learnx_dk.pathlib.Path.home", return_value=home), \
         patch("scripts.learnx_dk.subprocess.run") as mock_run:
        main(["--dry-run"])
    out = capsys.readouterr().out
    assert "docker" in out          # default is now Docker
    mock_run.assert_not_called()


# test_container_dry_run_prints_docker_command
# Before: --mode container. After: Docker is default, no --mode flag.
def test_default_dry_run_prints_docker_command(dirs, capsys):
    project, home = dirs
    with patch("scripts.learnx_dk.pathlib.Path.cwd", return_value=project), \
         patch("scripts.learnx_dk.pathlib.Path.home", return_value=home), \
         patch("scripts.learnx_dk.subprocess.run") as mock_run:
        main(["--dry-run"])
    out = capsys.readouterr().out
    assert "docker" in out
    mock_run.assert_not_called()


# test_container_dry_run_has_skip_permissions  →  rename to test_implement_dry_run_has_skip_permissions
def test_implement_dry_run_has_skip_permissions(dirs, capsys):
    project, home = dirs
    run_implement(project, home, spec=None, review=False, extra_args=[], dry_run=True)
    out = capsys.readouterr().out
    assert "--dangerously-skip-permissions" in out


# test_yolo_dry_run_shows_three_steps  →  rename to test_implement_review_dry_run_shows_three_steps
def test_implement_review_dry_run_shows_three_steps(dirs, capsys):
    project, home = dirs
    run_implement(project, home, spec=None, review=True, extra_args=[], dry_run=True)
    out = capsys.readouterr().out
    assert "Step 1" in out
    assert "Step 2" in out
    assert "Step 3" in out


# test_yolo_dry_run_with_spec
def test_implement_review_dry_run_with_spec(dirs, capsys):
    project, home = dirs
    spec = pathlib.Path("specs/v5/day1.md")
    run_implement(project, home, spec=spec, review=True, extra_args=[], dry_run=True)
    out = capsys.readouterr().out
    assert "--spec" in out
    assert "day1.md" in out


# test_parse_version_flag — positions shift from (_, _, _, version, _) to (_, _, _, _, version, _)
def test_parse_version_flag():
    _, _, _, _, version, _ = _parse(["--version", "v5"])
    assert version == "v5"


# test_parse_version_equals_form
def test_parse_version_equals_form():
    _, _, _, _, version, _ = _parse(["--version=v5"])
    assert version == "v5"


# test_version_and_spec_mutually_exclusive — still exits 1, unpack positions change
def test_version_and_spec_mutually_exclusive():
    with pytest.raises(SystemExit) as exc:
        _parse(["--version", "v5", "--spec", "specs/v5/day1.md"])
    assert exc.value.code == 1


# test_run_yolo_version_dry_run_prints_each_spec — add review=False
def test_run_yolo_version_dry_run_prints_each_spec(tmp_path, dirs, capsys):
    project, home = dirs
    ver_dir = tmp_path / "specs" / "v5"
    ver_dir.mkdir(parents=True)
    (ver_dir / "day1.md").write_text("# day1")
    (ver_dir / "day2.md").write_text("# day2")
    run_yolo_version(tmp_path, home, "v5", review=False, extra_args=[], dry_run=True)
    out = capsys.readouterr().out
    assert "day1.md" in out
    assert "day2.md" in out


# test_run_yolo_version_dry_run_shows_branch_names — add review=False
def test_run_yolo_version_dry_run_shows_branch_names(tmp_path, dirs, capsys):
    project, home = dirs
    ver_dir = tmp_path / "specs" / "v5"
    ver_dir.mkdir(parents=True)
    (ver_dir / "day1.md").write_text("# day1")
    run_yolo_version(tmp_path, home, "v5", review=False, extra_args=[], dry_run=True)
    out = capsys.readouterr().out
    assert "sandbox/v5-day1" in out
```

### ADD these new tests

```python
from scripts.learnx_dk import EXPLORE_PERMISSIONS, run_explore, run_implement


def test_default_dry_run_uses_docker(dirs, capsys):
    """No flags → Docker container is the default execution path."""
    project, home = dirs
    with patch("scripts.learnx_dk.pathlib.Path.cwd", return_value=project), \
         patch("scripts.learnx_dk.pathlib.Path.home", return_value=home), \
         patch("scripts.learnx_dk.subprocess.run") as mock_run:
        main(["--dry-run"])
    out = capsys.readouterr().out
    assert "docker" in out
    mock_run.assert_not_called()


def test_explore_dry_run_runs_on_host(capsys):
    """--explore outputs a host claude command, not docker."""
    run_explore([], dry_run=True)
    out = capsys.readouterr().out
    assert "docker" not in out
    assert "claude" in out


def test_explore_dry_run_shows_settings_local(capsys):
    """--explore writes and deletes settings.local.json."""
    run_explore([], dry_run=True)
    out = capsys.readouterr().out
    assert "settings.local.json" in out


def test_explore_permissions_allow_only_reads():
    """Explore mode must not allow Edit or Write."""
    allows = EXPLORE_PERMISSIONS["permissions"]["allow"]
    assert not any("Edit" in rule for rule in allows)
    assert not any("Write" in rule for rule in allows)
```

### Keep these tests unchanged (still valid)

```
test_command_contains_skip_permissions
test_command_mounts_project_as_workspace
test_command_mounts_claude_dir_readonly
test_command_omits_gitconfig_when_absent
test_command_omits_claude_mount_when_absent
test_extra_args_forwarded_to_claude
test_discover_specs_numeric_sort
test_discover_specs_missing_dir_exits
test_spec_result_fields
test_spec_branch_name
test_checkout_spec_branch_dry_run
test_print_version_report_shows_all_specs
```

---

## Acceptance criteria

- [ ] `_parse()` returns 6-tuple `(explore, review, dry_run, spec, version, rest)`
- [ ] No `--mode` flag — passing `--mode anything` passes it through to `rest` silently
- [ ] Default (no flags) runs Docker container session via `run_implement()`
- [ ] `--explore` runs host `claude` with `EXPLORE_PERMISSIONS` (no Docker)
- [ ] `--explore` permissions allow Read/Glob/Grep/git-read; deny Edit and Write
- [ ] `--explore` writes and deletes `settings.local.json` (same try/finally as old `run_assisted`)
- [ ] `--review` triggers E2E + review after the container session
- [ ] `--spec X --review` passes `--spec X` to `scripts/run_review.py`
- [ ] `--version v5` alone: runs each spec without review
- [ ] `--version v5 --review`: runs each spec and runs review after each
- [ ] `run_yolo_version()` accepts `review: bool` parameter
- [ ] `run_container()`, `run_yolo()`, `run_supervised()`, `run_assisted()` are deleted
- [ ] `MODES`, `BANNER`, `ASSISTED_PERMISSIONS` are deleted; `SETTINGS_LOCAL` is kept
- [ ] All 9 deleted tests are gone from the test file
- [ ] All 8 updated tests pass with new function names / signatures
- [ ] All 4 new tests pass
- [ ] All unchanged tests still pass (no regression)
- [ ] ruff clean
