import json
import logging
import re
import time
from pathlib import Path

from openai import OpenAI

from tutor.config import Config
from tutor.exceptions import ConfigError, LLMError

log = logging.getLogger(__name__)

MODEL_MAP = {
    ("groq", "curriculum"): "llama-3.3-70b-versatile",
    ("groq", "dialogue"): "llama-3.1-8b-instant",
    ("groq", "summarize"): "llama-3.1-8b-instant",
    ("groq", "qa"): "llama-3.1-8b-instant",
    ("openrouter", "curriculum"): "google/gemma-3-27b-it:free",
    ("openrouter", "dialogue"): "meta-llama/llama-3.1-8b-instruct:free",
    ("openrouter", "summarize"): "meta-llama/llama-3.1-8b-instruct:free",
    ("openrouter", "qa"): "meta-llama/llama-3.1-8b-instruct:free",
}

# Max *response* tokens per call type — keeps total request well under the
# Groq free-tier 6 k-token-per-request cap (input + output combined).
MAX_TOKENS_MAP = {
    "curriculum": 2_000,
    "dialogue":   1_500,
    "summarize":  400,
    "qa":         600,
}


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


def chat(
    messages: list[dict],
    config: Config,
    provider: str = "groq",
    call_type: str = "dialogue",
) -> str:
    model = MODEL_MAP.get((provider, call_type))
    if model is None:
        raise LLMError(f"No model configured for ({provider}, {call_type})")

    client = _build_client(provider, config)
    log.debug("LLM call provider=%s call_type=%s model=%s", provider, call_type, model)

    max_tokens = MAX_TOKENS_MAP.get(call_type, 1_000)

    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7,
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
                    f"Request too large for {model} — reduce source text or word budget. ({e})"
                ) from e
            if attempt == 0:
                log.warning("LLM call failed (%s), retrying in 2s...", e)
                time.sleep(2)
                continue
            raise LLMError(f"LLM call failed after retry: {e}") from e

    raise LLMError("Unreachable")


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
