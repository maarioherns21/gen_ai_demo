from agents import function_tool
from datetime import date
from typing import Dict, Any
from backend.tools.flights_api import search_flights
from backend.tools.hotels_api import search_hotels
from backend.tools.events_api import search_activities

@function_tool
def tool_search_flights(
    origin: str,
    destination: str,
    depart_date: str,
    return_date: str | None = None,
    adults: int = 1,
    currency: str = "USD",
    non_stop: bool | None = None,
    max_results: int = 12,
) -> Dict[str, Any]:
    """Amadeus-backed flight search (wrapped for Agents SDK)."""
    offers = search_flights(
        origin_code=origin,
        dest_code=destination,
        depart=date.fromisoformat(depart_date),
        ret=date.fromisoformat(return_date) if return_date else None,
        adults=int(adults),
        currency=currency,
        non_stop=non_stop,
        max_results=int(max_results),
    ) or []
    print("Search flights payload ****", offers)
    # keep payload small
    return {"source": "amadeus", "currency": currency, "count": len(offers), "offers": offers[:3]}

@function_tool
def tool_search_hotels(
    city: str,
    check_in: str,
    check_out: str,
    guests: int = 1,
    currency: str = "USD",
    refundable_only: bool = False,
    max_results: int = 10,
) -> Dict[str, Any]:
    res = search_hotels(
        city=city,
        check_in=date.fromisoformat(check_in),
        check_out=date.fromisoformat(check_out),
        guests=int(guests),
        currency=currency,
        refundable_only=bool(refundable_only),
        max_results=int(max_results),
    ) or []
    print("Search Hotels payload ****", res)
    return {"hotels": res[:3]}

@function_tool
def tool_search_activities(
    city_code: str,
    for_date: str,
    max_results: int = 6,
) -> Dict[str, Any]:
    acts = search_activities(
        city_code=city_code,
        for_date=date.fromisoformat(for_date),
        max_results=int(max_results),
    ) or []
    print("Search Activities payload ****", acts)
    return {"activities": acts[:5]}
