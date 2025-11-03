from __future__ import annotations
import logging
from typing import Any
from openai import OpenAI
from backend.config.settings import OPENAI_API_KEY, OPENAI_MODEL

# --- Logger setup ---
logger = logging.getLogger("backend.llm.openai_client")

client = OpenAI(api_key=OPENAI_API_KEY)

def respond(
    system: str,
    user: str,
    *,
    tools: list | None = None,
    tool_choice: str | None = None,
    json_schema: dict | None = None,
    stream: bool = False,
) -> Any:
    """
    Minimal wrapper for OpenAI Responses API.
    Supports optional tool calling & JSON schema outputs.
    """

    kwargs = dict(
        model=OPENAI_MODEL,
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )

    # Add optional tools / structured output
    if tools:
        kwargs["tools"] = tools
        if tool_choice:
            kwargs["tool_choice"] = tool_choice

    # New SDK expects "format" inside "response" args or special JSON mode
    if json_schema:
        # Safe fallback – use 'response_format' only if supported
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": json_schema,
        }

    # Optional streaming
    if stream:
        kwargs["stream"] = True

    try:
        resp = client.responses.create(**kwargs)
        return resp
    except TypeError as e:
        # Compatibility fallback for SDKs that renamed argument
        logger.warning("Falling back due to SDK change: %s", str(e))
        kwargs.pop("response_format", None)
        resp = client.responses.create(**kwargs)
        return resp
    except Exception as e:
        logger.error(f"OpenAI call failed: {e}", exc_info=True)
        raise RuntimeError("OpenAI call failed") from e

