import json
from typing import Any, Optional

from agents import Runner, SQLiteSession
from backend.llm.agents_graph import orchestrator as orchestrator_agent



def _safe_to_dict(obj: Any) -> dict:
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

class OrchestratorInputs:
    """
    Maintains a state dict entirely produced/modified by the orchestrator.
    You can feed NL lines (or JSON-ish lines) and it will call the orchestrator
    to return a JSON patch, then merge it into the state.
    """

    def __init__(self, session_id: Optional[str] = None, seed: Optional[dict] = None):
        self.session = SQLiteSession(session_id or "trip_input_session")
        self.state: dict = dict(seed or {})  # no defaults; seed is optional

    def _as_prompt(
        self,
        user_message: Optional[str] = None,
        state: Optional[dict] = None,
        payload: Optional[dict] = None,
    ) -> str:
        parts = []
        if user_message is not None:
            parts.append(f"User message:\n{user_message}")
        if state is not None:
            parts.append("Current state JSON:\n" + json.dumps(state, ensure_ascii=False))
        if payload is not None:
            parts.append("Payload JSON:\n" + json.dumps(payload, ensure_ascii=False))
        parts.append("Return ONLY valid JSON per your output schema. No prose.")
        return "\n\n".join(parts)

    async def apply_line(self, line: str) -> dict:
        """
        Send one line of NL (or quick JSON) to the orchestrator.
        Orchestrator returns a JSON payload/patch per its schema.
        The result is merged into the current state.
        """
        prompt = self._as_prompt(user_message=line, state=self.state)
        res = await Runner.run(orchestrator_agent, input=prompt, session=self.session)
        final = getattr(res, "final_output", getattr(res, "text", "{}"))
        patch = _safe_to_dict(final)
        if not isinstance(patch, dict):
            patch = {}
        self.state.update(patch)
        return dict(self.state)

    def set(self, key: str, value: Any) -> dict:
        """Manual override without calling the model."""
        self.state[key] = value
        return dict(self.state)

    def show(self) -> dict:
        return dict(self.state)