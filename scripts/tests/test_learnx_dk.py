import http.client
import json
import socket
import threading

from scripts.learnx_dk import DashboardServer, OutputBuffer, SpecResult


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


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
    assert "y" not in snapshot


def test_output_buffer_thread_safe():
    buf = OutputBuffer(maxlen=1000)

    def _writer() -> None:
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
        payload = json.loads(resp.read())
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
        payload = json.loads(conn.getresponse().read())
        assert payload["current_spec"] == "day2"
        assert payload["results"][0]["spec"] == "day1"
    finally:
        server.stop()
