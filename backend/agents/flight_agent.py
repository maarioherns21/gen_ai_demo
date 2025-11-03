from __future__ import annotations
from typing import Dict, Any
from backend.tools.flights_api import search_flights
from decimal import Decimal
from backend.schemas.trip_schema import LineItem, LineItemType
import uuid

class FlightAgent:
    name = "flights"

    def run(self, *, state: Dict[str, Any]) -> Dict[str, Any]:
        trip = state["trip"]
        origin = state.get("origin") or trip.origin
        dest   = state.get("destination") or trip.destination
        adults = int(state.get("adults", 1))
        currency = state.get("currency", "USD")

        offers = search_flights(
            origin_code=origin,
            dest_code=dest,
            depart=trip.start_date,
            ret=trip.end_date,
            adults=adults,
            currency=currency,
            max_results=int(state.get("max_results_flights", 12)),
            non_stop=state.get("non_stop")  # None/True/False
        )

        # Add the cheapest as a preview line item (optional)
        if offers:
            best = min(offers, key=lambda x: float(x.get("total") or 9e18))
            price = Decimal(str(best.get("total") or "0.00"))
            li = LineItem(
                id=str(uuid.uuid4()),
                trip_id=trip.id,
                type=LineItemType.FLIGHT,
                vendor="/".join(best.get("carriers") or []) or "Flight",
                price_usd=price if (best.get("currency") == "USD") else Decimal("0.00"),
                refundable=None,
                terms={},
                meta={
                    "currency": best.get("currency"),
                    "total_native": best.get("total"),
                    "carriers": best.get("carriers"),
                    "durations": best.get("durations"),
                    "raw_offer_id": best.get("id"),
                }
            )
            trip.add_line_item(li)

        return {
            "flight_options": {
                "source": "amadeus",
                "currency": currency,
                "count": len(offers),
                "offers": offers[:6],  # keep response skinny for UI
            }
        }
