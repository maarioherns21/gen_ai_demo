from datetime import date
import importlib
import pytest
import requests

# --- Locate the actual module path in your repo (tools/ vs root/) ---
MODULE_PATHS = ["backend.tools.flights_api", "backend.flights_api"]
mod = None
for path in MODULE_PATHS:
    try:
        mod = importlib.import_module(path)
        MODULE = path  # keep if you want to print/debug
        break
    except ImportError:
        continue
if mod is None:
    raise ImportError("Could not import backend.tools.flights_api or backend.flights_api")

search_flights = getattr(mod, "search_flights")


def _normalized_offer_stub(
    *,
    oid="1",
    currency="USD",
    total="999.99",
    carriers=("AA",),
    durations=("PT10H",),  # 1 for one-way, 2 for round-trip
):
    """
    Build a minimal Amadeus v2 flight-offers item.
    Your adapter's _normalize_offer() extracts price, carriers, durations, etc.
    """
    segs = [{"carrierCode": c} for c in carriers]
    itineraries = [{"duration": durations[0], "segments": segs}]
    if len(durations) > 1:
        itineraries.append({"duration": durations[1], "segments": segs})
    return {
        "id": oid,
        "price": {"currency": currency, "total": total},
        "itineraries": itineraries,
    }


# --------- Success: one-way search returns normalized list ----------
def test_search_flights_success_oneway(monkeypatch):
    # _post_offers returns data with two offers
    fake_payload = {
        "data": [
            _normalized_offer_stub(
                oid="A",
                currency="USD",
                total="812.45",
                carriers=("AM",),
                durations=("PT12H",),
            ),
            _normalized_offer_stub(
                oid="B",
                currency="USD",
                total="840.10",
                carriers=("AC", "LX"),
                durations=("PT14H30M",),
            ),
        ]
    }

    calls = []

    def fake_post_offers(body):
        # Capture body so we can assert construction
        calls.append(body)
        return fake_payload

    # IMPORTANT: patch the imported module object, not a string path
    monkeypatch.setattr(mod, "_post_offers", fake_post_offers, raising=True)

    out = search_flights(
        origin_code="MEX",
        dest_code="FCO",
        depart=date(2025, 6, 1),
        ret=None,
        adults=1,
        currency="USD",
        max_results=12,
        non_stop=None,
    )

    # Returns list of normalized offers
    assert isinstance(out, list)
    assert len(out) == 2

    first = out[0]
    assert first["id"] == "A"
    assert first["currency"] == "USD"
    assert first["total"] == "812.45"
    assert first["carriers"] == ["AM"]           # sorted unique
    assert first["itinerary_count"] == 1         # one-way
    assert first["durations"] == ["PT12H"]

    # Body was built correctly
    assert len(calls) == 1
    body = calls[0]
    assert body["currencyCode"] == "USD"
    assert body["travelers"] == [{"id": "1", "travelerType": "ADULT"}]
    assert body["sources"] == ["GDS"]
    assert body["searchCriteria"]["maxFlightOffers"] == 12
    assert "flightFilters" not in body["searchCriteria"]
    assert body["originDestinations"][0]["originLocationCode"] == "MEX"
    assert body["originDestinations"][0]["destinationLocationCode"] == "FCO"
    assert body["originDestinations"][0]["departureDateTimeRange"]["date"] == "2025-06-01"


# --------- Success: round-trip & non_stop=True wiring ----------
def test_search_flights_success_roundtrip_nonstop(monkeypatch):
    fake_payload = {
        "data": [
            _normalized_offer_stub(
                oid="R",
                currency="USD",
                total="1099.33",
                carriers=("SK",),
                durations=("PT9H", "PT10H"),  # out/back
            )
        ]
    }

    captured = {}

    def fake_post_offers(body):
        captured["body"] = body
        return fake_payload

    monkeypatch.setattr(mod, "_post_offers", fake_post_offers, raising=True)

    out = search_flights(
        origin_code="SFO",
        dest_code="ROM",                 # city, not airport
        depart=date(2025, 12, 27),
        ret=date(2026, 1, 3),
        adults=2,
        currency="USD",
        max_results=5,
        non_stop=True,
    )

    assert isinstance(out, list)
    assert len(out) == 1
    assert out[0]["id"] == "R"

    body = captured["body"]
    # travelers x2
    assert body["travelers"] == [
        {"id": "1", "travelerType": "ADULT"},
        {"id": "2", "travelerType": "ADULT"},
    ]
    # has 2 originDestinations for roundtrip
    assert len(body["originDestinations"]) == 2
    out_leg = body["originDestinations"][0]
    back_leg = body["originDestinations"][1]
    assert out_leg["departureDateTimeRange"]["date"] == "2025-12-27"
    assert back_leg["departureDateTimeRange"]["date"] == "2026-01-03"
    # non-stop filter wiring
    filters = body["searchCriteria"]["flightFilters"]
    assert filters["connectionRestriction"]["maxNumberOfConnections"] == 0


# --------- No results across airport permutations -> [] ----------
def test_search_flights_no_results(monkeypatch):
    # Always return empty list to force loop exhaustion
    def fake_post_offers(_body):
        return {"data": []}

    monkeypatch.setattr(mod, "_post_offers", fake_post_offers, raising=True)

    out = search_flights(
        origin_code="NYC",          # maps to JFK/EWR/LGA
        dest_code="ROM",            # maps to FCO/CIA
        depart=date(2025, 7, 1),
        ret=None,
        adults=1,
        currency="USD",
        max_results=10,
        non_stop=None,
    )
    assert out == []


# --------- Loop tries multiple airports: first empty, second returns data ----------
def test_search_flights_tries_next_airport(monkeypatch):
    calls = []

    def fake_post_offers(body):
        calls.append(body)
        # First call -> empty results, second call -> returns data
        if len(calls) == 1:
            return {"data": []}
        return {"data": [_normalized_offer_stub(oid="HIT")]}

    monkeypatch.setattr(mod, "_post_offers", fake_post_offers, raising=True)

    out = search_flights(
        origin_code="MEX",
        dest_code="ROM",            # should try FCO then CIA
        depart=date(2025, 8, 2),
        ret=None,
        adults=1,
        currency="USD",
        max_results=5,
        non_stop=None,
    )

    # First call empty, second call returns one offer
    assert len(calls) >= 2
    assert isinstance(out, list) and len(out) == 1
    assert out[0]["id"] == "HIT"

    # Assert we actually switched destination station on second try
    first_dest = calls[0]["originDestinations"][0]["destinationLocationCode"]
    second_dest = calls[1]["originDestinations"][0]["destinationLocationCode"]
    assert first_dest != second_dest  # e.g., FCO then CIA


# --------- HTTP error bubbles up (first attempt) ----------
def test_search_flights_http_error(monkeypatch):
    def fake_post_offers(_body):
        raise requests.HTTPError("500 Boom")

    monkeypatch.setattr(mod, "_post_offers", fake_post_offers, raising=True)

    with pytest.raises(requests.HTTPError):
        search_flights(
            origin_code="MEX",
            dest_code="FCO",
            depart=date(2025, 6, 1),
            ret=None,
            adults=1,
            currency="USD",
            max_results=12,
            non_stop=None,
        )
