import json
from typing import Any


def as_dict(run_result):
    """Normalize Runner.run(...) result to a dict."""
    out = getattr(run_result, "final_output", run_result)
    # If the model returned a plain JSON string
    if isinstance(out, str):
        return json.loads(out)
    # Some agents return {"text": "<json>"} – handle that too
    if isinstance(out, dict) and "text" in out and isinstance(out["text"], str):
        try:
            return json.loads(out["text"])
        except json.JSONDecodeError:
            pass
    # Already a dict
    if isinstance(out, dict):
        return out
    # Fallback
    return {}

def as_prompt(payload: dict) -> str:
    return "Payload JSON:\n" + json.dumps(payload, ensure_ascii=False) + "\n\nReturn ONLY valid JSON per your output schema. No prose."


def safe_to_dict(obj: Any) -> dict:
    """Best-effort conversion to dict from LLM returns (string JSON or dict)."""
    if isinstance(obj, dict):
        # Some agents return {"text": "<json>"}
        if "text" in obj and isinstance(obj["text"], str):
            try:
                return json.loads(obj["text"])
            except json.JSONDecodeError:
                return {}
        return obj
    if isinstance(obj, str):
        try:
            return json.loads(obj)
        except json.JSONDecodeError:
            return {}
    return {}