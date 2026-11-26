#---------------------beginning-of-code------------------------#
#--------------------------------------------------------------#

# File: visuals/llm.py
# Purpose: the only place that talks to the LLM (same pattern as the content suggester).
#   call_llm(task, prompt, schema, tier, check)
#     1. asks the model for JSON matching the Pydantic schema
#     2. validates it, then runs `check` (extra rules, e.g. "only numbers from the sources")
#     3. on a problem sends it back and retries (max 2 retries)
#     4. logs tokens and cost to logs/llm_calls.csv
#   Returns (result, warnings): warnings = check problems still left after the last retry.
#
#   Two tiers, set in .env:
#     LLM_MODEL_FAST  (cheap: short, structured posts)   e.g. anthropic/claude-haiku-5-5
#     LLM_MODEL_SMART (storytelling: explainers, videos) e.g. anthropic/claude-sonnet-5-5
#     (either falls back to LLM_MODEL). Prices: LLM_PRICE_<FAST|SMART>_<INPUT|OUTPUT>_PER_MTOK.
#   Reaching the model:
#     - Gateway (Unoblox): LLM_BASE_URL=https://api.unoblox.ai/v1 and UNOBLOX_API_KEY
#     - Anthropic directly: leave LLM_BASE_URL unset and set ANTHROPIC_API_KEY
#--------------------------------------------------------------#

# Imports Libraries
import csv
import json
import os
from datetime import datetime
from typing import Callable, TypeVar

from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

from visuals.paths import ROOT
#--------------------------------------------------------------#

# Global variables and setup
load_dotenv(ROOT / ".env")
T = TypeVar("T", bound=BaseModel)
MAX_RETRIES = 2
LOG_FILE = ROOT / "logs" / "llm_calls.csv"
_client = None

SYSTEM = (
    "You write content specs for a branded video and image generator. "
    "Reply with a single JSON object that matches the JSON Schema below. "
    "No markdown, no code fences, no text before or after the JSON.\n\n"
    "JSON Schema:\n{schema}"
)


class LLMError(Exception):
    pass
#--------------------------------------------------------------#

# Model name and prices for a tier
def settings(tier: str) -> tuple[str, float, float]:
    key = tier.upper()
    model = os.environ.get(f"LLM_MODEL_{key}") or os.environ.get("LLM_MODEL")
    if not model:
        raise LLMError(f"Set LLM_MODEL_{key} (or LLM_MODEL) in .env, e.g. anthropic/claude-haiku-5-5")

    def price(kind: str) -> float:
        value = os.environ.get(f"LLM_PRICE_{key}_{kind}_PER_MTOK") or os.environ.get(f"LLM_PRICE_{kind}_PER_MTOK")
        return float(value or 0)
    return model, price("INPUT"), price("OUTPUT")
#--------------------------------------------------------------#

# Create the API client once: a gateway (OpenAI-style) if LLM_BASE_URL is set, else Anthropic
def _get_client():
    global _client
    if _client is None:
        base_url = os.environ.get("LLM_BASE_URL")
        if base_url:
            from openai import OpenAI
            api_key = os.environ.get("LLM_API_KEY") or os.environ.get("UNOBLOX_API_KEY")
            if not api_key:
                raise LLMError("LLM_BASE_URL is set but neither LLM_API_KEY nor UNOBLOX_API_KEY is")
            _client = ("gateway", OpenAI(base_url=base_url, api_key=api_key))
        else:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise LLMError("No LLM key: set LLM_BASE_URL + UNOBLOX_API_KEY, or ANTHROPIC_API_KEY")
            import anthropic
            _client = ("anthropic", anthropic.Anthropic())
    return _client


# One API call. Returns (text, input_tokens, output_tokens). Tests replace this with a fake.
def _send(model: str, system: str, messages: list[dict], max_tokens: int) -> tuple[str, int, int]:
    kind, client = _get_client()
    if kind == "gateway":
        resp = client.chat.completions.create(
            model=model, max_tokens=max_tokens,
            messages=[{"role": "system", "content": system}, *messages])
        text = resp.choices[0].message.content or ""
        return text, resp.usage.prompt_tokens, resp.usage.completion_tokens
    resp = client.messages.create(model=model, system=system, messages=messages, max_tokens=max_tokens)
    text = "".join(block.text for block in resp.content if block.type == "text")
    return text, resp.usage.input_tokens, resp.usage.output_tokens
#--------------------------------------------------------------#

# Helpers: pull the {...} out of a reply; append a cost line to the log
def _extract_json(text: str) -> str:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in the reply")
    return text[start:end + 1]


def _log_call(task: str, model: str, tokens_in: int, tokens_out: int, cost: float, ok: bool) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    new = not LOG_FILE.exists()
    with LOG_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if new:
            writer.writerow(["time", "task", "model", "input_tokens", "output_tokens", "cost", "ok"])
        writer.writerow([datetime.now().isoformat(timespec="seconds"), task, model,
                         tokens_in, tokens_out, f"{cost:.6f}", ok])
#--------------------------------------------------------------#

# Main entry point
def call_llm(task: str, prompt: str, schema: type[T], tier: str = "fast",
             check: Callable[[T], list[str]] | None = None,
             max_tokens: int = 4096) -> tuple[T, list[str]]:
    model, price_in, price_out = settings(tier)
    system = SYSTEM.format(schema=json.dumps(schema.model_json_schema()))
    messages = [{"role": "user", "content": prompt}]
    tokens_in = tokens_out = 0
    result, problems, last_error = None, [], ""

    for attempt in range(MAX_RETRIES + 1):
        text, t_in, t_out = _send(model, system, messages, max_tokens)
        tokens_in += t_in
        tokens_out += t_out
        try:
            result = schema.model_validate_json(_extract_json(text))
        except (ValueError, ValidationError) as e:
            result, last_error = None, str(e)
            feedback = f"That reply was invalid:\n{last_error}"
        else:
            problems = check(result) if check else []
            if not problems:
                break
            feedback = "That reply breaks these rules:\n- " + "\n- ".join(problems)
        if attempt < MAX_RETRIES:
            messages += [{"role": "assistant", "content": text},
                         {"role": "user", "content": feedback + "\nReply again with only the corrected JSON object."}]

    cost = tokens_in / 1e6 * price_in + tokens_out / 1e6 * price_out
    _log_call(task, model, tokens_in, tokens_out, cost, result is not None)
    if result is None:
        raise LLMError(f"{task}: no valid reply after {MAX_RETRIES + 1} attempts. Last error: {last_error[:500]}")
    return result, problems
#--------------------------------------------------------------#
#----------------------End-of-code-----------------------------#
