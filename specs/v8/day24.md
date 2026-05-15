# Day 24 (v8) — Session Timeout and Idle Watchdog

## Goal

Version runs (`--version v5 --review`) are unattended and can hang indefinitely.
This day adds two defences:

1. **Session timeout** — kill the container if the total wall-clock time exceeds N
   minutes. The loop continues with the next spec; the stuck spec is marked `TIMED_OUT`.
2. **Idle timeout** — kill the container if no output arrives for N minutes. Catches
   the "Claude finished but a background process kept Docker alive" case.

Both timeouts apply only to version runs. Single-spec interactive runs get session
timeout only (idle timeout requires non-interactive output capture, which conflicts
with the `-it` Docker flags needed for interactive sessions).

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
  devloop.toml                          ← add [resilience] section
  scripts/learnx_dk.py                  ← add _extract_int_flag(),
                                          _run_with_timeout(); update
                                          build_docker_command(),
                                          run_implement(), run_yolo_version(),
                                          SpecResult, main()
  scripts/tests/test_learnx_dk.py       ← add 5 new tests

Does NOT touch:
  scripts/run_review.py       ← unchanged
  tutor/                      ← application code unchanged
  .claude/agents/             ← unchanged
```

---

## Change 1 — Add `[resilience]` to `devloop.toml`

Append to `devloop.toml` (created in v7/day1):

```toml
[resilience]
session_timeout_minutes = 30   # kill container after this wall-clock time
idle_timeout_minutes = 5       # kill if no output for this long
rate_limit_wait_minutes = 2    # wait before retrying on rate limit (0 = no retry)
max_retries_per_spec = 1       # max retries per spec on rate limit
rate_limit_patterns = [
    "rate limit exceeded",
    "you've hit your limit",
    "429 too many requests",
    "quota exceeded",
]
```

---

## Change 2 — Add `[resilience]` defaults to `_DEFAULTS` in `learnx_dk.py`

```python
_DEFAULTS: dict = {
    ...
    "resilience": {
        "session_timeout_minutes": 30,
        "idle_timeout_minutes": 5,
        "rate_limit_wait_minutes": 2,
        "max_retries_per_spec": 1,
        "rate_limit_patterns": [
            "rate limit exceeded",
            "you've hit your limit",
            "429 too many requests",
            "quota exceeded",
        ],
    },
}
```

---

## Change 3 — Add `interactive` param to `build_docker_command()`

Version runs need non-interactive Docker execution (no `-it` flags) so that stdout
can be piped and inspected for idle detection and rate limit patterns.

```python
def build_docker_command(
    project_dir: pathlib.Path,
    home_dir: pathlib.Path,
    extra_args: list[str],
    image: str = IMAGE,
    workspace: str = WORKSPACE,
    interactive: bool = True,   # ← new
) -> list[str]:
    cmd = ["docker", "run", "--rm"]
    if interactive:
        cmd.append("-it")       # was always present; now gated
    ...
```

Update `build_command()` alias to forward `interactive`:

```python
def build_command(
    project_dir, home_dir, extra_args,
    image=IMAGE, workspace=WORKSPACE, interactive=True,
) -> list[str]:
    return build_docker_command(project_dir, home_dir, extra_args,
                                image, workspace, interactive)
```

---

## Change 4 — Add `_extract_int_flag()` helper

```python
def _extract_int_flag(
    args: list[str], flag: str
) -> tuple[int | None, list[str]]:
    """Pop --flag N from args. Return (int_value_or_None, remaining_args)."""
    if flag not in args:
        return None, args
    idx = args.index(flag)
    try:
        val = int(args[idx + 1])
        return val, args[:idx] + args[idx + 2:]
    except (IndexError, ValueError):
        return None, args
```

---

## Change 5 — Add `_run_with_timeout()`

This function runs a command non-interactively, streams its output to the terminal
in real time, and kills the process if it hangs (idle) or runs too long (session).

```python
import threading
import time

def _run_with_timeout(
    cmd: list[str],
    session_timeout_s: float,
    idle_timeout_s: float,
) -> tuple[int, list[str], bool]:
    """
    Run cmd non-interactively with output streaming and two kill triggers.

    Returns:
        returncode   — process exit code (-9 or similar if killed)
        last_lines   — last 200 stdout+stderr lines (for rate-limit detection)
        timed_out    — True if killed by session or idle timeout
    """
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )

    ring: list[str] = []
    last_output_at = [time.monotonic()]
    timed_out = [False]

    def _reader() -> None:
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = raw.decode(errors="replace").rstrip()
            print(line, flush=True)
            ring.append(line)
            if len(ring) > 200:
                ring.pop(0)
            last_output_at[0] = time.monotonic()

    def _watchdog() -> None:
        deadline = time.monotonic() + session_timeout_s
        while proc.poll() is None:
            now = time.monotonic()
            if idle_timeout_s > 0 and (now - last_output_at[0]) > idle_timeout_s:
                print(
                    f"\n[resilience] idle timeout "
                    f"({idle_timeout_s / 60:.0f} min) — killing session",
                    flush=True,
                )
                timed_out[0] = True
                proc.kill()
                return
            if now > deadline:
                print(
                    f"\n[resilience] session timeout "
                    f"({session_timeout_s / 60:.0f} min) — killing session",
                    flush=True,
                )
                timed_out[0] = True
                proc.kill()
                return
            time.sleep(2)

    t_read = threading.Thread(target=_reader, daemon=True)
    t_watch = threading.Thread(target=_watchdog, daemon=True)
    t_read.start()
    t_watch.start()
    proc.wait()
    t_read.join(timeout=5)

    return proc.returncode, ring, timed_out[0]
```

### Why `stdout=subprocess.PIPE` and no `-it`

`-it` allocates a pseudo-TTY and attaches stdin. With `stdout=PIPE` the OS cannot
allocate a TTY for the pipe — Docker would error. Non-interactive (`interactive=False`
in `build_docker_command`) removes `-it` so the pipe works. Output is still forwarded
to the terminal line-by-line via the reader thread.

---

## Change 6 — Update `SpecResult` to support `TIMED_OUT` status

`SpecResult` (defined in v5/day2) uses an untyped `str` for `status`. Document the
valid values with a comment; no dataclass change is needed:

```python
@dataclass
class SpecResult:
    spec_name: str
    status: str           # "DONE" | "FAILED" | "TIMED_OUT"
    duration_s: float
    branch: str
```

Update `_print_version_report()` to handle `TIMED_OUT`:

```python
def _print_version_report(results: list[SpecResult], version: str) -> None:
    ...
    for r in results:
        if r.status == "DONE":
            icon = "✓"
        elif r.status == "TIMED_OUT":
            icon = "⏱"
        else:
            icon = "✗"
        mins = int(r.duration_s / 60)
        print(f"  {r.spec_name:<12}  {icon} {r.status:<10}  {mins} min")
    ...
    done = sum(1 for r in results if r.status == "DONE")
    timed_out = sum(1 for r in results if r.status == "TIMED_OUT")
    failed = len(results) - done - timed_out
    print(
        f"  {len(results)}/{len(results)} specs attempted · "
        f"{done} done · {failed} failed · {timed_out} timed out · "
        f"Total: {total_mins} min"
    )
```

---

## Change 7 — Update `run_yolo_version()` to use `_run_with_timeout()`

`run_yolo_version()` currently calls `run_implement()` for each spec. Replace the
container step with `_run_with_timeout()` directly, using `interactive=False`:

```python
def run_yolo_version(
    project_dir: pathlib.Path,
    home_dir: pathlib.Path,
    version: str,
    review: bool,
    extra_args: list[str],
    dry_run: bool,
    specs_dir: str = "specs",
    session_timeout_s: float = 1800.0,   # ← new (30 min default)
    idle_timeout_s: float = 300.0,       # ← new (5 min default)
    config: dict | None = None,          # ← new (for review/e2e paths)
) -> None:
    ...
    for spec in specs:
        branch = _spec_branch_name(version, spec.stem)
        _checkout_spec_branch(branch, dry_run)
        t0 = time.monotonic()

        cfg = config or _DEFAULTS
        image = cfg["project"]["docker_image"]
        workspace = cfg["project"]["workspace"]
        container_cmd = build_docker_command(
            project_dir, home_dir, extra_args,
            image=image, workspace=workspace,
            interactive=False,             # ← non-interactive for output capture
        )

        if dry_run:
            print("# container:", " ".join(container_cmd))
            status = "DONE"
        else:
            rc, last_lines, timed_out = _run_with_timeout(
                container_cmd, session_timeout_s, idle_timeout_s
            )
            if timed_out:
                status = "TIMED_OUT"
            elif rc == 0:
                status = "DONE"
            else:
                status = "FAILED"

            if review and status != "TIMED_OUT":
                # Run E2E + review as before (unchanged)
                e2e_cmd = cfg["validation"]["e2e_tests"]
                subprocess.run(
                    _build_e2e_command(project_dir, e2e_cmd, image, workspace),
                    check=False,
                )
                rev_cmd = [_PY, cfg["review"]["review_script"],
                           "--spec", spec.as_posix()]
                subprocess.run(rev_cmd, check=False)

        duration_s = time.monotonic() - t0
        results.append(SpecResult(spec.stem, status, duration_s, branch))

    _print_version_report(results, version)
```

---

## Change 8 — Add `--session-timeout` and `--idle-timeout` CLI flags in `main()`

After calling `_parse()`, extract timeout flags from `extra` before passing to
functions. Use `_extract_int_flag()`:

```python
def main(argv=None):
    ...
    explore, review, dry_run, spec, version, extra = _parse(argv)
    project_dir = pathlib.Path.cwd()
    home_dir = pathlib.Path.home()
    config = _load_config(project_dir)

    # Extract resilience CLI flags (consume from extra so they aren't sent to Claude)
    res = config.get("resilience", _DEFAULTS["resilience"])
    session_timeout_min, extra = _extract_int_flag(extra, "--session-timeout")
    idle_timeout_min, extra = _extract_int_flag(extra, "--idle-timeout")
    session_timeout_s = (session_timeout_min or res["session_timeout_minutes"]) * 60.0
    idle_timeout_s = (idle_timeout_min or res["idle_timeout_minutes"]) * 60.0

    ...

    if version:
        run_yolo_version(
            project_dir, home_dir, version, review, extra, dry_run,
            specs_dir=proj["specs_dir"],
            session_timeout_s=session_timeout_s,
            idle_timeout_s=idle_timeout_s,
            config=config,
        )
        return
    ...
```

---

## New tests — add to `scripts/tests/test_learnx_dk.py`

```python
import threading
import time
from scripts.learnx_dk import _extract_int_flag, _run_with_timeout


def test_extract_int_flag_present():
    val, rest = _extract_int_flag(["--session-timeout", "45", "--dry-run"], "--session-timeout")
    assert val == 45
    assert rest == ["--dry-run"]


def test_extract_int_flag_absent():
    val, rest = _extract_int_flag(["--dry-run"], "--session-timeout")
    assert val is None
    assert rest == ["--dry-run"]


def test_build_docker_command_omits_it_when_not_interactive(dirs):
    project, home = dirs
    cmd = build_docker_command(project, home, extra_args=[], interactive=False)
    assert "-it" not in cmd
    assert "-i" not in cmd


def test_build_docker_command_includes_it_by_default(dirs):
    project, home = dirs
    cmd = build_docker_command(project, home, extra_args=[])
    assert "-it" in cmd


def test_run_with_timeout_kills_on_session_timeout():
    """Process that runs longer than session_timeout_s must be killed (timed_out=True)."""
    cmd = ["python", "-c", "import time; time.sleep(60)"]
    rc, lines, timed_out = _run_with_timeout(cmd, session_timeout_s=2.0, idle_timeout_s=0)
    assert timed_out is True
    # returncode is negative (SIGKILL) on Linux; non-zero on Windows
    assert rc != 0
```

---

## Acceptance criteria

- [ ] `devloop.toml` `[resilience]` section exists with all five keys
- [ ] `_DEFAULTS["resilience"]` mirrors the `devloop.toml` defaults
- [ ] `build_docker_command()` omits `-it` when `interactive=False`
- [ ] `build_docker_command()` includes `-it` by default (no regression)
- [ ] `_extract_int_flag()` removes the flag+value from args and returns the int
- [ ] `_extract_int_flag()` returns `(None, original_args)` when flag is absent
- [ ] `_run_with_timeout()` returns `(returncode, last_lines, timed_out)`
- [ ] `_run_with_timeout()` kills the process and sets `timed_out=True` when session timeout expires
- [ ] `_run_with_timeout()` kills the process and sets `timed_out=True` when idle timeout expires
- [ ] `_run_with_timeout()` streams output to terminal line-by-line while the process runs
- [ ] `run_yolo_version()` uses `_run_with_timeout()` with `interactive=False`
- [ ] `run_yolo_version()` marks spec `TIMED_OUT` when `_run_with_timeout` returns `timed_out=True`
- [ ] `run_yolo_version()` skips review step for `TIMED_OUT` specs
- [ ] `_print_version_report()` shows `⏱ TIMED_OUT` and counts timed-out specs separately
- [ ] `--session-timeout N` CLI flag overrides the config value
- [ ] `--idle-timeout N` CLI flag overrides the config value
- [ ] `test_extract_int_flag_present` passes
- [ ] `test_extract_int_flag_absent` passes
- [ ] `test_build_docker_command_omits_it_when_not_interactive` passes
- [ ] `test_build_docker_command_includes_it_by_default` passes
- [ ] `test_run_with_timeout_kills_on_session_timeout` passes
- [ ] All pre-existing tests still pass
- [ ] ruff clean
