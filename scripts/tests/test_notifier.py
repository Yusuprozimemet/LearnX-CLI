"""Tests for Notifier class, payload builder, and notification wiring (Day 26, 27)."""

import json
import pathlib
import time
from unittest.mock import patch

import pytest

from scripts.learnx_dk import (
    _DEFAULTS,
    Notifier,
    SpecResult,
    _build_notify_payload,
    main,
    run_yolo_version,
)


# ── Day 26 — payload and notifier ────────────────────────────────────────────


def test_build_notify_payload_structure():
    results = [
        SpecResult("day1", "DONE", 60.0, "sandbox/v5-day1"),
        SpecResult("day2", "FAILED", 30.0, "sandbox/v5-day2"),
        SpecResult("day3", "TIMED_OUT", 1800.0, "sandbox/v5-day3"),
    ]
    start = time.monotonic() - 120
    payload = _build_notify_payload("v5", results, "completed", start, _DEFAULTS)
    assert payload["version"] == "v5"
    assert payload["specs_total"] == 3
    assert payload["specs_ready"] == 1
    assert payload["specs_failed"] == 1
    assert payload["specs_timed_out"] == 1
    assert payload["status"] == "completed"
    assert len(payload["branch_summary"]) == 3


def test_notifier_disabled_when_no_channels_configured():
    n = Notifier({"notify": {}})
    assert n.enabled() is False


def test_notifier_enabled_when_webhook_configured():
    n = Notifier({"notify": {"webhook_url": "https://example.com/hook"}})
    assert n.enabled() is True


def test_notifier_enabled_false_with_only_telegram_token():
    """enabled() must require both token AND chat_id — partial config is not enough."""
    n = Notifier({"notify": {"telegram_token_env": "MY_TOKEN"}})
    assert n.enabled() is False


def test_notifier_webhook_posts_json():
    n = Notifier({"notify": {"webhook_url": "https://example.com/hook"}})
    with patch("scripts.dk.notifier.urllib.request.urlopen") as mock_open:
        n.send({"status": "completed"})
    mock_open.assert_called_once()
    req = mock_open.call_args[0][0]
    body = json.loads(req.data)
    assert body["status"] == "completed"


def test_notifier_webhook_failure_does_not_raise(capsys):
    n = Notifier({"notify": {"webhook_url": "https://example.com/hook"}})
    with patch(
        "scripts.dk.notifier.urllib.request.urlopen", side_effect=OSError("no network")
    ):
        n.send({"status": "completed"})
    out = capsys.readouterr().out
    assert "webhook failed" in out


def test_notifier_telegram_skips_when_env_unset(capsys, monkeypatch):
    monkeypatch.delenv("MY_TOKEN", raising=False)
    n = Notifier({"notify": {"telegram_token_env": "MY_TOKEN", "telegram_chat_id_env": "MY_CHAT"}})
    n._send_telegram({"status": "completed"})
    out = capsys.readouterr().out
    assert "not set" in out


def test_format_telegram_success_message():
    n = Notifier({})
    payload = {
        "project": "LearnX",
        "version": "v5",
        "specs_total": 5,
        "specs_ready": 5,
        "specs_failed": 0,
        "specs_timed_out": 0,
        "duration_minutes": 214,
    }
    msg = n._format_telegram(payload)
    assert "✓" in msg
    assert "v5 complete" in msg
    assert "3h34m" in msg


def test_format_telegram_failure_message():
    n = Notifier({})
    payload = {
        "project": "LearnX",
        "version": "v5",
        "specs_total": 5,
        "specs_ready": 3,
        "specs_failed": 1,
        "specs_timed_out": 1,
        "duration_minutes": 60,
    }
    msg = n._format_telegram(payload)
    assert "✗" in msg
    assert "NEEDS ATTENTION" in msg
    assert "1 failed" in msg
    assert "1 timed out" in msg


def test_run_yolo_version_calls_notifier_on_completion(tmp_path):
    (tmp_path / "specs" / "v9").mkdir(parents=True)
    (tmp_path / "specs" / "v9" / "day1.md").write_text("spec")

    config = {**_DEFAULTS, "notify": {"webhook_url": "https://example.com/hook"}}

    with (
        patch("scripts.dk.runners._checkout_spec_branch", return_value=True),
        patch("scripts.dk.runners._run_with_timeout", return_value=(0, [], False)),
        patch("scripts.dk.notifier.Notifier.send") as mock_send,
    ):
        run_yolo_version(
            tmp_path,
            pathlib.Path.home(),
            "v9",
            review=False,
            extra_args=[],
            dry_run=False,
            config=config,
        )

    mock_send.assert_called_once()
    payload = mock_send.call_args[0][0]
    assert payload["version"] == "v9"
    assert payload["status"] == "completed"


def test_main_calls_notifier_after_run_implement(tmp_path):
    """main() must call Notifier.send() after run_implement() when a channel is configured."""
    toml_content = (
        "[project]\n"
        'name = "TestProj"\n'
        'docker_image = "img"\n'
        'workspace = "/ws"\n'
        'specs_dir = "specs"\n'
        "[notify]\n"
        'webhook_url = "https://example.com/hook"\n'
    )
    (tmp_path / "devloop.toml").write_text(toml_content)

    with (
        patch("scripts.learnx_dk.pathlib.Path.cwd", return_value=tmp_path),
        patch("scripts.learnx_dk.run_implement"),
        patch("scripts.dk.notifier.Notifier.send") as mock_send,
    ):
        main([])

    mock_send.assert_called_once()
    payload = mock_send.call_args[0][0]
    assert payload["status"] == "completed"


# ── Day 27 — atexit fallback ──────────────────────────────────────────────────


def test_notifier_send_not_called_when_disabled():
    """When no channels configured, send() is a no-op — no network calls made."""
    n = Notifier({"notify": {}})
    assert n.enabled() is False
    with patch("scripts.dk.notifier.urllib.request.urlopen") as mock_open:
        n.send({"status": "completed"})
    mock_open.assert_not_called()


def test_run_yolo_version_sends_notification_on_completion(tmp_path, dirs):
    """After all specs run, notifier fires via urlopen with status='completed'."""
    project, home = dirs
    ver_dir = tmp_path / "specs" / "v5"
    ver_dir.mkdir(parents=True)
    (ver_dir / "day1.md").write_text("# day1")

    cfg = {**_DEFAULTS, "notify": {"webhook_url": "https://example.com/hook"}}

    with (
        patch("scripts.dk.notifier.urllib.request.urlopen") as mock_open,
        patch("scripts.dk.runners._checkout_spec_branch", return_value=True),
        patch("scripts.dk.runners._run_with_timeout", return_value=(0, [], False)),
    ):
        run_yolo_version(
            tmp_path, home, "v5", review=False, extra_args=[], dry_run=False, config=cfg
        )

    mock_open.assert_called_once()
    payload = json.loads(mock_open.call_args[0][0].data)
    assert payload["status"] == "completed"
    assert payload["version"] == "v5"


def test_atexit_handler_sends_aborted_when_not_notified(tmp_path, dirs):
    """atexit handler fires with status='aborted' when run is interrupted before completion."""
    project, home = dirs
    ver_dir = tmp_path / "specs" / "v5"
    ver_dir.mkdir(parents=True)
    (ver_dir / "day1.md").write_text("# day1")

    cfg = {**_DEFAULTS, "notify": {"webhook_url": "https://example.com/hook"}}
    captured_handler = []

    with (
        patch("atexit.register", side_effect=lambda fn: captured_handler.append(fn)),
        patch(
            "scripts.dk.runners._checkout_spec_branch",
            side_effect=RuntimeError("simulated abort"),
        ),
        patch("scripts.dk.notifier.urllib.request.urlopen") as mock_open,
    ):
        with pytest.raises(RuntimeError):
            run_yolo_version(
                tmp_path, home, "v5", review=False, extra_args=[], dry_run=False, config=cfg
            )

        assert len(captured_handler) == 1
        captured_handler[0]()
        mock_open.assert_called_once()
        payload = json.loads(mock_open.call_args[0][0].data)
        assert payload["status"] == "aborted"


def test_completion_notification_skipped_in_dry_run(tmp_path, dirs):
    """dry_run=True must not send a completion notification."""
    project, home = dirs
    ver_dir = tmp_path / "specs" / "v5"
    ver_dir.mkdir(parents=True)
    (ver_dir / "day1.md").write_text("# day1")

    cfg = {**_DEFAULTS, "notify": {"webhook_url": "https://example.com/hook"}}

    with patch("scripts.dk.notifier.urllib.request.urlopen") as mock_open:
        run_yolo_version(
            tmp_path, home, "v5", review=False, extra_args=[], dry_run=True, config=cfg
        )

    mock_open.assert_not_called()


def test_atexit_handler_skipped_in_dry_run(tmp_path, dirs):
    """atexit handler must not send an abort notification when dry_run=True."""
    project, home = dirs
    ver_dir = tmp_path / "specs" / "v5"
    ver_dir.mkdir(parents=True)
    (ver_dir / "day1.md").write_text("# day1")

    cfg = {**_DEFAULTS, "notify": {"webhook_url": "https://example.com/hook"}}
    captured_handler = []

    with (
        patch("atexit.register", side_effect=lambda fn: captured_handler.append(fn)),
        patch("scripts.dk.notifier.urllib.request.urlopen") as mock_open,
    ):
        run_yolo_version(
            tmp_path, home, "v5", review=False, extra_args=[], dry_run=True, config=cfg
        )

        assert len(captured_handler) == 1
        captured_handler[0]()
        mock_open.assert_not_called()
