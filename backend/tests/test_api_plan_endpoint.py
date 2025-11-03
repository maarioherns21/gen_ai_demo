from fastapi.testclient import TestClient
from backend.main import app
from backend.schemas.tool_schema import FlightSearchOutput, FlightItinerary, FlightSegment, CabinClass

client = TestClient(app)

def test_api_v1_trips_plan_success(monkeypatch):
    # Stub flights search used by the controller
    seg = FlightSegment(
        carrier="AM", flight_number="AM001",
        origin="MEX", destination="FCO",
        depart_iso="2025-06-01T08:00:00Z", arrive_iso="2025-06-01T20:00:00Z",
        duration_minutes=720, cabin=CabinClass.ECONOMY
    )
    itin = FlightItinerary(price_total_usd=799.99, refundable=True, segments=[seg])
    fake_out = FlightSearchOutput(itineraries=[itin], source="test", currency="USD")

    import backend.orchestrator.controller as ctrl_mod
    # IMPORTANT: accept keyword args to match the controller's call signature
    monkeypatch.setattr(ctrl_mod, "search_flights", lambda **kwargs: fake_out)
 

    payload = {
        "user_id": "u1",
        "origin": "MEX",
        "destination": "FCO",
        "start_date": "2025-06-01",
        "end_date":   "2025-06-07",
        "budget_usd": 2500,
        "title": "Italy Week",
        "adults": 1
    }
    r = client.post("/v1/trips/plan", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["trip"]["title"] == "Italy Week"
    assert len(data["trip"]["days"]) == 7

def test_api_v1_trips_plan_bad_dates():
    # Missing/invalid date should 400
    payload = {
        "user_id": "u1",
        "origin": "MEX",
        "destination": "FCO",
        "start_date": "bad-date",
        "end_date":   "2025-06-07",
        "budget_usd": 2500
    }
    r = client.post("/v1/trips/plan", json=payload)
    assert r.status_code in (400, 422)
