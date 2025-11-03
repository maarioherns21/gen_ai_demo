from __future__ import annotations
from datetime import date
from uuid import uuid4
from typing import Dict, Any, Iterable

REQUIRED_KEYS: tuple[str, ...] = (
    "user_id", "origin", "destination", "start_date", "end_date", "budget_usd"
)

def _as_date(v):
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v))

def _find_state(obj: Dict[str, Any]) -> Dict[str, Any]:
    """
    Accept either:
      - the raw 'state' dict from /v1/trips/chat, or
      - the full /v1/trips/chat response (with top-level keys like need_more_info, state, next_step)
    """
    if not isinstance(obj, dict):
        return {}
    # If they posted the full /chat response, peel out 'state'
    if "state" in obj and isinstance(obj["state"], dict) and any(k in obj["state"] for k in REQUIRED_KEYS):
        return obj["state"]
    # If this already looks like a state dict, return it
    if any(k in obj for k in REQUIRED_KEYS):
        return obj
    return {}

def _missing_keys(d: Dict[str, Any], req: Iterable[str]) -> list[str]:
    return [k for k in req if d.get(k) in (None, "", [])]

def normalize_chat_state(incoming: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert /v1/trips/chat output into the payload expected by the planner/tools.
    Raises ValueError with a clear message when required keys are missing.
    """
    state = _find_state(incoming)
    if not state:
        raise ValueError("Invalid payload: expected a 'state' dict from /v1/trips/chat or the raw state object.")

    missing = _missing_keys(state, REQUIRED_KEYS)
    if missing:
        raise ValueError(f"Missing required fields in state: {', '.join(missing)}")

    payload = {
        "user_id": str(state["user_id"]),
        "trip_id": str(uuid4()),
        "origin": str(state["origin"]).strip().upper(),
        "destination": str(state["destination"]).strip().upper(),
        "start_date": _as_date(state["start_date"]),
        "end_date": _as_date(state["end_date"]),
        "budget_usd": float(state["budget_usd"]),
        "title": state.get("title") or "Proposed Trip",
        "primary_city": state.get("primary_city"),
        "adults": int(state.get("adults", 1)),
        "non_stop": state.get("non_stop", None),
        "max_results_flights": int(state.get("max_results_flights", 12)),
        "activities_enabled": bool(state.get("activities_enabled", True)),
        "critic_enabled": bool(state.get("critic_enabled", True)),
        "skip_day1_activities": bool(state.get("skip_day1_activities", True)),
        "max_activities_per_day": int(state.get("max_activities_per_day", 2)),
    }

    # Amadeus hotels/activities need a city IATA code (e.g., MEX). If you got a name, fall back to destination.
    pc = payload.get("primary_city")
    if not pc or not (isinstance(pc, str) and len(pc.strip()) == 3 and pc.isalpha()):
        payload["primary_city"] = payload["destination"]

    return payload
