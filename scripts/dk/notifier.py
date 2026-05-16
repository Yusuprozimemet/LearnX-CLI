import json
import os
import subprocess
import time
import urllib.parse
import urllib.request


def _build_notify_payload(
    version: str,
    results: list,
    status: str,
    start_time: float,
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
            {"spec": r.spec_name, "status": r.status, "branch": r.branch} for r in results
        ],
    }


class Notifier:
    """Best-effort multi-channel notifier. Never raises; logs failures to stdout."""

    def __init__(self, config: dict) -> None:
        notify = config.get("notify", {})
        self._webhook_url: str | None = notify.get("webhook_url")
        self._tg_token_env: str | None = notify.get("telegram_token_env")
        self._tg_chat_env: str | None = notify.get("telegram_chat_id_env")
        self._script: str | None = notify.get("script")

    def enabled(self) -> bool:
        """True if at least one channel is fully configured."""
        telegram_ready = bool(self._tg_token_env and self._tg_chat_env)
        return bool(self._webhook_url or telegram_ready or self._script)

    def send(self, payload: dict) -> None:
        """Fire all configured channels. Exceptions are caught and logged."""
        if self._webhook_url:
            self._send_webhook(payload)
        if self._tg_token_env and self._tg_chat_env:
            self._send_telegram(payload)
        if self._script:
            self._send_script(payload)

    def _send_webhook(self, payload: dict) -> None:
        try:
            data = json.dumps(payload).encode()
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
            data = json.dumps(payload).encode()
            subprocess.run(
                [self._script],
                input=data,
                timeout=30,
                check=False,
            )
            print(f"[notify] script {self._script!r} called", flush=True)
        except Exception as exc:
            print(f"[notify] script failed: {exc}", flush=True)

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
