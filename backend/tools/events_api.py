from __future__ import annotations
import os, time, requests
from typing import List, Dict, Any, Optional, Tuple
from datetime import date, datetime, time as dtime, timezone
from dotenv import load_dotenv

load_dotenv()

# ---- Amadeus setup ----
AMA_HOST = os.getenv("AMADEUS_BASE", "https://test.api.amadeus.com")
AMA_CID  = os.getenv("AMADEUS_CLIENT_ID")
AMA_SEC  = os.getenv("AMADEUS_CLIENT_SECRET")
_ama_session = requests.Session()
_ama_token: Optional[str] = None
_ama_exp   = 0.0

def _ama_auth():
    """Fetch or reuse an Amadeus OAuth token."""
    global _ama_token, _ama_exp
    if not AMA_CID or not AMA_SEC:
        raise RuntimeError("Amadeus credentials not set")
    now = time.time()
    if _ama_token and now < _ama_exp - 60:
        return
    r = _ama_session.post(
        f"{AMA_HOST}/v1/security/oauth2/token",
        headers={"Accept": "application/vnd.amadeus+json"},
        data={"grant_type": "client_credentials",
              "client_id": AMA_CID,
              "client_secret": AMA_SEC},
        timeout=20
    )
    r.raise_for_status()
    j = r.json()
    _ama_token = j["access_token"]
    _ama_exp = now + int(j.get("expires_in", 1799))
    _ama_session.headers.update({
        "Authorization": f"Bearer {_ama_token}",
        "Accept": "application/json",
        "User-Agent": "AgenticPlanner/0.1 (+python-requests)"
    })

# Canonical city centers — extend as needed
CITY_LATLON: Dict[str, Tuple[float, float]] = {
    "PAR": (48.8566, 2.3522),
    "ROM": (41.9028, 12.4964),
    "NYC": (40.7128, -74.0060),
    "MEX": (19.4326, -99.1332),
    "SFO": (37.6213, -122.3790),
    "LAX": (33.9416, -118.4085),
}

def _iso_utc(dt: datetime) -> str:
    # ensure timezone-aware, then ISO Z
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ------------------ Public API ------------------

def search_activities(*, city_code: str,
                      for_date: date,
                      radius_km: float = 10.0,
                      max_results: int = 10) -> List[Dict[str, Any]]:
    """
    Fetch real Amadeus Tours & Activities near a city's center.
    Endpoint: /v1/shopping/activities  (or by-square if empty)
    """
    latlon = CITY_LATLON.get(city_code.upper())
    if not latlon:
        return []
    lat, lon = latlon

    _ama_auth()

    # 1) Try /shopping/activities (by radius)
    try:
        r = _ama_session.get(
            f"{AMA_HOST}/v1/shopping/activities",
            params={
                "latitude": f"{lat:.6f}",
                "longitude": f"{lon:.6f}",
                "radius": str(int(radius_km)),
            },
            timeout=20,
        )
        if r.ok:
            data = (r.json().get("data") or [])[:max_results]
        else:
            data = []
    except requests.RequestException:
        data = []

    # 2) Fallback: /shopping/activities/by-square if radius returns none
    if not data:
        delta = radius_km / 111.0  # approx degrees per km
        north, south = lat + delta, lat - delta
        east, west = lon + delta, lon - delta
        try:
            r2 = _ama_session.get(
                f"{AMA_HOST}/v1/shopping/activities/by-square",
                params={
                    "north": f"{north:.5f}",
                    "south": f"{south:.5f}",
                    "east": f"{east:.5f}",
                    "west": f"{west:.5f}",
                },
                timeout=20,
            )
            if r2.ok:
                data = (r2.json().get("data") or [])[:max_results]
        except requests.RequestException:
            pass

    # Normalize into your internal activity DTO
    out: List[Dict[str, Any]] = []
    # Build stable 10:00–12:00 slots **on the requested day**
    start_dt = datetime.combine(for_date, dtime(10, 0, 0), tzinfo=timezone.utc)
    end_dt   = datetime.combine(for_date, dtime(12, 0, 0), tzinfo=timezone.utc)

    for a in data:
        name = a.get("name") or "Activity"
        desc = (a.get("shortDescription") or "").strip()
        out.append({
            "title": name,
            "description": desc,
            "city": city_code.upper(),
            "start_iso": _iso_utc(start_dt),   # <-- anchored to for_date
            "end_iso":   _iso_utc(end_dt),     # <-- anchored to for_dates
            "price_usd": 0.0,
            "refundable": True,
            "category": "activity",
            "provider": "amadeus_activities",
            "provider_ref": a.get("id"),
        })
    return out
