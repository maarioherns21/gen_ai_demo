from __future__ import annotations
from typing import Dict, Any
from decimal import Decimal
from backend.tools.hotels_api import search_hotels
from backend.schemas.trip_schema import LineItem, LineItemType
import uuid


class LodgingAgent:
    name = "lodging"

    def _to_usd(self, total: float, cur: str, fx_rates: Dict[str, float] | None) -> Decimal:
        """
        Convert total to USD if possible. If no fx rate is available and cur != USD,
        return Decimal('0.00') to avoid over-counting in the trip preview.
        """
        if cur == "USD":
            return Decimal(str(round(total, 2)))
        rate = (fx_rates or {}).get(cur)
        if rate:  # rate should be VALUE_IN_USD_PER_1_CUR (e.g., MXN->USD 0.055)
            return Decimal(str(round(total * rate, 2)))
        return Decimal("0.00")

    def run(self, *, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Requires in state:
          - trip (Trip dataclass already created by Planner)
          - primary_city or trip.destination
          - (optional) fx_rates: dict like {"EUR": 1.08, "MXN": 0.055}
        Produces:
          - lodging_options (list of dict)  # normalized DTOs
          - (optionally) adds a default hotel line_item to trip for budgeting preview
        """
        trip = state["trip"]
        city = state.get("primary_city") or trip.destination
        fx_rates: Dict[str, float] | None = state.get("fx_rates")
        preview_n = int(state.get("preview_hotels", 3))

        options = search_hotels(
            city=city,
            check_in=trip.start_date,
            check_out=trip.end_date,
            guests=state.get("adults", 1),
            currency="USD",  # we still ask for USD, but provider may return local
            refundable_only=bool(state.get("refundable_only", False)),
            max_km_from_center=float(state.get("max_km_from_center", 15.0)),
            max_results=int(state.get("max_results_hotels", 20)),
        )

        if options:
            # choose the cheapest *total* in its native currency, then convert
            best = min(
                options,
                key=lambda x: float(x.get("total") or 9e18)
            )
            total = float(best.get("total") or 0.0)
            cur = best.get("currency", "USD") or "USD"
            price_usd = self._to_usd(total, cur, fx_rates)

            line = LineItem(
                id=str(uuid.uuid4()),
                trip_id=trip.id,
                type=LineItemType.HOTEL,
                vendor=best.get("name"),
                price_usd=price_usd,  # already converted or zero if unknown
                refundable=bool(best.get("refundable")),
                terms={
                    "refund_policy": best.get("refund_policy"),
                    "cancel_deadline": best.get("cancel_deadline"),
                    "board": best.get("board"),
                    "rating": best.get("rating"),
                },
                meta={
                    "city": best.get("city"),
                    "country": best.get("country"),
                    "room_type": best.get("room_type"),
                    # Keep both ids for convenience:
                    "amadeus_hotel_id": best.get("amadeus_hotel_id") or best.get("hotelId"),
                    "hotelId": best.get("hotelId"),
                    "offer_id": best.get("raw_offer_id"),
                    "iataCity": best.get("iataCity"),
                    "currency": cur,
                    "avg_per_night": best.get("avg_per_night"),              # may be base or total/nights depending on provider
                    "geo": best.get("geo"),
                },
            )
            trip.add_line_item(line)

        return {"lodging_options": options}
