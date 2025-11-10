from __future__ import annotations
import time, requests
from typing import Dict, Any, List, Optional
from datetime import date
from backend.config.settings import AMADEUS_BASE, AMADEUS_CLIENT_ID, AMADEUS_CLIENT_SECRET

_session = requests.Session()
_token: Optional[str] = None
_exp   = 0.0

def _auth():
    global _token, _exp
    now = time.time()
    if _token and now < _exp - 60:
        return
    r = _session.post(
        f"{AMADEUS_BASE}/v1/security/oauth2/token",
        headers={"Accept": "application/vnd.amadeus+json"},
        data={"grant_type":"client_credentials","client_id":AMADEUS_CLIENT_ID,"client_secret":AMADEUS_CLIENT_SECRET},
        timeout=20
    )
    r.raise_for_status()
    j = r.json()
    _token = j["access_token"]
    _exp = now + int(j.get("expires_in", 1799))
    _session.headers.update({
        "Authorization": f"Bearer {_token}",
        "Accept": "application/json"
    })

def _post_offers(body: Dict[str, Any]) -> Dict[str, Any]:
    _auth()
    r = _session.post(f"{AMADEUS_BASE}/v2/shopping/flight-offers", json=body, timeout=45)
    if not r.ok:
        raise requests.HTTPError(f"{r.status_code} {r.reason}: {r.text}", response=r)
    return r.json()

def _city_to_airports(code: str) -> List[str]:
    # minimal mapping; extend if you want (you can also call locations API)
    m = {
        "ROM": ["FCO", "CIA"],
        "NYC": ["JFK", "EWR", "LGA"],
        "MEX": ["MEX", "NLU", "TLC"],
        "SFO": ["SFO"],
        "LAX": ["LAX"],
        "PAR": ["CDG", "ORY", "BVA"],
    }
    return m.get(code.upper(), [code.upper()])

def _normalize_offer(off: Dict[str, Any]) -> Dict[str, Any]:
    price = off.get("price") or {}
    its   = off.get("itineraries") or []
    carriers = set()
    durs = []
    for it in its:
        durs.append(it.get("duration"))
        for s in (it.get("segments") or []):
            if s.get("carrierCode"):
                carriers.add(s["carrierCode"])
    return {
        "id": off.get("id"),
        "currency": price.get("currency"),
        "total": price.get("total"),
        "carriers": sorted(list(carriers)),
        "itinerary_count": len(its),   # 1 one-way, 2 roundtrip
        "durations": durs[:2],         # out/back
        "raw": off,                    # keep full payload for booking later
    }

def search_flights(*, origin_code: str, dest_code: str, depart: date, ret: Optional[date],
                   adults: int = 1, currency: str = "USD", max_results: int = 20,
                   non_stop: Optional[bool] = None) -> List[Dict[str, Any]]:
    """
    origin_code/dest_code may be a CITY (ROM) or AIRPORT (FCO).
    We try each airport variant until we get results.
    """
    origins = _city_to_airports(origin_code)
    dests   = _city_to_airports(dest_code)
    
    print("[Adapter] Amadeus params:", {
        "originLocationCode": origin_code,
        "destinationLocationCode": dest_code,
        "departureDate": str(depart),
        "returnDate": str(ret),
        "adults": adults,
        "nonStop": bool(non_stop) if non_stop is not None else None,
        "currencyCode": currency,
        "max": max_results
    })
    body_base = {
        "currencyCode": currency,
        "travelers": [{"id": str(i+1), "travelerType": "ADULT"} for i in range(max(1, adults))],
        "sources": ["GDS"],
        "searchCriteria": {"maxFlightOffers": max_results}
    }
    if non_stop is not None:
        body_base["searchCriteria"]["flightFilters"] = {
            "connectionRestriction": {"maxNumberOfConnections": 0 if non_stop else 3}
        }

    for o in origins:
        for d in dests:
            body = {**body_base}
            body["originDestinations"] = [{
                "id": "1",
                "originLocationCode": o,
                "destinationLocationCode": d,
                "departureDateTimeRange": {"date": depart.isoformat()}
            }]
            if ret:
                body["originDestinations"].append({
                    "id": "2",
                    "originLocationCode": d,
                    "destinationLocationCode": o,
                    "departureDateTimeRange": {"date": ret.isoformat()}
                })

            j = _post_offers(body)
            data = (j or {}).get("data") or []
            print("API FLIGHTS &&&&&&",data) 
            if data:
                return [_normalize_offer(x) for x in data]
    return []

