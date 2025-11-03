from __future__ import annotations
from typing import Dict, Any
from datetime import timedelta
from backend.schemas.trip_schema import Trip
from decimal import Decimal

class PlannerAgent:
    name: str = "planner"

    def run(self, *, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inputs expected in state:
          - origin (IATA), destination (IATA)
          - start_date (date), end_date (date)
          - budget_usd (Decimal or str)
          - title (optional)
        Produces:
          - trip (Trip dataclass)
          - itinerary_days (list[ItineraryDay])
        """
        start_date = state["start_date"]
        end_date = state["end_date"]
        title = state.get("title", "Proposed Trip")
        budget = state["budget_usd"]
        if isinstance(budget, str):
            budget = Decimal(budget)

        trip = Trip(
            id=state["trip_id"],
            user_id=state["user_id"],
            title=title,
            origin=state["origin"],
            destination=state["destination"],
            start_date=start_date,
            end_date=end_date,
            budget_usd=budget,
        )

        # simple heuristic: all days in same city initially
        total_days = trip.duration_days
        for i in range(total_days):
            day_date = start_date + timedelta(days=i)
            trip.add_day(city=state.get("primary_city") or state["destination"], notes=f"Day {i+1} ({day_date.isoformat()})")

        return {"trip": trip}  # Orchestrator holds the object directly
