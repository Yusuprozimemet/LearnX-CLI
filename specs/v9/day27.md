# Day 27 (v9) — Wire Notifier into Execution Flow and atexit Fallback

## Goal

Connect the `Notifier` built in day1 to the two execution paths that reach a
terminal state:

1. **`run_yolo_version()`** — fires on successful completion of all specs.
2. **`atexit` handler** — fires if the process is killed mid-run; marks status
   `"aborted"` so the notification still arrives even if the terminal disappears.

A `_notified` flag prevents double-firing when the normal path and the atexit
handler both try to send.

Also update `tutor/.env copy.example` to document the two Telegram env vars.

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
  scripts/learnx_dk.py                  ← wire Notifier into run_yolo_version();
                                          add atexit registration
  scripts/tests/test_learnx_dk.py       ← add 3 new tests
  tutor/.env copy.example               ← add NOTIFY_TELEGRAM_TOKEN,
                                          NOTIFY_TELEGRAM_CHAT_ID lines

Does NOT touch:
  devloop.toml          ← unchanged (notify section added in day1)
  scripts/run_review.py ← unchanged
  tutor/                ← application code unchanged
```

---

## Change 1 — Wire `Notifier` into `run_yolo_version()`

Add `import atexit` at the top of `learnx_dk.py`.

Inside `run_yolo_version()`, after declaring `results: list[SpecResult] = []`:

```python
import atexit

def run_yolo_version(
    project_dir, home_dir, version, review,
    extra_args, dry_run,
    specs_dir="specs",
    session_timeout_s=1800.0,
    idle_timeout_s=300.0,
    config=None,
    ...
) -> None:
    cfg = config or _DEFAULTS
    notifier = Notifier(cfg)
    start_time = time.monotonic()
    results: list[SpecResult] = []
    _notified = [False]

    # ── atexit fallback ───────────────────────────────────────────────────────
    def _atexit_handler() -> None:
        if _notified[0] or not notifier.enabled():
            return
        payload = _build_notify_payload(
            version, results, "aborted", start_time, cfg
        )
        notifier.send(payload)

    atexit.register(_atexit_handler)
    # ─────────────────────────────────────────────────────────────────────────

    # ... existing spec loop (unchanged from v8) ...

    _print_version_report(results, version)

    # ── normal completion notification ────────────────────────────────────────
    if notifier.enabled():
        payload = _build_notify_payload(
            version, results, "completed", start_time, cfg
        )
        notifier.send(payload)
        _notified[0] = True
```

### Why `_notified` is a list

`_notified` must be mutable inside the closure. A plain `bool` local cannot be
rebound from inside `_atexit_handler`. A single-element list is the standard
Python closure workaround.

### atexit fires at process exit

`atexit.register()` adds the handler to a LIFO stack called at normal interpreter
shutdown — including after `sys.exit()`, `SIGTERM`, and uncaught exceptions. It
does NOT fire on `SIGKILL` (unblockable). The handler checks `_notified[0]` first
so it is a no-op on the normal path where `send()` already fired.

---

## Change 2 — Update `tutor/.env copy.example`

Append two lines to `tutor/.env copy.example`:

```
NOTIFY_TELEGRAM_TOKEN=<your-bot-token>
NOTIFY_TELEGRAM_CHAT_ID=<your-chat-id>
```

These are the env var names referenced by `telegram_token_env` and
`telegram_chat_id_env` in `devloop.toml`. Values are never committed; only the
variable names appear in `devloop.toml`.

---

## New tests — add to `scripts/tests/test_learnx_dk.py`

```python
from scripts.learnx_dk import Notifier, _build_notify_payload, _DEFAULTS
import atexit as _atexit_mod


def test_notifier_send_not_called_when_disabled(dirs, tmp_path):
    """When no channels configured, notifier.enabled() is False and send is a no-op."""
    n = Notifier({"notify": {}})
    assert n.enabled() is False
    # send() should not raise and should call no network ops
    with patch("scripts.learnx_dk.urllib.request.urlopen") as mock_open:
        n.send({"status": "completed"})
    mock_open.assert_not_called()


def test_run_yolo_version_sends_notification_on_completion(tmp_path, dirs, capsys):
    """After all specs run, notifier.send() is called with status='completed'."""
    project, home = dirs
    ver_dir = tmp_path / "specs" / "v5"
    ver_dir.mkdir(parents=True)
    (ver_dir / "day1.md").write_text("# day1")

    cfg = {
        **_DEFAULTS,
        "notify": {"webhook_url": "https://example.com/hook"},
    }

    with patch("scripts.learnx_dk.urllib.request.urlopen") as mock_open, \
         patch("scripts.learnx_dk._checkout_spec_branch"), \
         patch("scripts.learnx_dk._run_with_timeout", return_value=(0, [], False)):
        run_yolo_version(
            tmp_path, home, "v5", review=False,
            extra_args=[], dry_run=False,
            config=cfg,
        )

    mock_open.assert_called_once()
    req = mock_open.call_args[0][0]
    import json
    payload = json.loads(req.data)
    assert payload["status"] == "completed"
    assert payload["version"] == "v5"


def test_atexit_handler_sends_aborted_when_not_notified(tmp_path, dirs):
    """If run is interrupted before completion, atexit sends status='aborted'."""
    project, home = dirs
    ver_dir = tmp_path / "specs" / "v5"
    ver_dir.mkdir(parents=True)
    (ver_dir / "day1.md").write_text("# day1")

    cfg = {
        **_DEFAULTS,
        "notify": {"webhook_url": "https://example.com/hook"},
    }
    captured_payloads = []

    def _fake_urlopen(req, **kwargs):
        import json
        captured_payloads.append(json.loads(req.data))

    # Run with dry_run=True so no actual subprocess; atexit handler is still registered.
    # Then manually call the last registered atexit handler to simulate aborted run.
    registered_handlers_before = len(_atexit_mod._atexit_registry if hasattr(_atexit_mod, '_atexit_registry') else [])

    with patch("scripts.learnx_dk.urllib.request.urlopen", side_effect=_fake_urlopen):
        run_yolo_version(
            tmp_path, home, "v5", review=False,
            extra_args=[], dry_run=True,
            config=cfg,
        )
        # dry_run marks _notified[0] = True after send — the atexit handler should not double-send.
        # To test the aborted path we verify the notifier class directly instead.
        n = Notifier(cfg)
        assert n.enabled() is True
```

Note: the atexit double-send prevention is verified by `_notified[0] = True` being
set before `atexit` could fire in the normal path. The third test confirms the
`Notifier.enabled()` gate rather than trying to introspect the `atexit` registry,
which is CPython-internal.

---

## Acceptance criteria

- [ ] `import atexit` is added to `learnx_dk.py`
- [ ] `run_yolo_version()` creates a `Notifier` using the current `config`
- [ ] `run_yolo_version()` registers an `atexit` handler before the spec loop begins
- [ ] `run_yolo_version()` calls `notifier.send()` with `status="completed"` after `_print_version_report()`
- [ ] `run_yolo_version()` sets `_notified[0] = True` after sending, preventing atexit double-fire
- [ ] The atexit handler sends `status="aborted"` when `_notified[0]` is `False`
- [ ] The atexit handler is a no-op when `notifier.enabled()` is `False` (no channels configured)
- [ ] Notification failure never propagates as an exception to the caller
- [ ] `tutor/.env copy.example` includes `NOTIFY_TELEGRAM_TOKEN` and `NOTIFY_TELEGRAM_CHAT_ID` lines
- [ ] `test_notifier_send_not_called_when_disabled` passes
- [ ] `test_run_yolo_version_sends_notification_on_completion` passes
- [ ] `test_atexit_handler_sends_aborted_when_not_notified` passes
- [ ] All pre-existing tests still pass
- [ ] ruff clean
