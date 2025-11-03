from __future__ import annotations
import os, time, requests, re, math
from typing import List, Dict, Any, Optional
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()

HOST = os.getenv("AMADEUS_BASE", "https://test.api.amadeus.com")
CID  = os.environ["AMADEUS_CLIENT_ID"]
SEC  = os.environ["AMADEUS_CLIENT_SECRET"]

_session = requests.Session()
_token: Optional[str] = None
_exp = 0.0

# Amadeus allows fairly short alphanumeric hotelIds; keep regex permissive
HOTEL_ID_RE = re.compile(r"^[A-Z0-9]{6,10}$")

# Optional canonical city centers to prefer geocode seeding (fallback to by-city)
CITY_LATLON: Dict[str, tuple[float, float]] = {
    "PAR": (48.8566, 2.3522),
    "ROM": (41.9028, 12.4964),
    "NYC": (40.7128, -74.0060),
    "MEX": (19.4326, -99.1332),
}


def _auth():
    global _token, _exp
    now = time.time()
    if _token and now < _exp - 60:
        return
    r = _session.post(
        f"{HOST}/v1/security/oauth2/token",
        headers={"Accept": "application/vnd.amadeus+json"},
        data={"grant_type": "client_credentials", "client_id": CID, "client_secret": SEC},
        timeout=15,
    )
    r.raise_for_status()
    j = r.json()
    _token = j["access_token"]
    _exp = now + int(j.get("expires_in", 1799))
    _session.headers.update({
        "Authorization": f"Bearer {_token}",
        "Accept": "application/vnd.amadeus+json",
        "User-Agent": "AgenticPlanner/0.1 (+python-requests)"
    })


def _hotel_list_by_city(city: str, limit: int = 60) -> List[Dict[str, Any]]:
    _auth()
    r = _session.get(
        f"{HOST}/v1/reference-data/locations/hotels/by-city",
        params={"cityCode": city},
        timeout=20
    )
    r.raise_for_status()
    return (r.json().get("data") or [])[:limit]


def _hotel_list_by_geocode(city: str, radius_km: float = 12.0, limit: int = 60) -> List[Dict[str, Any]]:
    """
    Prefer hotels near canonical city center when available to avoid far-out properties.
    NOTE: /by-geocode does not support page[limit] in test; keep params minimal.
    """
    _auth()
    latlon = CITY_LATLON.get(city)
    if not latlon:
        return []
    lat, lon = latlon

    # Amadeus is picky here; keep radius simple and within common bounds.
    r = max(1, min(int(round(radius_km)), 20))  # 1..20 KM

    try:
        resp = _session.get(
            f"{HOST}/v1/reference-data/locations/hotels/by-geocode",
            params={
                "latitude": f"{lat:.5f}",
                "longitude": f"{lon:.5f}",
                "radius": str(r),
                "radiusUnit": "KM",  # allowed; you can omit to use default KM
            },
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json().get("data") or []
        # Manually trim to 'limit' since page[limit] isn't supported here in test
        return data[:limit]
    except requests.HTTPError as e:
        # Log for visibility and let caller fall back to by-city
        print("by-geocode failed; falling back to by-city:", str(e))
        return []


def _offers_by_city(city: str, check_in: date, check_out: date, adults: int, currency: str) -> List[Dict[str, Any]]:
    _auth()
    r = _session.get(
        f"{HOST}/v3/shopping/hotel-offers",
        params={
            "cityCode": city,
            "checkInDate": check_in.isoformat(),
            "checkOutDate": check_out.isoformat(),
            "adults": str(adults),
            "currency": currency,
            "roomQuantity": "1",
            "bestRateOnly": "true",
            "view": "FULL",
        },
        timeout=25,
    )
    if not r.ok:
        raise requests.HTTPError(f"{r.status_code} {r.reason}: {r.text}", response=r)
    return r.json().get("data") or []


def _offers_by_ids_chunk(hids: List[str], check_in: date, check_out: date, adults: int, currency: str) -> Dict[str, Any]:
    """
    Return full JSON (so we can read warnings and filter bad IDs).
    """
    _auth()
    r = _session.get(
        f"{HOST}/v3/shopping/hotel-offers",
        params={
            "hotelIds": ",".join(hids),
            "checkInDate": check_in.isoformat(),
            "checkOutDate": check_out.isoformat(),
            "adults": str(adults),
            "currency": currency,
            "roomQuantity": "1",
            "bestRateOnly": "true",
            "view": "FULL",
        },
        timeout=25,
    )
    if not r.ok:
        raise requests.HTTPError(f"{r.status_code} {r.reason}: {r.text}", response=r)
    return r.json() or {}


def _by_hotels_enrich(hids: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Enrich city/country/address/rating via /by-hotels (chunks of up to ~20).
    Returns map of hotelId -> enrichment dict.
    """
    _auth()
    out: Dict[str, Dict[str, Any]] = {}
    if not hids:
        return out
    CHUNK = 20
    for i in range(0, len(hids), CHUNK):
        chunk = hids[i:i+CHUNK]
        r = _session.get(
            f"{HOST}/v1/reference-data/locations/hotels/by-hotels",
            params={"hotelIds": ",".join(chunk)},
            timeout=20,
        )
        if not r.ok:
            continue
        for h in r.json().get("data", []):
            out[h.get("hotelId")] = h
    return out


def _pick_cheapest_offer(offers: List[Dict[str, Any]], refundable_only: bool) -> Dict[str, Any] | None:
    def _is_refundable(o: Dict[str, Any]) -> bool:
        ref = ((o.get("policies") or {}).get("refundable") or {}).get("cancellationRefund")
        return ref != "NON_REFUNDABLE"

    bucket = [o for o in offers if _is_refundable(o)] if refundable_only else offers
    if not bucket:
        return None

    def _tot(o: Dict[str, Any]) -> float:
        p = o.get("price") or {}
        return float(p.get("total") or p.get("base") or 9e18)

    return min(bucket, key=_tot)


def _normalize_block(block: Dict[str, Any], *, refundable_only: bool = False) -> Dict[str, Any] | None:
    """
    Produce a stable DTO:
    {
      hotelId, name, city, country, rating, geo,
      room_type, board, currency, total, avg_per_night,
      refundable, refund_policy, cancel_deadline, raw_offer_id
    }
    """
    hotel = block.get("hotel") or {}
    offers = block.get("offers") or []
    chosen = _pick_cheapest_offer(offers, refundable_only=refundable_only)
    if not chosen:
        return None

    price = chosen.get("price") or {}
    total = float(price.get("total") or price.get("base") or 0.0)
    avg_base = ((price.get("variations") or {}).get("average") or {}).get("base")
    avg_total = ((price.get("variations") or {}).get("average") or {}).get("total")
    avg_per_night = float(avg_total or avg_base) if (avg_total or avg_base) else None

    policies = chosen.get("policies") or {}
    refund_code = (policies.get("refundable") or {}).get("cancellationRefund")
    refundable = refund_code != "NON_REFUNDABLE"

    cancel_deadline = None
    for c in (policies.get("cancellations") or []):
        if c.get("deadline"):
            cancel_deadline = c["deadline"]
            break

    room = chosen.get("room") or {}
    te = room.get("typeEstimated") or {}

    return {
        "hotelId": hotel.get("hotelId"),
        "name": hotel.get("name"),
        "city": None,                 # will be filled by enrichment
        "country": None,
        "rating": None,
        "geo": {"latitude": hotel.get("latitude"), "longitude": hotel.get("longitude")},
        "room_type": room.get("type"),
        "board": chosen.get("boardType"),
        "currency": price.get("currency", "USD"),
        "total": round(total, 2),
        "avg_per_night": round(avg_per_night, 2) if avg_per_night is not None else None,
        "refundable": bool(refundable),
        "refund_policy": refund_code,
        "cancel_deadline": cancel_deadline,
        "raw_offer_id": chosen.get("id"),
    }


def search_hotels(
    *,
    city: str,
    check_in: date,
    check_out: date,
    guests: int = 1,
    max_results: int = 20,
    currency: str = "USD",
    refundable_only: bool = False,
    max_km_from_center: float = 15.0,
) -> List[Dict[str, Any]]:
    """
    Robust search strategy:
      1) Ensure dates are in the future.
      2) Try city-wide offers (v3). If 477 (needs hotelIds), fall through.
      3) Seed hotelIds via by-geocode (preferred) then by-city; chunk requests.
      4) Parse provider warnings and auto-drop invalid/bad IDs.
      5) Enrich city/country/address/rating via /by-hotels for final DTOs.
    """
    today = date.today()
    if check_in <= today:
        # keep same trip length, push forward by 30 days to keep sandbox happy
        nights = max((check_out - check_in).days, 1)
        check_in = today + timedelta(days=30)
        check_out = check_in + timedelta(days=nights)

    # 1) city-wide offers (fast path)
    try:
        raw_city = _offers_by_city(city, check_in, check_out, adults=guests, currency=currency)
        if raw_city:
            normalized = []
            for block in raw_city:
                n = _normalize_block(block, refundable_only=refundable_only)
                if n:
                    normalized.append(n)
            if normalized:
                # Enrich basic location details from /by-hotels for nicer UI
                enrich_map = _by_hotels_enrich([x["hotelId"] for x in normalized if x.get("hotelId")])
                for item in normalized:
                    h = enrich_map.get(item["hotelId"]) or {}
                    addr = h.get("address") or {}
                    item["city"] = addr.get("cityName") or item["city"]
                    item["country"] = addr.get("countryCode") or item["country"]
                    item["rating"] = h.get("rating") or item["rating"]
                return normalized[:max_results]
    except requests.HTTPError as e:
        txt = (e.response.text if getattr(e, "response", None) else str(e))
        # Only swallow the classic 477 path; otherwise print and continue to IDs
        if '"code":477' not in txt and "Required parameter: hotelIds" not in txt:
            print("cityCode offers failed (non-477):", txt)

    # 2) hotelIds path — prefer geocode, then by-city
    seeded = _hotel_list_by_geocode(city, radius_km=max_km_from_center, limit=80)
    if not seeded or len(seeded) < 8:
        seeded = _hotel_list_by_city(city, limit=80)

    raw_ids = [h.get("hotelId") for h in seeded if h.get("hotelId")]
    valid_ids = [hid for hid in raw_ids if HOTEL_ID_RE.match(hid)]
    if not valid_ids:
        return []

    results: List[Dict[str, Any]] = []
    warnings_bad_ids: set[str] = set()
    CHUNK = 20  # v3 handles big chunks fine; warnings guide us

    for i in range(0, len(valid_ids), CHUNK):
        chunk = valid_ids[i:i+CHUNK]
        try:
            payload = _offers_by_ids_chunk(chunk, check_in, check_out, adults=guests, currency=currency)
        except requests.HTTPError as e:
            # Fallback to one-by-one to skip bad apples
            for hid in chunk:
                try:
                    p1 = _offers_by_ids_chunk([hid], check_in, check_out, adults=guests, currency=currency)
                    for b in (p1.get("data") or []):
                        n = _normalize_block(b, refundable_only=refundable_only)
                        if n:
                            results.append(n)
                except requests.HTTPError as ee:
                    print("skipped hotelId:", hid, str(ee))
            continue

        # Parse warnings to remove bad IDs from subsequent logic (informational here)
        for w in (payload.get("warnings") or []):
            src = ((w.get("source") or {}).get("parameter") or "")
            # src looks like "hotelIds=AAA,BBB"
            if "hotelIds=" in src:
                bads = src.split("hotelIds=", 1)[1].split(",")
                for b in bads:
                    b = b.strip()
                    if HOTEL_ID_RE.match(b):
                        warnings_bad_ids.add(b)

        for b in (payload.get("data") or []):
            n = _normalize_block(b, refundable_only=refundable_only)
            if n:
                results.append(n)
        if len(results) >= max_results:
            break

    # Enrich best results for city/country/rating
    deduped = { (x["hotelId"], x.get("raw_offer_id")): x for x in results if x.get("hotelId") }
    final_list = list(deduped.values())
    final_list.sort(key=lambda x: float(x.get("total") or 9e18))
    final_list = final_list[:max_results]

    enrich_map = _by_hotels_enrich([x["hotelId"] for x in final_list if x.get("hotelId")])
    for item in final_list:
        h = enrich_map.get(item["hotelId"]) or {}
        addr = h.get("address") or {}
        item["city"] = addr.get("cityName") or item["city"]
        item["country"] = addr.get("countryCode") or item["country"]
        # if Amadeus publishes rating here for your plan, capture it
        item["rating"] = h.get("rating") or item["rating"]

    return final_list


# from __future__ import annotations
# import os
# from datetime import date
# from typing import List, Dict, Any

# from amadeus import Client, ResponseError

# --- client bootstrap (same style as your flights adapter) --------------------

# def _client() -> Client:
#     host = os.getenv("AMADEUS_HOST", "test")
#     return Client(
#         client_id=os.getenv("AMADEUS_CLIENT_ID"),
#         client_secret=os.getenv("AMADEUS_CLIENT_SECRET"),
#         hostname="test" if host == "test" else "production",
#     )

# # Small map airport→city code (extend as you like)
# _AIRPORT_TO_CITY = {
#     "FCO": "ROM", "CIA": "ROM",
#     "MXP": "MIL", "LIN": "MIL", "BGY": "MIL",
#     "VCE": "VCE", "FLR": "FLR", "NAP": "NAP",
#     "JFK": "NYC", "LGA": "NYC", "EWR": "NYC",
#     "SFO": "SFO", "OAK": "SFO", "SJC": "SFO",
#     "MEX": "MEX",
# }

# def _to_city_code(city: str) -> str:
#     if not city:
#         return "ROM"
#     up = city.strip().upper()
#     if len(up) == 3:
#         return _AIRPORT_TO_CITY.get(up, up)  # airport→city or already city code
#     # minimal name mapping
#     name_map = {"ROME": "ROM", "MILAN": "MIL", "VENICE": "VCE", "NAPLES": "NAP", "FLORENCE": "FLR"}
#     return name_map.get(up, "ROM")

# # --- public function your LodgingAgent calls ----------------------------------

# def search_hotels(
#     *, city: str, check_in: date, check_out: date, guests: int = 1, max_results: int = 3
# ) -> List[Dict[str, Any]]:
#     """
#     Real hotel search via Amadeus Self-Service Hotels (Hotel Offers Search v3).
#     Returns a list of dicts shaped like your previous mock to keep agents unchanged.
#     """
#     amadeus = _client()
#     city_code = _to_city_code(city)
#     currency = os.getenv("CURRENCY", "USD")

#     # Amadeus: /v3/shopping/hotel-offers supports search by cityCode
#     params = {
#         "cityCode": city_code,
#         "checkInDate": check_in.isoformat(),
#         "checkOutDate": check_out.isoformat(),
#         "adults": str(guests),
#         "roomQuantity": "1",
#         "currency": currency,
#         # "bestRateOnly": "true",     # uncomment if you want only best rates
#         # "view": "FULL",             # FULL returns richer details
#         "sort": "PRICE",              # helps keep results predictable
#     }

#     try:
#         res = amadeus.shopping.hotel_offers_search.get(**params)  # SDK call
       
#     except ResponseError as e:
#         raise RuntimeError(f"Amadeus hotels error: {getattr(e, 'code', 'unknown')} {e}") from e

#     data = res.data or []
#     out: List[Dict[str, Any]] = []

#     for item in data:
#         if len(out) >= max_results:
#             break
#         hotel = item.get("hotel") or {}
#         offers = item.get("offers") or []
#         if not offers:
#             continue

#         # take the first offer as a sample
#         off = offers[0]
#         price = (off.get("price") or {})
#         total_str = price.get("grandTotal") or price.get("total")
#         try:
#             total = float(total_str) if total_str is not None else None
#         except Exception:
#             total = None

#         # refundability / cancellation (not always populated)
#         refundable = False
#         cancel_text = "See rate details"
#         policies = off.get("policies") or {}
#         cancellation = policies.get("cancellation")
#         if isinstance(cancellation, dict):
#             refundable = bool(cancellation.get("refundable", False))
#             cancel_text = (
#                 cancellation.get("description")
#                 or cancellation.get("type")
#                 or cancel_text
#             )

#         nights = max((check_out - check_in).days, 1)
#         ppn = round(total / nights, 2) if (total and nights) else total

#         out.append({
#             "name": hotel.get("name") or "Hotel",
#             "city": hotel.get("cityCode") or city_code,
#             "refundable": refundable,
#             "cancellation_policy": cancel_text,
#             "price_per_night_usd": ppn,
#             "total_usd": total,
#             "neighborhood": (hotel.get("address") or {}).get("cityName"),
#             "rating": hotel.get("rating"),  # often string like "4"
#             "room_type": ((off.get("room") or {}).get("type")
#                           or (off.get("room") or {}).get("description", {}).get("text")),
#         })

#     # If Amadeus returned nothing usable, raise so your fallback (if any) can kick in
#     if not out:
#         raise RuntimeError(f"No hotel offers returned for {city} ({city_code}) {check_in}→{check_out}")

#     return out


# def search_hotels(*, city: str, check_in: date, check_out: date, guests: int = 1, max_results: int = 3) -> List[Dict[str, Any]]:
#     """
#     Mock hotel search. Replace with real provider later (Booking/Expedia API).
#     """
#     nights = (check_out - check_in).days
#     base = [
#         {
#             "name": "Demo Inn Centro",
#             "city": city,
#             "refundable": True,
#             "cancellation_policy": "Free until 24h before check-in",
#             "price_per_night_usd": 120.0,
#             "total_usd": round(120.0 * max(nights, 1), 2),
#             "neighborhood": "Historic Center",
#             "rating": 8.6,
#             "room_type": "Double",
#         },
#         {
#             "name": "Traste Stay",
#             "city": city,
#             "refundable": False,
#             "cancellation_policy": "Non-refundable",
#             "price_per_night_usd": 95.0,
#             "total_usd": round(95.0 * max(nights, 1), 2),
#             "neighborhood": "Trastevere",
#             "rating": 8.1,
#             "room_type": "Queen",
#         },
#         {
#             "name": "Villa Verde Suites",
#             "city": city,
#             "refundable": True,
#             "cancellation_policy": "Free until 48h before",
#             "price_per_night_usd": 160.0,
#             "total_usd": round(160.0 * max(nights, 1), 2),
#             "neighborhood": "Near Park",
#             "rating": 9.0,
#             "room_type": "King",
#         },
#     ]
#     return base[:max_results]
