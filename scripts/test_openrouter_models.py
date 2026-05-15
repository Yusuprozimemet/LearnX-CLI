#!/usr/bin/env python3
"""
Test free OpenRouter models for LearnX pipeline compatibility.

Two checks per model:
  JSON  — returns a valid JSON array  (required by curriculum + visual planners)
  DIAL  — follows SPEAKER: text format (required by dialogue generator)

Usage:
    python scripts/test_openrouter_models.py           # full test, all models
    python scripts/test_openrouter_models.py --quick   # JSON check only (faster)
    python scripts/test_openrouter_models.py --model meta-llama/llama-3.3-70b-instruct:free
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).parent.parent / "tutor" / ".env")

API_KEY = os.getenv("OPENROUTER_API_KEY", "")
if not API_KEY:
    print("Error: OPENROUTER_API_KEY not set in tutor/.env")
    sys.exit(1)

CLIENT = OpenAI(
    api_key=API_KEY,
    base_url="https://openrouter.ai/api/v1",
    default_headers={"HTTP-Referer": "http://localhost"},
    timeout=60.0,
)

# ── Models from tutor/models.md (free tier, May 2026) ────────────────────────
# Skipped: embed model (Nemotron Embed VL 1B), tiny models (<5B), Free Router.
# IDs are best-guess from display names — 404 means the slug needs updating.
MODELS = [
    "poolside/laguna-m.1:free",
    "openai/gpt-oss-120b:free",
    "z-ai/glm-4.5-air:free",
    "minimax/minimax-m2.5:free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "poolside/laguna-xs.2:free",
    "openai/gpt-oss-20b:free",
    "baidu/qianfan-cobuddy:free",
    "arcee-ai/trinity-large-thinking:free",   # thinking model — may return empty content
    "nvidia/nemotron-3-nano-omni:free",
    "deepseek/deepseek-v4-flash:free",        # fast but known bad JSON
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-nano-12b-2-vl:free",
    "nvidia/nemotron-nano-9b-v2:free",
    "google/gemma-4-26b-a4b:free",
    "qwen/qwen3-coder-480b-a35b:free",
    "qwen/qwen3-80b-a3b:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "nousresearch/hermes-3-405b-instruct:free",
]

# ── Prompts (minimal versions of what the real pipeline sends) ────────────────

JSON_PROMPT = """\
Return a JSON array of 3 teaching units about Java collections.
Each object must have exactly these fields:
  "concept"    : string  — topic name
  "complexity" : integer — 1, 2, or 3
  "key_facts"  : array of 2 strings

Reply with the raw JSON array only. No markdown, no explanation."""

DIALOGUE_PROMPT = """\
Write 4 lines of educational dialogue about Java ArrayLists.
Format every line exactly as:   SPEAKER: text
Use only TUTOR and STUDENT as speakers, alternating, starting with TUTOR."""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _call(model: str, prompt: str, max_tokens: int, temperature: float) -> tuple[str, float]:
    """Return (content, elapsed_s). Raises on API or empty-content errors."""
    t0 = time.time()
    resp = CLIENT.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    elapsed = time.time() - t0
    content = resp.choices[0].message.content or ""
    # Thinking models wrap reasoning in <think>…</think>; strip it to get final answer.
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    return content, elapsed


def _strip_fences(text: str) -> str:
    return text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()


# ── Check functions ───────────────────────────────────────────────────────────

def check_json(model: str) -> tuple[bool, float, str]:
    """(passed, elapsed_s, note)"""
    try:
        content, elapsed = _call(model, JSON_PROMPT, max_tokens=600, temperature=0.2)
        if not content:
            return False, elapsed, "empty response"
        data = json.loads(_strip_fences(content))
        if not isinstance(data, list) or not data:
            return False, elapsed, "not a JSON array"
        if "concept" not in data[0]:
            return False, elapsed, "missing 'concept' field"
        return True, elapsed, f"{len(data)} units returned"
    except json.JSONDecodeError as e:
        return False, 0.0, f"invalid JSON: {str(e)[:40]}"
    except Exception as e:
        code = getattr(e, "status_code", None)
        if code == 404:
            return False, 0.0, "404 — wrong model ID or removed"
        if code == 429:
            return False, 0.0, "429 — rate limited"
        return False, 0.0, str(e)[:55]


def check_dialogue(model: str) -> tuple[bool, float, str]:
    """(passed, elapsed_s, note)"""
    try:
        content, elapsed = _call(model, DIALOGUE_PROMPT, max_tokens=300, temperature=0.7)
        if not content:
            return False, elapsed, "empty response"
        lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
        speaker_lines = [
            ln for ln in lines
            if re.match(r"^(TUTOR|STUDENT)\s*:", ln, re.IGNORECASE)
        ]
        if len(speaker_lines) < 2:
            return False, elapsed, f"only {len(speaker_lines)} speaker line(s) found"
        return True, elapsed, f"{len(speaker_lines)} lines"
    except Exception as e:
        code = getattr(e, "status_code", None)
        if code == 404:
            return False, 0.0, "404 — wrong model ID or removed"
        if code == 429:
            return False, 0.0, "429 — rate limited"
        return False, 0.0, str(e)[:55]


# ── Report ────────────────────────────────────────────────────────────────────

PASS = "PASS"
FAIL = "FAIL"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quick", action="store_true", help="JSON check only")
    parser.add_argument("--model", help="Test a single model slug")
    args = parser.parse_args()

    models = [args.model] if args.model else MODELS

    col_model = 48
    header = f"{'Model':<{col_model}}  {'JSON':>4}  {'t':>5}s"
    if not args.quick:
        header += f"  {'DIAL':>4}  {'t':>5}s"
    header += "  Notes"
    sep = "-" * 110
    print(f"\n{header}\n{sep}")

    passed_json = []
    passed_both = []

    for model in models:
        json_ok, json_t, json_note = check_json(model)

        if args.quick:
            dial_ok, dial_t, dial_note = False, 0.0, ""
        else:
            dial_ok, dial_t, dial_note = check_dialogue(model)

        row = f"{model:<{col_model}}  {PASS if json_ok else FAIL:>4}  {json_t:>5.1f}s"
        if not args.quick:
            row += f"  {PASS if dial_ok else FAIL:>4}  {dial_t:>5.1f}s"

        notes = []
        if not json_ok:
            notes.append(f"json: {json_note}")
        if not args.quick and not dial_ok:
            notes.append(f"dial: {dial_note}")
        if notes:
            row += f"  {' | '.join(notes)}"

        print(row)

        if json_ok:
            passed_json.append((model, json_t, dial_t if not args.quick else None))
        if json_ok and (args.quick or dial_ok):
            passed_both.append(model)

    print(sep)
    if passed_both:
        print(f"\nPASSED all checks ({len(passed_both)}):")
        for m in passed_both:
            t = next(t for mdl, t, _ in passed_json if mdl == m)
            print(f"  {m}  ({t:.1f}s JSON)")
    else:
        print("\nNO model passed all checks.")

    if passed_both:
        fastest = min(passed_both, key=lambda m: next(t for mdl, t, _ in passed_json if mdl == m))
        print(f"\n  Recommended for llm_config.toml: {fastest}")
    print()


if __name__ == "__main__":
    main()
