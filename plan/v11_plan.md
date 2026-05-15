# LearnX v11 — Real-Time Progress Dashboard

## The problem with v10

A v9 version run (10 specs, 3–4 hours) with v9 notifications tells you when it
finishes. But during the run, you have no visibility:

- Which spec is currently executing?
- How long has it been running?
- Is it stuck, or just slow on a hard task?
- Did spec 4 fail cleanly or is the container hanging?

The notification arrives at the end. What about the middle?

The v6 progress file tracks state, but reading a JSON file manually is not useful.
The terminal output is inaccessible once you walk away from the machine.

A lightweight browser dashboard solves this: open a URL on any device on the
same network, see live progress without touching the running session.

---

## How the dashboard works

```powershell
python scripts/learnx_dk.py --version v5 --review --serve
# Starting dashboard at http://localhost:8080
# Version run started — 10 specs
```

Open `http://localhost:8080` in any browser on the same network.

### Dashboard view

```
LearnX — v5 (10 specs)                    Started: 22:14:03
──────────────────────────────────────────────────────────────
  day1   Add IdleWatcher class      ✓  MERGE READY   22 min
  day2   Wire IdleWatcher           ✓  MERGE READY   18 min
  day3   CLI flags                  ✓  MERGE READY   14 min
  day4   Notifications              ► IN PROGRESS    09 min  (phase 1 review)
  day5   Two-phase review           ○  waiting
  ...
──────────────────────────────────────────────────────────────
Live output (day4 — phase 1 review):
  [22:55:41]  Agent: code_quality — 1 finding
  [22:55:49]  Agent: spec_compliance — 0 findings
  [22:55:57]  Agent: test_coverage — 2 findings
  [22:56:02]  Claude applying fixes...
```

The page auto-refreshes via server-sent events (SSE). No JavaScript framework.
Minimal HTML with inline CSS.

### What is served

- `GET /` — dashboard HTML (static, auto-refreshes via SSE)
- `GET /stream` — SSE stream: task status events + live output lines
- `GET /status` — JSON snapshot (for programmatic checks or mobile polling)

### Implementation

The HTTP server runs in a background thread inside `learnx_dk.py`. It reads from:

1. The progress file (task status, start/end times, results) — v6 feature
2. A shared in-memory ring buffer — last 200 lines of live stdout from the current
   Docker session

The ring buffer is written by the output streaming thread. The HTTP server reads
it without blocking the task loop. Thread-safe via a `threading.Lock`.

The server is never started unless `--serve` is explicitly passed. Default runs
have zero background threads.

### Port configuration

```powershell
python scripts/learnx_dk.py --version v5 --review --serve --port=9090
```

Default: 8080. Configurable via `--port` CLI flag or `LEARNX_DASHBOARD_PORT` env var.

### devloop.toml

```toml
[dashboard]
default_port = 8080
```

---

## What changes

| Component | Change |
|---|---|
| `scripts/learnx_dk.py` | `DashboardServer` class — background HTTP thread, SSE endpoint |
| `scripts/learnx_dk.py` | `OutputBuffer` — thread-safe ring buffer for live output |
| `scripts/learnx_dk.py` | Docker stdout tee'd to terminal AND `OutputBuffer` |
| `scripts/learnx_dk.py` | `--serve`, `--port` CLI flags |
| `devloop.toml` | `[dashboard]` section (optional) |

---

## What does not change

- Task execution path — unchanged; `--serve` is additive
- Progress file format — unchanged (dashboard reads it, never writes it)
- All existing modes — unchanged
- No external server, no cloud, purely local HTTP

---

## Expected outcome

Start a version run, open the browser on your phone (same WiFi). See which spec is
running, how long it has been going, and the last 200 lines of output. Know in
30 seconds whether it is progressing or stuck — without SSH, without a terminal,
without interrupting the run.
