# Day 26 (v9) — Notifier Class and Payload Builder

## Goal

Build the notification machinery: a `Notifier` class that fires best-effort messages
to three optional channels (webhook, Telegram, custom script) and a
`_build_notify_payload()` function that assembles the JSON payload from the
`SpecResult` list.

Nothing is wired into the execution flow yet — that is day2. This day creates and
tests the components in isolation.

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
  devloop.toml                          ← add commented-out [notify] section
  scripts/learnx_dk.py                  ← add _DEFAULTS["notify"], Notifier,
                                          _build_notify_payload()
  scripts/tests/test_learnx_dk.py       ← add 8 new tests

Does NOT touch:
  scripts/run_review.py       ← unchanged
  tutor/                      ← unchanged
  tutor/.env copy.example     ← updated in day2
```

---

## Change 1 — Add commented-out `[notify]` section to `devloop.toml`

Append to `devloop.toml` (existing file from v7/day1). The section is entirely
commented out so no channel fires until the user explicitly enables one:

```toml
# [notify]
# Credentials are NEVER stored here — list the env var name, not the value.
#
# Webhook — receives JSON POST on completion/failure
# webhook_url = "https://hooks.example.com/learnx"
#
# Telegram — reads token and chat_id from the named environment variables
# telegram_token_env = "NOTIFY_TELEGRAM_TOKEN"
# telegram_chat_id_env = "NOTIFY_TELEGRAM_CHAT_ID"
#
# Custom script — receives result JSON on stdin, exit code is ignored
# script = "scripts/notify.sh"
```

---

## Change 2 — Add `"notify"` to `_DEFAULTS` in `learnx_dk.py`

```python
_DEFAULTS: dict = {
    ...
    "notify": {
        "webhook_url": None,
        "telegram_token_env": None,
        "telegram_chat_id_env": None,
        "script": None,
    },
}
```

`_load_config()` already merges all sections with defaults, so the `[notify]`
section is automatically optional — absent means all keys are `None`.

---

## Change 3 — Add `_build_notify_payload()`

```python
def _build_notify_payload(
    version: str,
    results: list[SpecResult],
    status: str,        # "completed" | "aborted"
    start_time: float,  # time.monotonic() value from run start
    config: dict,
) -> dict:
    done = sum(1 for r in results if r.status == "DONE")
    failed = sum(1 for r in results if r.status == "FAILED")
    timed_out = sum(1 for r in results if r.status == "TIMED_OUT")
    duration_minutes = int((time.monotonic() - start_time) / 60)
    return {
        "project": config.get("project", {}).get("name", "LearnX"),
        "version": version,
        "status": status,
        "specs_total": len(results),
        "specs_ready": done,
        "specs_failed": failed,
        "specs_timed_out": timed_out,
        "duration_minutes": duration_minutes,
        "branch_summary": [
            {"spec": r.spec_name, "status": r.status, "branch": r.branch}
            for r in results
        ],
    }
```

---

## Change 4 — Add `Notifier` class

Place after `_build_notify_payload()`. Uses only stdlib: `json`, `os`,
`urllib.request`, `urllib.parse`, `subprocess` (already imported).

```python
import json as _json
import urllib.parse
import urllib.request


class Notifier:
    """Best-effort multi-channel notifier. Never raises; logs failures to stdout."""

    def __init__(self, config: dict) -> None:
        notify = config.get("notify", {})
        self._webhook_url: str | None = notify.get("webhook_url")
        self._tg_token_env: str | None = notify.get("telegram_token_env")
        self._tg_chat_env: str | None = notify.get("telegram_chat_id_env")
        self._script: str | None = notify.get("script")

    def enabled(self) -> bool:
        """True if at least one channel is configured."""
        return bool(self._webhook_url or self._tg_token_env or self._script)

    def send(self, payload: dict) -> None:
        """Fire all configured channels. Exceptions are caught and logged."""
        if self._webhook_url:
            self._send_webhook(payload)
        if self._tg_token_env:
            self._send_telegram(payload)
        if self._script:
            self._send_script(payload)

    # ── channels ──────────────────────────────────────────────────────────────

    def _send_webhook(self, payload: dict) -> None:
        try:
            data = _json.dumps(payload).encode()
            req = urllib.request.Request(
                self._webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=10)
            print("[notify] webhook sent", flush=True)
        except Exception as exc:
            print(f"[notify] webhook failed: {exc}", flush=True)

    def _send_telegram(self, payload: dict) -> None:
        try:
            token = os.environ.get(self._tg_token_env or "", "")
            chat_id = os.environ.get(self._tg_chat_env or "", "")
            if not token or not chat_id:
                print(
                    f"[notify] telegram: env vars "
                    f"{self._tg_token_env!r} / {self._tg_chat_env!r} not set",
                    flush=True,
                )
                return
            text = self._format_telegram(payload)
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
            urllib.request.urlopen(url, data=data, timeout=10)
            print("[notify] telegram sent", flush=True)
        except Exception as exc:
            print(f"[notify] telegram failed: {exc}", flush=True)

    def _send_script(self, payload: dict) -> None:
        try:
            data = _json.dumps(payload).encode()
            subprocess.run(
                [self._script],
                input=data,
                timeout=30,
                check=False,
            )
            print(f"[notify] script {self._script!r} called", flush=True)
        except Exception as exc:
            print(f"[notify] script failed: {exc}", flush=True)

    # ── formatting ────────────────────────────────────────────────────────────

    def _format_telegram(self, payload: dict) -> str:
        project = payload.get("project", "LearnX")
        version = payload.get("version", "?")
        total = payload.get("specs_total", 0)
        done = payload.get("specs_ready", 0)
        failed = payload.get("specs_failed", 0)
        timed_out = payload.get("specs_timed_out", 0)
        mins = payload.get("duration_minutes", 0)
        h, m = divmod(mins, 60)
        duration = f"{h}h{m:02d}m" if h else f"{m}m"

        if failed == 0 and timed_out == 0:
            icon, headline = "✓", f"{project} {version} complete"
        else:
            icon, headline = "✗", f"{project} {version} — NEEDS ATTENTION"

        parts = [f"{done}/{total} specs done"]
        if failed:
            parts.append(f"{failed} failed")
        if timed_out:
            parts.append(f"{timed_out} timed out")
        parts.append(duration)
        return f"{icon} {headline}\n{' · '.join(parts)}"
```

---

## New tests — add to `scripts/tests/test_learnx_dk.py`

```python
import json
from unittest.mock import MagicMock, patch

from scripts.learnx_dk import Notifier, SpecResult, _build_notify_payload


# ── payload ──────────────────────────────────────────────────────────────────

def test_build_notify_payload_structure():
    results = [
        SpecResult("day1", "DONE", 60.0, "sandbox/v5-day1"),
        SpecResult("day2", "FAILED", 30.0, "sandbox/v5-day2"),
        SpecResult("day3", "TIMED_OUT", 1800.0, "sandbox/v5-day3"),
    ]
    import time
    start = time.monotonic() - 120   # pretend 2 minutes ago
    payload = _build_notify_payload("v5", results, "completed", start, _DEFAULTS)
    assert payload["version"] == "v5"
    assert payload["specs_total"] == 3
    assert payload["specs_ready"] == 1
    assert payload["specs_failed"] == 1
    assert payload["specs_timed_out"] == 1
    assert payload["status"] == "completed"
    assert len(payload["branch_summary"]) == 3


# ── Notifier.enabled ─────────────────────────────────────────────────────────

def test_notifier_disabled_when_no_channels_configured():
    n = Notifier({"notify": {}})
    assert n.enabled() is False


def test_notifier_enabled_when_webhook_configured():
    n = Notifier({"notify": {"webhook_url": "https://example.com/hook"}})
    assert n.enabled() is True


# ── Notifier.send ─────────────────────────────────────────────────────────────

def test_notifier_webhook_posts_json(capsys):
    n = Notifier({"notify": {"webhook_url": "https://example.com/hook"}})
    with patch("scripts.learnx_dk.urllib.request.urlopen") as mock_open:
        n.send({"status": "completed"})
    mock_open.assert_called_once()
    req = mock_open.call_args[0][0]
    body = json.loads(req.data)
    assert body["status"] == "completed"


def test_notifier_webhook_failure_does_not_raise(capsys):
    n = Notifier({"notify": {"webhook_url": "https://example.com/hook"}})
    with patch("scripts.learnx_dk.urllib.request.urlopen", side_effect=OSError("no network")):
        n.send({"status": "completed"})   # must not raise
    out = capsys.readouterr().out
    assert "webhook failed" in out


def test_notifier_telegram_skips_when_env_unset(capsys, monkeypatch):
    monkeypatch.delenv("MY_TOKEN", raising=False)
    n = Notifier({"notify": {"telegram_token_env": "MY_TOKEN",
                              "telegram_chat_id_env": "MY_CHAT"}})
    n._send_telegram({"status": "completed"})
    out = capsys.readouterr().out
    assert "not set" in out


def test_format_telegram_success_message():
    n = Notifier({})
    payload = {
        "project": "LearnX", "version": "v5", "specs_total": 5,
        "specs_ready": 5, "specs_failed": 0, "specs_timed_out": 0,
        "duration_minutes": 214,
    }
    msg = n._format_telegram(payload)
    assert "✓" in msg
    assert "v5 complete" in msg
    assert "3h34m" in msg


def test_format_telegram_failure_message():
    n = Notifier({})
    payload = {
        "project": "LearnX", "version": "v5", "specs_total": 5,
        "specs_ready": 3, "specs_failed": 1, "specs_timed_out": 1,
        "duration_minutes": 60,
    }
    msg = n._format_telegram(payload)
    assert "✗" in msg
    assert "NEEDS ATTENTION" in msg
    assert "1 failed" in msg
    assert "1 timed out" in msg
```

---

## Acceptance criteria

- [ ] `devloop.toml` has a fully-commented `[notify]` section (no channel fires by default)
- [ ] `_DEFAULTS["notify"]` has `webhook_url`, `telegram_token_env`, `telegram_chat_id_env`, `script` all `None`
- [ ] `_build_notify_payload()` returns correct counts for DONE / FAILED / TIMED_OUT
- [ ] `_build_notify_payload()` includes `branch_summary` list with one entry per result
- [ ] `Notifier.enabled()` returns `False` when no channels are configured
- [ ] `Notifier.enabled()` returns `True` when any channel is configured
- [ ] `Notifier._send_webhook()` makes an HTTP POST with `Content-Type: application/json`
- [ ] `Notifier._send_webhook()` catches exceptions and logs to stdout; never raises
- [ ] `Notifier._send_telegram()` logs a warning when env vars are absent; never raises
- [ ] `Notifier._send_script()` calls subprocess with JSON on stdin; catches exceptions
- [ ] `Notifier._format_telegram()` returns `✓ … complete` when no failures
- [ ] `Notifier._format_telegram()` returns `✗ … NEEDS ATTENTION` when failures > 0
- [ ] `Notifier._format_telegram()` formats duration as `3h34m` for 214 minutes
- [ ] All 8 new tests pass
- [ ] All pre-existing tests still pass
- [ ] ruff clean
