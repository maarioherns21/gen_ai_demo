from __future__ import annotations
from typing import Any, Dict
import json
from agents import Runner, SQLiteSession
from backend.llm.agents_graph import orchestrator, planner, flights, lodging, activities, budget, critic

import logging
logger = logging.getLogger("orchestrator")
logging.basicConfig(level=logging.INFO)

class Orchestrator:
    """High-level coordination using OpenAI Agents SDK +existing tools."""
    def __init__(self, session_id: str | None = None):
        self.session = SQLiteSession(session_id or "trip_session")

    def _as_prompt(self, user_message: str | None = None, state: dict | None = None, payload: dict | None = None) -> str:
        """Safely build a single string input for the agent run."""
        parts = []
        if user_message is not None:
            parts.append(f"User message:\n{user_message}")
        if state is not None:
            parts.append(f"Current state JSON:\n{json.dumps(state, ensure_ascii=False)}")
        if payload is not None:
            parts.append(f"Payload JSON:\n{json.dumps(payload, ensure_ascii=False)}")
        parts.append("Return ONLY valid JSON per your output schema. No prose.")
        return "\n\n".join(parts)

    async def _run_agent(self, agent, input: Any) -> dict:
        # Normalize any dict payload to a string prompt
        if isinstance(input, dict):
            prompt = self._as_prompt(payload=input)
        else:
            prompt = str(input)

        result = await Runner.run(agent, input=prompt, session=self.session)
        return result.final_output if isinstance(result.final_output, dict) else {"text": result.final_output}

    async def chat(self, user_message: str, state: dict | None = None) -> Dict[str, Any]:
        """Intake/triage: ask for missing info or move to planning."""
        prompt = self._as_prompt(user_message=user_message, state=state or {})
        out = await Runner.run(orchestrator, input=prompt, session=self.session)
        
        print("DEBUG final_output:", out.final_output) 
        
        data = out.final_output if isinstance(out.final_output, dict) else {}
        return {
            "need_more_info": bool(data.get("need_more_info", False)),
            "questions": data.get("questions", []),
            "state": data.get("state", {}),
            "next_step": data.get("next_step", "plan"),
        }

    async def plan_trip(self, payload: dict) -> Dict[str, Any]:
        """Fixed sequence (simple & reliable)."""
        logger.info("[ORCH] /plan payload keys=%s", list(payload.keys()))
        # 1) Planner
        p = await self._run_agent(planner, payload)
        logger.info("[ORCH] Planner out keys=%s", list(p.keys()))
        # 2) Flights
        f_in = {**payload, **p}

        logger.info("[ORCH] Flights in keys=%s", list(f_in.keys()))

        f = await self._run_agent(flights, f_in)

        if not isinstance(f, dict) or "flight_options" not in f:
            # Deterministic fallback
            from backend.tools.flights_api import search_flights as _search_flights
            f = {
                "flight_options": _search_flights(
                    origin=f_in.get("origin"),
                    destination=f_in.get("destination"),
                    depart_date=f_in.get("start_date"),
                    return_date=f_in.get("end_date"),
                    adults=int(f_in.get("adults", 1)),
                    currency="USD",
                    non_stop=bool(f_in.get("non_stop") or False),
                    max_results=int(f_in.get("max_results_flights", 12)),
                ) or {}
            }

        logger.info("[ORCH] Flights out keys=%s; sample=%s",
                    list((f or {}).keys()),
                    json.dumps((f or {}) if len(json.dumps(f or {})) < 300 else {"_": "omitted"}, ensure_ascii=False))


        # 3) Lodging
        l_in = {**payload, **p, **f}
        logger.info("[ORCH] Lodging in keys=%s", list(l_in.keys()))
        l = await self._run_agent(lodging, l_in)
        logger.info("[ORCH] Activities out keys=%s", list((a or {}).keys()))
        
        # 4) Activities
        a_in = {**payload, **p, **f, **l}
        a = await self._run_agent(activities, a_in)

        # 5) Budget
        b_in = {**payload, **p, **f, **l, **a}
        b = await self._run_agent(budget, b_in)

        # 6) Critic
        c_in = {**payload, **p, **f, **l, **a, **b}
        c = await self._run_agent(critic, c_in)

        # Merge final result
        merged = {**p, **f, **l, **a, **b, **c}
        merged.setdefault("flight_options", f.get("flight_options") or f)
        merged.setdefault("lodging_options", l.get("hotels", []))
        merged.setdefault("activities", a.get("plan", {}))
        merged.setdefault("budget", {
            "total_usd": 0.0,
            "cap_usd": payload.get("budget_usd", 0.0),
            "status": "under",
            "delta_usd": 0.0
        })
        merged.setdefault("critic", c)
        merged.setdefault("next_actions", [])
        return merged
