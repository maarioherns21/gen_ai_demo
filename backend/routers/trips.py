from __future__ import annotations
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Annotated
from uuid import uuid4

from fastapi.responses import RedirectResponse
from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field, field_validator

from backend.orchestrator.controllerllm import Orchestrator
from backend.orchestrator.controller import Orchestrator as Orch

orch = Orch()
# Use Annotated[Decimal, Field(...)] instead of condecimal(...)
BudgetDecimal = Annotated[Decimal, Field(gt=Decimal("0"))]

class PlanTripRequest(BaseModel):
    user_id: str
    origin: str = Field(..., min_length=3, max_length=3)
    destination: str = Field(..., min_length=3, max_length=3)
    start_date: date
    end_date: date
    budget_usd: BudgetDecimal
    title: Optional[str] = None
    primary_city: Optional[str] = None
    adults: int = Field(1, ge=1, le=12)

    # optional toggles/knobs already supported in your orchestrator
    non_stop: Optional[bool] = None
    max_results_flights: int = Field(12, ge=1, le=50)
    activities_enabled: bool = True
    critic_enabled: bool = True
    skip_day1_activities: bool = True
    max_activities_per_day: int = Field(2, ge=0, le=10)

    # Ensure IATA codes are uppercase and exactly 3 letters
    @field_validator("origin", "destination")
    @classmethod
    def _iata_upper(cls, v: str) -> str:
        v = v.strip().upper()
        if len(v) != 3 or not v.isalpha():
            raise ValueError("must be a 3-letter IATA code")
        return v
    
    @field_validator("budget_usd", mode="before")
    @classmethod
    def _coerce_budget(cls, v):
        try:
            return Decimal(str(v))
        except (InvalidOperation, ValueError, TypeError):
            raise ValueError("budget_usd must be a valid number")
        
class PlanTripResponse(BaseModel):
    trip: dict
    flight_options: dict
    lodging_options: list
    activities: dict
    budget: dict
    critic: dict
    next_actions: list


class ChatRequest(BaseModel):
    message: str = Field(..., description="User message (free text)")
    state: Dict[str, Any] = Field(default_factory=dict, description="Accumulated state (optional)")


class ChatResponse(BaseModel):
    need_more_info: bool
    questions: Optional[List[str]] = None
    state: Dict[str, Any]
    next_step: str

router = APIRouter(prefix="/v1/trips", tags=["trips"])


@router.post("/chat", response_model=ChatResponse)
async def chat_planner(input: ChatRequest = Body(...)):
    orch = Orchestrator(session_id=input.state.get("user_id", "anon"))
    try:
        out = await orch.chat(user_message=input.message, state=input.state)
        # return dict; FastAPI enforces ChatResponse
        return {
            "need_more_info": bool(out.get("need_more_info", False)),
            "questions": out.get("questions") or None,
            "state": out.get("state", {}),
            "next_step": out.get("next_step", "plan"),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- Routes ---
@router.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")

@router.post("/plan", response_model=PlanTripResponse)
async def plan_trip(req: PlanTripRequest):
    try:
        payload = req.model_dump()  # <-- v2; preserves date objects
        
        payload["trip_id"] = str(uuid4())
        
        result = orch.plan_trip(payload=payload)
        print("chck 123 results", result)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    

