from __future__ import annotations
from typing import Dict, Any, List
from decimal import Decimal


class BudgetAgent:
    name = "budget"

    def run(self, *, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Requires:
          - trip (Trip with line_items possibly added by other agents)
        Emits:
          - budget_summary dict with totals and status (under/over)
          - suggested_tradeoffs when over budget
        """
        trip = state["trip"]

        # Trip should expose totals as Decimal already; keep final strings for UI
        total = trip.total_cost_usd              # Decimal
        cap = trip.budget_usd                    # Decimal
        status = "under" if total <= cap else "over"
        diff = (cap - total).quantize(Decimal("0.01"))

        tradeoffs: List[str] = []
        if status == "over":
            # Prioritize concrete, controllable levers
            tradeoffs.extend([
                "Pick a refundable rate with a lower total or switch to ROOM_ONLY if breakfast isn’t needed.",
                "Adjust dates to Sun–Thu to reduce nightly rates and airfares.",
                "Filter hotels within 8–10 km of center to avoid premium zones.",
                "Reduce paid activities; favor free city walks/parks/museums.",
                "Trim one night or switch to a business hotel outside the historic center.",
            ])

        return {
            "budget_summary": {
                "cap_usd": str(cap),
                "total_usd": str(total),
                "status": status,
                "delta_usd": str(diff),
            },
            "suggested_tradeoffs": tradeoffs,
        }
