# LearnX v9 — Completion Notifications

## The problem with v8

v8 makes unattended version runs resilient. A 10-spec overnight run will complete
or fail gracefully without hanging. But the user still must actively check the
result:

- Open a terminal
- Navigate to the project
- Read the last output or check git log

"Walk away and come back" is only true walk-away if you are notified when it ends.
Without notification, "walk away" becomes "walk away and remember to check tomorrow
morning." The run might have finished at 2am or it might still be running — you
won't know until you look.

---

## How notifications work

Notifications are optional, best-effort, and configured in `devloop.toml`.
A failed notification never blocks or fails a spec run. Notifications fire once:
when the version run (or single-spec run) reaches a terminal state.

### Supported channels

| Channel | Config key | Notes |
|---|---|---|
| Webhook | `notify.webhook_url` | HTTP POST with JSON payload |
| Telegram | `notify.telegram_token_env` + `notify.telegram_chat_id_env` | Message to a bot |
| Custom script | `notify.script` | Called with result JSON as stdin |

```toml
[notify]
# Webhook — receives JSON POST on completion/failure
webhook_url = "https://hooks.example.com/learnx"

# Telegram — token and chat ID read from env vars (not stored in toml)
telegram_token_env = "NOTIFY_TELEGRAM_TOKEN"
telegram_chat_id_env = "NOTIFY_TELEGRAM_CHAT_ID"

# Custom script — receives result JSON on stdin
# script = "scripts/notify.sh"
```

Credentials are never stored in `devloop.toml` (which is committed). Token values
are read from environment variables whose names are listed in the config.

### Notification payload

```json
{
  "project": "LearnX",
  "version": "v5",
  "status": "completed",
  "specs_total": 10,
  "specs_ready": 9,
  "specs_failed": 0,
  "specs_timed_out": 1,
  "duration_minutes": 214,
  "branch_summary": [
    {"spec": "day1", "status": "MERGE READY", "branch": "sandbox/v5-day1"},
    {"spec": "day3", "status": "TIMED OUT", "branch": "sandbox/v5-day3"}
  ]
}
```

### Telegram message

On success:
```
✓ LearnX v5 complete
9/10 specs MERGE READY · 1 timed out · 3h34m
```

On failure:
```
✗ LearnX v5 — NEEDS ATTENTION
7/10 specs done · 2 failed · 1 timed out · 2h11m
```

### Notification timing

- Fires after the consolidated report is printed
- Uses `atexit` handler as fallback — fires even if the run is killed mid-way
- The atexit notification marks status as `aborted` if the run was not completed

---

## What changes

| Component | Change |
|---|---|
| `scripts/learnx_dk.py` | `Notifier` class: webhook, Telegram, custom-script channels |
| `scripts/learnx_dk.py` | `atexit` registration in `run_version()` and `run_spec()` |
| `devloop.toml` | `[notify]` section |
| `tutor/.env.example` | Document `NOTIFY_TELEGRAM_TOKEN`, `NOTIFY_TELEGRAM_CHAT_ID` |

---

## What does not change

- Nothing in the spec execution path changes
- Notifications never affect run outcome
- devloop.toml structure is additive (`[notify]` is a new section)
- All existing validation and review behavior unchanged

---

## Expected outcome

Add four lines to `devloop.toml`, set two env vars, start a version run before
bed. Wake up to a Telegram message: "9/10 specs MERGE READY · 3h34m". Open
the one PR with findings, fix it, merge the other nine. Done.
