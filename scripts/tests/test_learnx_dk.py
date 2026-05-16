import http.client
import json
import socket
import sys
import threading
from unittest.mock import patch

from scripts.learnx_dk import (
    _DEFAULTS,
    DashboardServer,
    OutputBuffer,
    SpecResult,
    _run_with_timeout,
    main,
    run_yolo_version,
)


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


# ── Day 31 — dashboard integration tests ─────────────────────────────────────


def test_serve_flag_consumed_from_extra(dirs, capsys):
    """--serve must not be forwarded to Claude as an extra arg."""
    project, home = dirs
    with (
        patch("scripts.learnx_dk.pathlib.Path.cwd", return_value=project),
        patch("scripts.learnx_dk.pathlib.Path.home", return_value=home),
        patch("scripts.learnx_dk._load_config", return_value=_DEFAULTS),
        patch("scripts.learnx_dk.run_implement") as mock_impl,
    ):
        main(["--serve", "--dry-run"])
    mock_impl.assert_called_once()
    call_extra = mock_impl.call_args.kwargs.get(
        "extra_args",
        mock_impl.call_args.args[4] if len(mock_impl.call_args.args) > 4 else [],
    )
    assert "--serve" not in call_extra


def test_port_flag_consumed_from_extra(dirs, capsys):
    """--port N must not be forwarded to Claude."""
    project, home = dirs
    with (
        patch("scripts.learnx_dk.pathlib.Path.cwd", return_value=project),
        patch("scripts.learnx_dk.pathlib.Path.home", return_value=home),
        patch("scripts.learnx_dk._load_config", return_value=_DEFAULTS),
        patch("scripts.learnx_dk.run_implement") as mock_impl,
    ):
        main(["--port", "9090", "--dry-run"])
    mock_impl.assert_called_once()
    call_extra = mock_impl.call_args.kwargs.get(
        "extra_args",
        mock_impl.call_args.args[4] if len(mock_impl.call_args.args) > 4 else [],
    )
    assert "--port" not in call_extra
    assert "9090" not in call_extra


def test_run_with_timeout_tees_to_output_buffer():
    """Lines produced by the subprocess are written to the OutputBuffer."""
    buf = OutputBuffer()
    cmd = [sys.executable, "-c", "print('hello-from-container')"]
    rc, lines, timed_out = _run_with_timeout(
        cmd, session_timeout_s=30.0, idle_timeout_s=0, output_buffer=buf
    )
    assert rc == 0
    assert any("hello-from-container" in ln for ln in buf.lines())


def test_run_yolo_version_with_serve_starts_and_stops_server(tmp_path, dirs):
    """Dashboard server is started and stopped around the version loop."""
    _project, home = dirs
    ver_dir = tmp_path / "specs" / "v5"
    ver_dir.mkdir(parents=True)
    (ver_dir / "day1.md").write_text("# day1")

    started: list[bool] = []
    stopped: list[bool] = []

    class _FakeServer:
        def start(self) -> None:
            started.append(True)

        def stop(self) -> None:
            stopped.append(True)

        def update(self, *a: object, **kw: object) -> None:
            pass

    with (
        patch("scripts.dk.runners.DashboardServer", return_value=_FakeServer()),
        patch("scripts.dk.runners._checkout_spec_branch", return_value=True),
        patch("scripts.dk.runners._run_with_timeout", return_value=(0, [], False)),
    ):
        run_yolo_version(
            tmp_path,
            home,
            "v5",
            review=False,
            extra_args=[],
            dry_run=False,
            config={**_DEFAULTS},
            serve=True,
            port=18888,
        )

    assert started == [True]
    assert stopped == [True]
