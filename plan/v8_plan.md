# LearnX v8 — Resilience (Timeouts, Hang Detection, Rate Limit Retry)

## The problem with v7

v7 gives us a generic, config-driven loop that can run an entire version
autonomously. But a 10-spec overnight run is only useful if it survives
the full duration without human intervention.

Three failure modes break unattended runs:

**Failure 1 — Hanging sessions.** Claude Code inside the container occasionally
hangs: waiting for a tool that never responds, stuck in a test-fix loop with
no output, or blocked on a subprocess. The outer process blocks on
`subprocess.communicate()` indefinitely. The user returns after 8 hours to find
the container still running, frozen at spec 3.

**Failure 2 — Silent exit after idle.** Claude finishes the work and exits, but
a background process inside the container keeps Docker alive. The launcher waits
forever. The progress file shows the spec as `in_progress`. Indistinguishable
from a genuine hang without a timeout.

**Failure 3 — Rate limits abort the version run.** A rate limit error at spec 4
of 10 marks that spec `failed` and stops the entire version run. The next 6 specs
never execute. This is unnecessary: the error is transient and would clear in 2
minutes.

---

## The three fixes

### Fix 1 — Session timeout

Each Docker session runs with a wall-clock timeout (default: 30 minutes, configurable
in `devloop.toml` or via CLI flag). If the session exceeds the timeout, the
launcher kills the container and marks the spec `timed_out`.

```toml
[resilience]
session_timeout_minutes = 30     # kill session after this wall-clock time
idle_timeout_minutes = 5         # kill if no output for this long
rate_limit_wait_minutes = 2      # wait and retry on rate limit (0 = no retry)
max_retries_per_spec = 1         # how many times to retry a failed spec
```

On timeout: the spec is marked `timed_out` in the run report, and the loop
continues with the next spec. The run does not abort.

### Fix 2 — Idle timeout

Separate from session timeout. If no output lines arrive from the container for
N minutes (default: 5), the session is killed.

Implementation: Docker stdout is streamed line by line. A watchdog thread
tracks `last_output_at`. If `now - last_output_at > idle_timeout`, the container
is killed.

This catches the "finished but stuck" case that session timeout alone does not.

### Fix 3 — Rate limit retry

Rate limit patterns are checked against the session's last N output lines on
non-zero exit. Default patterns (configurable in `devloop.toml`):

```toml
[resilience]
rate_limit_patterns = [
    "rate limit exceeded",
    "you've hit your limit",
    "429 too many requests",
    "quota exceeded",
]
```

On match: wait `rate_limit_wait_minutes`, then retry the same spec in a fresh
session. The retry count is stored in the progress file. After `max_retries_per_spec`
retries, the spec is marked `failed`.

Without `rate_limit_wait_minutes > 0`, rate limit exits are treated as failures
(current behavior preserved as the default).

---

## Run report shows resilience events

```
── v5 Execution Summary ─────────────────────────────────────
  day1  ✓ MERGE READY   22 min
  day2  ✓ MERGE READY   34 min
  day3  ⏱ TIMED OUT     30 min  (hit session limit — review manually)
  day4  ✓ MERGE READY   18 min  (1 rate-limit retry)
  day5  ✓ MERGE READY   29 min
─────────────────────────────────────────────────────────────
  5/5 specs attempted · 4 MERGE READY · 1 timed out · Total: 2h13m
```

---

## What changes

| Component | Change |
|---|---|
| `scripts/learnx_dk.py` | `_run_with_timeout()` — session timeout + kill |
| `scripts/learnx_dk.py` | `_stream_with_idle_watch()` — idle timeout watchdog thread |
| `scripts/learnx_dk.py` | Rate limit pattern matching + wait/retry loop |
| `scripts/learnx_dk.py` | `--session-timeout`, `--idle-timeout`, `--wait` CLI flags |
| `devloop.toml` | `[resilience]` section |

---

## What does not change

- `devloop.toml` structure (additive — new `[resilience]` section)
- Review pipeline unchanged
- Branch strategy unchanged
- Spec format unchanged
