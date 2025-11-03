from __future__ import annotations
from typing import Dict, Any
from decimal import Decimal
from backend.schemas.tool_schema import FlightSearchInput
from backend.agents.planner_agent import PlannerAgent
from backend.tools.flights_api import search_flights
from backend.agents.lodging_agent import LodgingAgent
from backend.agents.budget_agent import BudgetAgent
from backend.agents.activity_agent import ActivitiesAgent
from backend.agents.critic_agent import CriticAgent

class Orchestrator:
    """
    Minimal orchestrator:
      1) PlannerAgent builds the Trip (days populated)
      2) Flights fetched via Amadeus helper
      3) LodgingAgent proposes hotel options and adds a preview hotel cost to the trip
      4) BudgetAgent summarizes current costs vs. cap
    """
    def __init__(self):
        self.planner = PlannerAgent()
        self.lodging = LodgingAgent()
        self.budget = BudgetAgent()
        self.activities = ActivitiesAgent()
        self.critic = CriticAgent()

    def _summarize_flights(self, offers: Any) -> Dict[str, Any]:
        """
        Normalize various return shapes into the compact summary the API returns.
        - If `offers` is already a list of normalized offer dicts: use that.
        - Otherwise, fall back to an empty summary.
        """
        if not isinstance(offers, list) or not offers:
            return {
                "source": "amadeus",
                "currency": "USD",
                "count": 0,
                "sample_price_usd": None,
                "offers": [],
            }

        first = offers[0]
        currency = first.get("currency", "USD")
        sample = first.get("total_price")
        try:
            sample = float(sample) if sample is not None else None
        except Exception:
            sample = None

        return {
            "source": "amadeus",
            "currency": currency,
            "count": len(offers),
            "sample_price_usd": sample,
            "offers": offers[:10],  # include a few for the client to render
        }

    def plan_trip(self, *, payload: Dict[str, Any]) -> Dict[str, Any]:
        # normalize incoming payload (keep date handling as you already had it)
        state: Dict[str, Any] = {
            "trip_id": payload["trip_id"],
            "user_id": payload["user_id"],
            "title": payload.get("title"),
            "origin": payload["origin"],
            "destination": payload["destination"],
            "start_date": payload["start_date"],
            "end_date": payload["end_date"],
            "budget_usd": Decimal(str(payload["budget_usd"])),
            "primary_city": payload.get("primary_city"),
            # pass through optional flight knobs if present
            "non_stop": payload.get("non_stop"),
            "max_results_flights": payload.get("max_results_flights", 12),

            # NEW toggles/knobs
            "activities_enabled": payload.get("activities_enabled", True),
            "critic_enabled": payload.get("critic_enabled", True),
            "skip_day1_activities": payload.get("skip_day1_activities", True),
            "max_activities_per_day": payload.get("max_activities_per_day", 2),
        }

        # 1) Planner builds the Trip
        out = self.planner.run(state=state)
        state.update(out)
        trip = state["trip"]

        # 2) Flights (call helper; it returns a list of offers)
        fs_in = FlightSearchInput(
            origin=trip.origin,
            destination=trip.destination,
            depart_date=trip.start_date,
            return_date=None,
            adults=state.setdefault("adults", payload.get("adults", 1)),
        )

        raw_flights = search_flights(
            origin_code=fs_in.origin,
            dest_code=fs_in.destination,
            depart=fs_in.depart_date,
            ret=fs_in.return_date,   # or None for one-way
            adults=fs_in.adults,
            currency="USD",
            non_stop=state.get("non_stop"),
            max_results=int(state.get("max_results_flights", 12)),
        )
        flight_summary = self._summarize_flights(raw_flights)

        # 3) Lodging
        lodging_out = self.lodging.run(state=state)
        state.update(lodging_out)

        # 4) Activities (optional)
        if state["activities_enabled"]:
            state.update(self.activities.run(state=state))

        # 5) Budget
        budget_out = self.budget.run(state=state)

        # 6) Critic (optional)
        critic = {"issues": [], "suggestions": [], "decision": "approve"}
        if state["critic_enabled"]:
            critic = self.critic.run(state=state)["critic"]

        # Response
        return {
            "trip": trip.to_dict(),
            "flight_options": flight_summary,
            "lodging_options": state.get("lodging_options", []),
            "activities": state.get("activities_plan", {}),
            "budget": budget_out["budget_summary"],
            "critic": critic,
            "next_actions": [
                "Add lodging options",
                "Review activities",
                "Confirm refundable terms",
            ],
        }

