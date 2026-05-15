# Day 25 (v8) — Rate Limit Detection and Retry

## Goal

When a spec fails because of an API rate limit, the current launcher marks it
`FAILED` and moves on. This day adds a retry loop: if the last N lines of output
match a rate-limit pattern, wait `rate_limit_wait_minutes` and try the spec again
in a fresh container. After `max_retries_per_spec` retries the spec is marked
`FAILED`.

The `SpecResult` gains a `retries` field and the consolidated report shows retry
annotations.

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
  scripts/learnx_dk.py                  ← add _is_rate_limited(); update
                                          SpecResult, run_yolo_version(),
                                          _print_version_report(), main()
  scripts/tests/test_learnx_dk.py       ← add 4 new tests

Does NOT touch:
  devloop.toml          ← [resilience] already has rate-limit keys from day1
  scripts/run_review.py ← unchanged
  tutor/                ← application code unchanged
```

---

## Change 1 — Add `_is_rate_limited()`

```python
def _is_rate_limited(last_lines: list[str], patterns: list[str]) -> bool:
    """Return True if any pattern appears (case-insensitive) in the last output lines."""
    text = "\n".join(last_lines).lower()
    return any(p.lower() in text for p in patterns)
```

---

## Change 2 — Add `retries` field to `SpecResult`

```python
@dataclass
class SpecResult:
    spec_name: str
    status: str           # "DONE" | "FAILED" | "TIMED_OUT"
    duration_s: float
    branch: str
    retries: int = 0      # ← new: rate-limit retries consumed
```

`retries` defaults to `0` so all existing `SpecResult(...)` construction in tests
continues to work without changes.

---

## Change 3 — Add retry loop to `run_yolo_version()`

Replace the single `_run_with_timeout()` call with a `while` loop. Read retry
config from the `[resilience]` section loaded in day1:

```python
# In run_yolo_version(), inside the `for spec in specs:` block:

cfg = config or _DEFAULTS
res = cfg.get("resilience", _DEFAULTS["resilience"])
max_retries = res["max_retries_per_spec"]
rate_limit_patterns = res["rate_limit_patterns"]
rate_limit_wait_s = res["rate_limit_wait_minutes"] * 60.0

container_cmd = build_docker_command(
    project_dir, home_dir, extra_args,
    image=cfg["project"]["docker_image"],
    workspace=cfg["project"]["workspace"],
    interactive=False,
)

attempt = 0
status = "FAILED"

while True:
    if dry_run:
        print(f"# [dry-run] container: {' '.join(container_cmd)}")
        status = "DONE"
        break

    rc, last_lines, timed_out = _run_with_timeout(
        container_cmd, session_timeout_s, idle_timeout_s
    )

    if timed_out:
        status = "TIMED_OUT"
        break

    if rc == 0:
        status = "DONE"
        break

    # Non-zero exit — check for rate limit
    if (
        rate_limit_wait_s > 0
        and attempt < max_retries
        and _is_rate_limited(last_lines, rate_limit_patterns)
    ):
        attempt += 1
        print(
            f"\n[resilience] rate limit detected — "
            f"waiting {rate_limit_wait_s / 60:.0f} min "
            f"(retry {attempt}/{max_retries})",
            flush=True,
        )
        time.sleep(rate_limit_wait_s)
        continue  # retry same spec

    status = "FAILED"
    break

duration_s = time.monotonic() - t0
results.append(SpecResult(spec.stem, status, duration_s, branch, retries=attempt))
```

---

## Change 4 — Update `_print_version_report()` to show retries

Append a retry annotation when `r.retries > 0`:

```python
for r in results:
    if r.status == "DONE":
        icon = "✓"
    elif r.status == "TIMED_OUT":
        icon = "⏱"
    else:
        icon = "✗"
    mins = int(r.duration_s / 60)
    retry_note = f"  ({r.retries} rate-limit retr{'y' if r.retries == 1 else 'ies'})" \
                 if r.retries > 0 else ""
    print(f"  {r.spec_name:<12}  {icon} {r.status:<10}  {mins} min{retry_note}")
```

---

## Change 5 — Add `--wait` CLI flag in `main()`

Parse `--wait N` from `extra` (minutes to wait on rate limit), the same way
`--session-timeout` is parsed in day1:

```python
wait_min, extra = _extract_int_flag(extra, "--wait")
rate_limit_wait_s = (wait_min or res["rate_limit_wait_minutes"]) * 60.0
```

Pass `rate_limit_wait_s` through to `run_yolo_version()` as part of the
`[resilience]` config override, or as a direct keyword argument:

```python
def run_yolo_version(
    ...
    rate_limit_wait_s: float = 120.0,   # ← new (2 min default)
    max_retries: int = 1,               # ← new
) -> None:
```

Alternatively, override the relevant resilience config keys before passing `config`
down. Either approach is acceptable — pick whichever is cleaner given the code
as it stands after day1.

---

## New tests — add to `scripts/tests/test_learnx_dk.py`

```python
from scripts.learnx_dk import _is_rate_limited


def test_is_rate_limited_matches_pattern():
    lines = ["some output", "Error: rate limit exceeded", "bye"]
    assert _is_rate_limited(lines, ["rate limit exceeded"]) is True


def test_is_rate_limited_case_insensitive():
    lines = ["You've Hit Your Limit for today"]
    assert _is_rate_limited(lines, ["you've hit your limit"]) is True


def test_is_rate_limited_no_match():
    lines = ["all good", "tests passed", "done"]
    assert _is_rate_limited(lines, ["rate limit exceeded"]) is False


def test_spec_result_retries_defaults_to_zero():
    r = SpecResult("day1", "DONE", 60.0, "sandbox/v5-day1")
    assert r.retries == 0
```

---

## Acceptance criteria

- [ ] `_is_rate_limited()` returns `True` when any pattern appears in the joined output
- [ ] `_is_rate_limited()` matching is case-insensitive
- [ ] `_is_rate_limited()` returns `False` when no pattern matches
- [ ] `SpecResult.retries` field exists and defaults to `0`
- [ ] Existing `SpecResult(...)` calls without `retries` still work (no breakage)
- [ ] `run_yolo_version()` retries a rate-limited spec up to `max_retries_per_spec` times
- [ ] `run_yolo_version()` does NOT retry when `rate_limit_wait_minutes == 0`
- [ ] `run_yolo_version()` marks spec `FAILED` after exhausting retries
- [ ] `run_yolo_version()` records `retries` count in `SpecResult`
- [ ] `_print_version_report()` shows `(1 rate-limit retry)` annotation for specs that retried
- [ ] `_print_version_report()` shows `(N rate-limit retries)` for N > 1
- [ ] `--wait N` CLI flag overrides `rate_limit_wait_minutes` from config
- [ ] `test_is_rate_limited_matches_pattern` passes
- [ ] `test_is_rate_limited_case_insensitive` passes
- [ ] `test_is_rate_limited_no_match` passes
- [ ] `test_spec_result_retries_defaults_to_zero` passes
- [ ] All pre-existing tests still pass
- [ ] ruff clean
