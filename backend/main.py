# backend/api.py
import json
from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agents import Runner, SQLiteSession
from backend.llm.agents_graph import orchestrator, planner, flights, lodging, activities, budget, critic
from backend.llm.orchestrator_input import OrchestratorInputs
from backend.utils.utils import as_dict, as_prompt

app = FastAPI(title="Trip Orchestrator API", version="1.0.0")

# Adjust this for your frontend origin(s)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------
# Simple in-memory session store
# -----------------------
_SESSIONS: Dict[str, OrchestratorInputs] = {}

# -----------------------
# Pydantic models
# -----------------------
class CreateSessionBody(BaseModel):
    session_id: str = Field(..., description="Client-provided session id (e.g., UUID)")

class ApplyLineBody(BaseModel):
    line: str = Field(..., description="Natural language line to feed the orchestrator")

class SetKeyBody(BaseModel):
    key: str
    value: Any  # value can be string/number/bool/object/array

class SeedBody(BaseModel):
    nl: Optional[str] = Field(None, description="Optional one-shot NL seed")

class RunResult(BaseModel):
    result: Dict[str, Any]

# -----------------------
# Helpers
# -----------------------
def _require_session(session_id: str) -> OrchestratorInputs:
    if session_id not in _SESSIONS:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return _SESSIONS[session_id]

# -----------------------
# Endpoints
# -----------------------
@app.post("/session", response_model=dict)
async def create_session(body: CreateSessionBody):
    """
    Create a new orchestrator session (stateless across process restarts).
    """
    if body.session_id in _SESSIONS:
        # Reset it to a fresh OrchestratorInputs if client reuses id intentionally
        _SESSIONS[body.session_id] = OrchestratorInputs(session_id=body.session_id)
    else:
        _SESSIONS[body.session_id] = OrchestratorInputs(session_id=body.session_id)
    return {"ok": True, "session_id": body.session_id}

@app.post("/session/{session_id}/seed", response_model=dict)
async def seed_session(session_id: str, body: SeedBody):
    """
    Optionally seed with a single NL line to create initial dict.
    """
    orch = _require_session(session_id)
    if body.nl:
        state = await orch.apply_line(body.nl)
    else:
        state = orch.show()
    return {"ok": True, "state": state}

@app.post("/session/{session_id}/apply-line", response_model=dict)
async def apply_line(session_id: str, body: ApplyLineBody):
    """
    Apply a natural-language line to the orchestrator and return updated state.
    """
    orch = _require_session(session_id)
    state = await orch.apply_line(body.line)
    return {"ok": True, "state": state}

@app.post("/session/{session_id}/set", response_model=dict)
async def set_key(session_id: str, body: SetKeyBody):
    """
    Set a key to a JSON value (no string parsing needed on client).
    """
    orch = _require_session(session_id)
    orch.set(body.key, body.value)
    return {"ok": True, "state": orch.show()}

@app.get("/session/{session_id}/show", response_model=dict)
async def show_state(session_id: str):
    """
    Return the current orchestrated TEST_INPUT dict.
    """
    orch = _require_session(session_id)
    state = orch.show()
    if not isinstance(state, dict) or not state:
        raise HTTPException(status_code=400, detail="Orchestrator did not produce a valid non-empty dict.")
    return {"ok": True, "state": state}

@app.post("/session/{session_id}/run", response_model=RunResult)
async def run_pipeline(session_id: str):
    """
    Execute full pipeline:
      planner -> flights -> lodging -> activities -> budget -> critic
    Returns merged result with the key fields expected by the UI.
    """
    orch = _require_session(session_id)
    TEST_INPUT = orch.show()
    if not isinstance(TEST_INPUT, dict) or not TEST_INPUT:
        raise HTTPException(status_code=400, detail="Orchestrator did not produce a valid non-empty dict.")
    
    # 1) Planner
    session = SQLiteSession("smoke_pipeline")
    # 1) Planner
    p_res = await Runner.run(planner, input=as_prompt(TEST_INPUT), session=session)
    p = as_dict(p_res)
    print("PLANNER ***************************" , p)
    assert "trip" in p and "primary_city" in p, "Planner failed"
    merged = {**TEST_INPUT, **p}

    # 2) Flights
    f_res = await Runner.run(flights, input=as_prompt(merged), session=session)
    f = as_dict(f_res)
    print("FLIGHT ***************************" , f)
    assert "flight_options" in f, "Flights failed"
    merged = {**merged, **f}

    # 3) Lodging
    l_res = await Runner.run(lodging, input=as_prompt(merged), session=session)
    l = as_dict(l_res)
    print("HOTELS ***************************" , l)
    assert "lodging_options" in l, "Lodging failed"
    merged = {**merged, **l}

    # 4) Activities
    a_res = await Runner.run(activities, input=as_prompt(merged), session=session)
    a = as_dict(a_res)
    print("ACTIVITIES ***************************" , a)
    assert ("activities" in a) or ("plan" in a), "Activities failed"
    merged = {**merged, **a}

    # 5) Budget
    b_res = await Runner.run(budget, input=as_prompt(merged), session=session)
    b = as_dict(b_res)
    print("Budget ***************************" , b)
    assert "budget" in b, "Budget failed"
    merged = {**merged, **b}

    # 6) Critic
    c_res = await Runner.run(critic, input=as_prompt(merged), session=session)
    c = as_dict(c_res)
    print("Critics ***************************" , c)
    assert "critic" in c, "Critic failed"
    merged = {**merged, **c}

    print(json.dumps(
        {k: merged[k] for k in ["trip","flight_options","lodging_options","activities","plan","budget","critic"] if k in merged},
        indent=2, ensure_ascii=False
    ))

    payload = {
        k: merged[k] 
        for k in ["trip","flight_options","lodging_options","activities","plan","budget","critic"] 
        if k in merged
    }

    return RunResult(result=payload)

@app.delete("/session/{session_id}", response_model=dict)
async def delete_session(session_id: str):
    _SESSIONS.pop(session_id, None)
    return {"ok": True}