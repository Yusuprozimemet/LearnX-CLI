import http.server
import json as _json
import threading

from scripts.dk.config import SpecResult

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
    function makeCell(text, cls) {
      var td = document.createElement("td");
      td.textContent = text;
      if (cls) td.className = cls;
      return td;
    }
    var es = new EventSource("/stream");
    es.onmessage = function(e) {
      var d = JSON.parse(e.data);
      var tbody = document.getElementById("rows");
      tbody.innerHTML = "";
      d.results.forEach(function(r) {
        var cls = r.status.toLowerCase().replace(/ /g,"_");
        var tr = document.createElement("tr");
        [makeCell(r.spec), makeCell(r.status, cls),
         makeCell(Math.round(r.duration_s/60)+" min"), makeCell(r.branch)
        ].forEach(function(td) { tr.appendChild(td); });
        tbody.appendChild(tr);
      });
      if (d.current_spec) {
        var tr = document.createElement("tr");
        [makeCell(d.current_spec), makeCell("► IN PROGRESS", "in_progress"),
         makeCell("—"), makeCell("—")
        ].forEach(function(td) { tr.appendChild(td); });
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


def _make_handler(server: "DashboardServer") -> type:
    """Return a BaseHTTPRequestHandler subclass bound to the given server."""

    class _Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: object) -> None:
            pass

        def do_GET(self) -> None:  # type: ignore[override]
            action = {
                "/": self._serve_html,
                "/status": self._serve_json,
                "/stream": self._serve_sse,
            }.get(self.path)
            if action:
                action()
            else:
                self.send_error(404)

        def _send_body(self, body: bytes, content_type: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _serve_html(self) -> None:
            self._send_body(DASHBOARD_HTML.encode(), "text/html; charset=utf-8")

        def _serve_json(self) -> None:
            self._send_body(_json.dumps(server._snapshot()).encode(), "application/json")

        def _serve_sse(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            try:
                data = _json.dumps(server._snapshot())
                self.wfile.write(f"data: {data}\n\n".encode())
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass

    return _Handler


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

    def _snapshot(self) -> dict:
        with self._lock:
            state = dict(self._state)
        state["recent_output"] = self._buffer.lines()
        return state

    def start(self) -> None:
        self._server = http.server.HTTPServer(("", self._port), _make_handler(self))
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
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
