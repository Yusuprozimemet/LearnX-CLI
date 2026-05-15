# Day 30 (v11) — OutputBuffer, DashboardServer, and Dashboard HTML

## Goal

Build the dashboard components in isolation — not yet wired into the version run.

1. `OutputBuffer` — thread-safe ring buffer (200 lines) that the output streaming
   thread writes and the HTTP server reads.
2. `DashboardServer` — background HTTP server exposing three endpoints:
   `GET /` (HTML page), `GET /status` (JSON snapshot), `GET /stream` (SSE).
3. `DASHBOARD_HTML` — the embedded HTML/JS page string (no external assets).
4. `devloop.toml [dashboard]` section and matching `_DEFAULTS` entry.

Day2 wires these into `_run_with_timeout()` and `run_yolo_version()`.

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
  devloop.toml                          ← add [dashboard] section
  scripts/learnx_dk.py                  ← add OutputBuffer, DashboardServer,
                                          DASHBOARD_HTML, _DEFAULTS["dashboard"]
  scripts/tests/test_learnx_dk.py       ← add 7 new tests

Does NOT touch:
  scripts/run_review.py       ← unchanged
  tutor/                      ← unchanged
  .claude/agents/             ← unchanged
```

---

## Change 1 — Add `[dashboard]` to `devloop.toml`

```toml
[dashboard]
default_port = 8080
```

---

## Change 2 — Add `"dashboard"` to `_DEFAULTS` in `learnx_dk.py`

```python
_DEFAULTS: dict = {
    ...
    "dashboard": {
        "default_port": 8080,
    },
}
```

---

## Change 3 — Add `OutputBuffer`

Place near the top of `learnx_dk.py`, after the imports:

```python
import threading

class OutputBuffer:
    """Thread-safe ring buffer for the last N lines of Docker stdout."""

    def __init__(self, maxlen: int = 200) -> None:
        self._lines: list[str] = []
        self._maxlen = maxlen
        self._lock = threading.Lock()

    def append(self, line: str) -> None:
        with self._lock:
            self._lines.append(line)
            if len(self._lines) > self._maxlen:
                self._lines.pop(0)

    def lines(self) -> list[str]:
        """Return a snapshot copy — safe to iterate outside the lock."""
        with self._lock:
            return list(self._lines)
```

---

## Change 4 — Add `DASHBOARD_HTML`

Embed the full page as a module-level string constant. No external files, no CDN.
The page connects to `/stream` via `EventSource`, receives a JSON snapshot on each
event, and updates the spec table and output div in-place.

```python
DASHBOARD_HTML = """\
<!DOCTYPE html>
<html>
<head>
  <title>LearnX Dashboard</title>
  <meta charset="utf-8">
  <style>
    body{font-family:monospace;background:#1a1a1a;color:#e0e0e0;padding:20px;margin:0}
    h2{color:#9c27b0;margin-bottom:4px}
    table{border-collapse:collapse;width:100%;margin-bottom:20px}
    th{text-align:left;padding:4px 12px;border-bottom:1px solid #333;color:#aaa}
    td{padding:4px 12px}
    .done{color:#4caf50}.failed{color:#f44336}.timed_out{color:#ff9800}
    .in_progress{color:#2196f3;font-weight:bold}.waiting{color:#666}
    #output{font-size:12px;height:280px;overflow-y:auto;background:#0a0a0a;
            padding:10px;white-space:pre-wrap;word-break:break-all}
    #info{color:#888;font-size:11px;margin-bottom:10px}
  </style>
</head>
<body>
  <h2>LearnX — version run</h2>
  <div id="info">connecting…</div>
  <table>
    <thead><tr><th>Spec</th><th>Status</th><th>Duration</th><th>Branch</th></tr></thead>
    <tbody id="rows"></tbody>
  </table>
  <h3>Live output</h3>
  <div id="output"></div>
  <script>
    var es = new EventSource("/stream");
    es.onmessage = function(e) {
      var d = JSON.parse(e.data);
      var tbody = document.getElementById("rows");
      tbody.innerHTML = "";
      d.results.forEach(function(r) {
        var cls = r.status.toLowerCase().replace(/ /g,"_");
        var tr = document.createElement("tr");
        tr.innerHTML = "<td>"+r.spec+"</td><td class='"+cls+"'>"+r.status+
          "</td><td>"+Math.round(r.duration_s/60)+" min</td><td>"+r.branch+"</td>";
        tbody.appendChild(tr);
      });
      if (d.current_spec) {
        var tr = document.createElement("tr");
        tr.innerHTML = "<td>"+d.current_spec+
          "</td><td class='in_progress'>► IN PROGRESS</td><td>—</td><td>—</td>";
        tbody.appendChild(tr);
      }
      var out = document.getElementById("output");
      out.textContent = d.recent_output.join("\\n");
      out.scrollTop = out.scrollHeight;
      document.getElementById("info").textContent =
        "last update: " + new Date().toLocaleTimeString();
    };
    es.onerror = function() {
      document.getElementById("info").textContent = "reconnecting…";
    };
  </script>
</body>
</html>"""
```

The SSE `EventSource` auto-reconnects when the server closes the connection after
each snapshot — this gives polling behaviour without managing a persistent write loop.

---

## Change 5 — Add `DashboardServer`

```python
import http.server
import json as _json


class DashboardServer:
    """
    Background HTTP server for the live progress dashboard.

    Thread model:
      - Main thread calls update() and stop().
      - A daemon thread runs HTTPServer.serve_forever().
      - HTTP handler reads _state and _buffer under _lock.
    """

    def __init__(self, output_buffer: OutputBuffer, port: int = 8080) -> None:
        self._buffer = output_buffer
        self._port = port
        self._lock = threading.Lock()
        self._state: dict = {"results": [], "current_spec": ""}
        self._server: http.server.HTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        server_self = self

        class _Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, fmt: str, *args: object) -> None:
                pass  # suppress per-request log lines

            def do_GET(self) -> None:  # type: ignore[override]
                if self.path == "/":
                    self._serve_html()
                elif self.path == "/status":
                    self._serve_json()
                elif self.path == "/stream":
                    self._serve_sse()
                else:
                    self.send_error(404)

            def _snapshot(self) -> dict:
                with server_self._lock:
                    state = dict(server_self._state)
                state["recent_output"] = server_self._buffer.lines()
                return state

            def _serve_html(self) -> None:
                body = DASHBOARD_HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _serve_json(self) -> None:
                body = _json.dumps(self._snapshot()).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _serve_sse(self) -> None:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                try:
                    data = _json.dumps(self._snapshot())
                    self.wfile.write(f"data: {data}\n\n".encode())
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass

        self._server = http.server.HTTPServer(("", self._port), _Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True
        )
        self._thread.start()
        print(f"[dashboard] serving at http://localhost:{self._port}", flush=True)

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()

    def update(self, results: list[SpecResult], current_spec: str) -> None:
        """Called by the main thread to push the latest progress state."""
        with self._lock:
            self._state = {
                "results": [
                    {
                        "spec": r.spec_name,
                        "status": r.status,
                        "duration_s": r.duration_s,
                        "branch": r.branch,
                    }
                    for r in results
                ],
                "current_spec": current_spec,
            }
```

---

## New tests — add to `scripts/tests/test_learnx_dk.py`

Use a random high port for each server test to avoid conflicts with other processes.

```python
import http.client
import random
import threading

from scripts.learnx_dk import DashboardServer, OutputBuffer


def _free_port() -> int:
    """Pick a random port in the ephemeral range unlikely to conflict."""
    return random.randint(18000, 19999)


def test_output_buffer_append_and_lines():
    buf = OutputBuffer(maxlen=3)
    buf.append("a")
    buf.append("b")
    buf.append("c")
    buf.append("d")  # evicts "a"
    assert buf.lines() == ["b", "c", "d"]


def test_output_buffer_lines_returns_copy():
    buf = OutputBuffer()
    buf.append("x")
    snapshot = buf.lines()
    buf.append("y")
    assert "y" not in snapshot  # snapshot is independent


def test_output_buffer_thread_safe():
    buf = OutputBuffer(maxlen=1000)
    def _writer():
        for i in range(500):
            buf.append(str(i))
    threads = [threading.Thread(target=_writer) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(buf.lines()) <= 1000


def test_dashboard_server_serves_html():
    port = _free_port()
    server = DashboardServer(OutputBuffer(), port=port)
    server.start()
    try:
        conn = http.client.HTTPConnection("localhost", port, timeout=5)
        conn.request("GET", "/")
        resp = conn.getresponse()
        assert resp.status == 200
        assert "text/html" in resp.getheader("Content-Type", "")
        assert b"LearnX" in resp.read()
    finally:
        server.stop()


def test_dashboard_server_status_returns_json():
    port = _free_port()
    buf = OutputBuffer()
    buf.append("hello from container")
    server = DashboardServer(buf, port=port)
    server.start()
    try:
        conn = http.client.HTTPConnection("localhost", port, timeout=5)
        conn.request("GET", "/status")
        resp = conn.getresponse()
        assert resp.status == 200
        payload = _json.loads(resp.read())
        assert "results" in payload
        assert "current_spec" in payload
        assert "recent_output" in payload
        assert "hello from container" in payload["recent_output"]
    finally:
        server.stop()


def test_dashboard_server_stream_returns_sse_headers():
    port = _free_port()
    server = DashboardServer(OutputBuffer(), port=port)
    server.start()
    try:
        conn = http.client.HTTPConnection("localhost", port, timeout=5)
        conn.request("GET", "/stream")
        resp = conn.getresponse()
        assert resp.status == 200
        assert "text/event-stream" in resp.getheader("Content-Type", "")
        body = resp.read().decode()
        assert body.startswith("data: ")
    finally:
        server.stop()


def test_dashboard_server_update_reflected_in_status():
    port = _free_port()
    server = DashboardServer(OutputBuffer(), port=port)
    server.start()
    try:
        server.update(
            [SpecResult("day1", "DONE", 60.0, "sandbox/v5-day1")],
            current_spec="day2",
        )
        conn = http.client.HTTPConnection("localhost", port, timeout=5)
        conn.request("GET", "/status")
        payload = _json.loads(conn.getresponse().read())
        assert payload["current_spec"] == "day2"
        assert payload["results"][0]["spec"] == "day1"
    finally:
        server.stop()
```

---

## Acceptance criteria

- [ ] `devloop.toml` `[dashboard]` section exists with `default_port = 8080`
- [ ] `_DEFAULTS["dashboard"]["default_port"]` is `8080`
- [ ] `OutputBuffer.append()` evicts the oldest line when `maxlen` is exceeded
- [ ] `OutputBuffer.lines()` returns a copy — mutations to the snapshot don't affect the buffer
- [ ] `OutputBuffer` is thread-safe under concurrent `append()` calls
- [ ] `DashboardServer.start()` launches a daemon thread; `stop()` shuts it down cleanly
- [ ] `GET /` returns `200 text/html` containing `"LearnX"`
- [ ] `GET /status` returns `200 application/json` with keys `results`, `current_spec`, `recent_output`
- [ ] `GET /stream` returns `200 text/event-stream`; body starts with `data: `
- [ ] `DashboardServer.update()` pushes new state visible in subsequent `/status` calls
- [ ] `DASHBOARD_HTML` contains an `EventSource("/stream")` call
- [ ] All 7 new tests pass
- [ ] All pre-existing tests still pass
- [ ] ruff clean
