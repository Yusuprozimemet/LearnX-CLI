import json
import logging
import re
import time
import tomllib
from pathlib import Path

from openai import OpenAI

from tutor.config import Config
from tutor.exceptions import ConfigError, LLMError

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config loading — reads tutor/llm_config.toml at import time
# ---------------------------------------------------------------------------

_CONFIG_PATH = Path(__file__).parent.parent / "llm_config.toml"


def _load() -> dict:
    with open(_CONFIG_PATH, "rb") as fh:
        return tomllib.load(fh)


_cfg = _load()

# Public dicts built from the TOML — used by chat() below and exported for
# other modules that need to read limits (dialogue.py, summarizer.py).
MODEL_MAP: dict[tuple[str, str], str] = {
    (provider, call_type): model
    for provider, calls in _cfg["providers"].items()
    for call_type, model in calls.items()
}

MAX_TOKENS_MAP: dict[str, int] = _cfg["max_tokens"]
LIMITS: dict[str, int] = _cfg["limits"]

_temperature: float = _cfg["llm"]["temperature"]
_retry_count: int = _cfg["llm"]["retry_count"]
_retry_delay_s: float = _cfg["llm"]["retry_delay_s"]


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------


def _build_client(provider: str, config: Config) -> OpenAI:
    if provider == "groq":
        if not config.groq_api_key:
            raise ConfigError("GROQ_API_KEY not set. Add it to tutor/.env")
        return OpenAI(
            api_key=config.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
        )
    if provider == "openrouter":
        if not config.openrouter_api_key:
            raise ConfigError(
                "OPENROUTER_API_KEY not set.\n"
                "  Get a free key at openrouter.ai and add OPENROUTER_API_KEY to tutor/.env"
            )
        return OpenAI(
            api_key=config.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
            default_headers={"HTTP-Referer": "http://localhost"},
        )
    raise ConfigError(f"Unknown provider: {provider!r}. Use 'groq' or 'openrouter'.")


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------


def chat(
    messages: list[dict],
    config: Config,
    provider: str = "groq",
    call_type: str = "dialogue",
) -> str:
    model = MODEL_MAP.get((provider, call_type))
    if model is None:
        raise LLMError(f"No model configured for ({provider!r}, {call_type!r}) in llm_config.toml")

    client = _build_client(provider, config)
    log.debug("LLM call provider=%s call_type=%s model=%s", provider, call_type, model)

    max_tokens = MAX_TOKENS_MAP.get(call_type, 1_000)

    for attempt in range(_retry_count):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=_temperature,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content
            log.debug("LLM response (first 200 chars): %s", content[:200])
            return content
        except Exception as e:
            status = getattr(e, "status_code", None)
            if status in (400, 401, 403):
                raise LLMError(f"Auth/request error ({status}): {e}") from e
            if status == 413:
                raise LLMError(
                    f"Request too large for {model}.\n"
                    f"  Lower max_source_tokens or max_tokens.{call_type} in llm_config.toml."
                ) from e
            if attempt < _retry_count - 1:
                log.warning("LLM call failed (%s), retrying in %.1fs...", e, _retry_delay_s)
                time.sleep(_retry_delay_s)
                continue
            raise LLMError(f"LLM call failed after {_retry_count} attempts: {e}") from e

    raise LLMError("Unreachable")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse_json_response(raw: str) -> object:
    text = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"(\[.*\]|\{.*\})", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    raise LLMError(f"Could not parse JSON from response: {raw[:200]}")


def load_prompt(name: str) -> str:
    prompts_dir = Path(__file__).parent.parent / "prompts"
    return (prompts_dir / name).read_text(encoding="utf-8")
