from datetime import date
import uuid
from backend.orchestrator.controller import Orchestrator
from backend.schemas.tool_schema import FlightSearchOutput, FlightItinerary, FlightSegment, CabinClass

def test_orchestrator_plan_trip(monkeypatch):
    # Fake flights output (no network)
    seg = FlightSegment(
        carrier="AM", flight_number="AM001",
        origin="MEX", destination="FCO",
        depart_iso="2025-06-01T08:00:00Z", arrive_iso="2025-06-01T20:00:00Z",
        duration_minutes=720, cabin=CabinClass.ECONOMY
    )
    itin = FlightItinerary(price_total_usd=800.0, refundable=True, segments=[seg])
    fake_out = FlightSearchOutput(itineraries=[itin], source="test", currency="USD")

    # Patch orchestrator to use a stubbed search function
    import backend.orchestrator.controller as ctrl_mod
    monkeypatch.setattr(ctrl_mod, "search_flights", lambda **kwargs: fake_out)

    orch = Orchestrator()
    payload = {
        "trip_id": str(uuid.uuid4()),
        "user_id": "u1",
        "title": "Italy Week",
        "origin": "MEX",
        "destination": "ROM",
        "start_date": date(2026, 6, 1),  # or "2025-06-01" if your controller parses
        "end_date":   date(2026, 6, 7),
        "budget_usd": 2500,
        "adults": 1,
    }
    res = orch.plan_trip(payload=payload)

    assert res["trip"]["origin"] == "MEX"
    assert res["trip"]["destination"] == "ROM"
    assert len(res["trip"]["days"]) == 7
