# Day 31 (v11) — Integrate Dashboard into Version Run

## Goal

Wire the `OutputBuffer` and `DashboardServer` (built in day1) into the execution
path:

1. `_run_with_timeout()` accepts an optional `output_buffer` parameter — the
   reader thread tees each output line to the buffer in addition to the terminal.
2. `run_yolo_version()` creates an `OutputBuffer`, optionally starts a
   `DashboardServer`, calls `dashboard.update()` before and after each spec, and
   stops the server in a `finally` block.
3. `--serve` and `--port` CLI flags are parsed in `main()` and forwarded to
   `run_yolo_version()`.

When `--serve` is not passed the code path is identical to v10 — zero overhead,
zero background threads.

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
  scripts/learnx_dk.py                ← update _run_with_timeout(),
                                        run_yolo_version(), main()
  scripts/tests/test_learnx_dk.py     ← add 4 new tests

Does NOT touch:
  scripts/run_review.py   ← unchanged
  devloop.toml            ← unchanged (dashboard section added in day1)
  tutor/                  ← unchanged
  .claude/agents/         ← unchanged
```

---

## Change 1 — Update `_run_with_timeout()` to accept `output_buffer`

Add an optional `output_buffer: OutputBuffer | None = None` parameter. In the
reader thread, tee each line to the buffer immediately after printing:

```python
def _run_with_timeout(
    cmd: list[str],
    session_timeout_s: float,
    idle_timeout_s: float,
    output_buffer: OutputBuffer | None = None,   # ← new
) -> tuple[int, list[str], bool]:
    ...
    def _reader() -> None:
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = raw.decode(errors="replace").rstrip()
            print(line, flush=True)
            ring.append(line)
            if len(ring) > 200:
                ring.pop(0)
            last_output_at[0] = time.monotonic()
            if output_buffer is not None:          # ← new
                output_buffer.append(line)         # ← new
    ...
```

The `output_buffer` reference is safe to write from the reader thread because
`OutputBuffer.append()` is protected by its own lock (day1).

---

## Change 2 — Update `run_yolo_version()` to create and manage the server

Add `serve: bool = False`, `port: int = 8080`, and `output_buffer: OutputBuffer | None = None`
parameters. The caller (`main()`) passes them; they default to no-op values.

```python
def run_yolo_version(
    project_dir: pathlib.Path,
    home_dir: pathlib.Path,
    version: str,
    review: bool,
    extra_args: list[str],
    dry_run: bool,
    specs_dir: str = "specs",
    session_timeout_s: float = 1800.0,
    idle_timeout_s: float = 300.0,
    rate_limit_wait_s: float = 120.0,
    max_retries: int = 1,
    config: dict | None = None,
    serve: bool = False,          # ← new
    port: int = 8080,             # ← new
) -> None:
    cfg = config or _DEFAULTS
    buf = OutputBuffer()
    dashboard = DashboardServer(buf, port=port) if serve else None

    if dashboard:
        dashboard.start()

    try:
        # ── existing notifier + atexit setup (v9, unchanged) ────────────────
        ...

        results: list[SpecResult] = []
        specs = _discover_specs(project_dir / specs_dir, version)
        ...

        for spec in specs:
            if dashboard:
                dashboard.update(results, current_spec=spec.stem)

            branch = _spec_branch_name(version, spec.stem)
            _checkout_spec_branch(branch, dry_run)
            t0 = time.monotonic()
            ...

            # Pass buf to _run_with_timeout so live output feeds the dashboard
            container_cmd = build_docker_command(
                project_dir, home_dir, extra_args,
                image=cfg["project"]["docker_image"],
                workspace=cfg["project"]["workspace"],
                interactive=False,
            )

            while True:
                if dry_run:
                    ...
                    break
                rc, last_lines, timed_out = _run_with_timeout(
                    container_cmd, session_timeout_s, idle_timeout_s,
                    output_buffer=buf,                # ← pass shared buffer
                )
                ...  # existing retry logic (v8, unchanged)

            duration_s = time.monotonic() - t0
            results.append(SpecResult(spec.stem, status, duration_s, branch, retries=attempt))

            if dashboard:
                dashboard.update(results, current_spec="")

        _print_version_report(results, version)

        # ── notification (v9, unchanged) ─────────────────────────────────────
        ...

    finally:
        if dashboard:
            dashboard.stop()
```

The `finally` block guarantees the server thread is shut down even if the loop
raises an exception or is interrupted.

---

## Change 3 — Parse `--serve` and `--port` in `main()`

After the existing flag extraction (session-timeout, idle-timeout, wait):

```python
# Consume --serve before passing extra to Claude
serve = "--serve" in extra
extra = [a for a in extra if a != "--serve"]

# Consume --port N
port_override, extra = _extract_int_flag(extra, "--port")

# Resolve port: CLI flag > env var > devloop.toml > default
dash_cfg = config.get("dashboard", _DEFAULTS["dashboard"])
env_port = int(os.environ.get("LEARNX_DASHBOARD_PORT", 0))
port = port_override or env_port or dash_cfg["default_port"]
```

Forward to `run_yolo_version()`:

```python
if version:
    run_yolo_version(
        project_dir, home_dir, version, review, extra, dry_run,
        specs_dir=proj["specs_dir"],
        session_timeout_s=session_timeout_s,
        idle_timeout_s=idle_timeout_s,
        rate_limit_wait_s=rate_limit_wait_s,
        max_retries=res["max_retries_per_spec"],
        config=config,
        serve=serve,      # ← new
        port=port,        # ← new
    )
    return
```

`--serve` is silently ignored when not combined with `--version` (no version run,
no dashboard). Attempting to start a dashboard for a single `run_implement()` call
is not supported — log a note if `serve` is True but `version` is None:

```python
if serve and not version:
    print("[dashboard] --serve is only used with --version; ignoring", flush=True)
```

---

## New tests — add to `scripts/tests/test_learnx_dk.py`

```python
def test_serve_flag_consumed_from_extra(dirs, capsys):
    """--serve must not be forwarded to Claude as an extra arg."""
    project, home = dirs
    with patch("scripts.learnx_dk.pathlib.Path.cwd", return_value=project), \
         patch("scripts.learnx_dk.pathlib.Path.home", return_value=home), \
         patch("scripts.learnx_dk._load_config", return_value=_DEFAULTS), \
         patch("scripts.learnx_dk.run_implement") as mock_impl:
        main(["--serve", "--dry-run"])
    # --serve without --version prints a note and falls through to run_implement
    # The important thing: "--serve" is not in the extra_args passed to run_implement
    if mock_impl.called:
        call_extra = mock_impl.call_args.kwargs.get("extra_args",
                     mock_impl.call_args.args[4] if len(mock_impl.call_args.args) > 4 else [])
        assert "--serve" not in call_extra


def test_port_flag_consumed_from_extra(dirs, capsys):
    """--port N must not be forwarded to Claude."""
    project, home = dirs
    with patch("scripts.learnx_dk.pathlib.Path.cwd", return_value=project), \
         patch("scripts.learnx_dk.pathlib.Path.home", return_value=home), \
         patch("scripts.learnx_dk._load_config", return_value=_DEFAULTS), \
         patch("scripts.learnx_dk.run_implement") as mock_impl:
        main(["--port", "9090", "--dry-run"])
    if mock_impl.called:
        call_extra = mock_impl.call_args.kwargs.get("extra_args",
                     mock_impl.call_args.args[4] if len(mock_impl.call_args.args) > 4 else [])
        assert "--port" not in call_extra
        assert "9090" not in call_extra


def test_run_with_timeout_tees_to_output_buffer():
    """Lines produced by the subprocess are written to the OutputBuffer."""
    buf = OutputBuffer()
    cmd = ["python", "-c", "print('hello-from-container')"]
    rc, lines, timed_out = _run_with_timeout(
        cmd, session_timeout_s=30.0, idle_timeout_s=0,
        output_buffer=buf,
    )
    assert rc == 0
    assert any("hello-from-container" in ln for ln in buf.lines())


def test_run_yolo_version_with_serve_starts_and_stops_server(tmp_path, dirs, capsys):
    """Dashboard server is started and stopped around the version loop."""
    project, home = dirs
    ver_dir = tmp_path / "specs" / "v5"
    ver_dir.mkdir(parents=True)
    (ver_dir / "day1.md").write_text("# day1")

    started = []
    stopped = []

    class _FakeServer:
        def start(self): started.append(True)
        def stop(self): stopped.append(True)
        def update(self, *a, **kw): pass

    with patch("scripts.learnx_dk.DashboardServer", return_value=_FakeServer()), \
         patch("scripts.learnx_dk._checkout_spec_branch"), \
         patch("scripts.learnx_dk._run_with_timeout", return_value=(0, [], False)):
        run_yolo_version(
            tmp_path, home, "v5", review=False,
            extra_args=[], dry_run=False,
            config={**_DEFAULTS},
            serve=True, port=18888,
        )

    assert started == [True]
    assert stopped == [True]
```

---

## Acceptance criteria

- [ ] `_run_with_timeout()` accepts `output_buffer: OutputBuffer | None = None`
- [ ] When `output_buffer` is provided, each output line is written to it via `append()`
- [ ] When `output_buffer` is `None`, behaviour is identical to v10 (no regression)
- [ ] `run_yolo_version()` accepts `serve: bool = False` and `port: int = 8080`
- [ ] When `serve=True`: `DashboardServer` is created, started before the loop, stopped in `finally`
- [ ] When `serve=False`: no `DashboardServer` is created (zero background threads)
- [ ] `dashboard.update(results, current_spec=spec.stem)` is called before each spec
- [ ] `dashboard.update(results, current_spec="")` is called after each spec completes
- [ ] `--serve` flag is consumed from `extra` and not forwarded to Claude
- [ ] `--port N` flag is consumed from `extra` and not forwarded to Claude
- [ ] Port resolution order: `--port` CLI > `LEARNX_DASHBOARD_PORT` env var > `devloop.toml` > `8080`
- [ ] `--serve` without `--version` logs a note and does not start a server
- [ ] `test_serve_flag_consumed_from_extra` passes
- [ ] `test_port_flag_consumed_from_extra` passes
- [ ] `test_run_with_timeout_tees_to_output_buffer` passes
- [ ] `test_run_yolo_version_with_serve_starts_and_stops_server` passes
- [ ] All pre-existing tests still pass
- [ ] ruff clean
