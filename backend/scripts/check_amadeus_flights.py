import os, json, requests, sys
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()

HOST = os.getenv("AMADEUS_BASE", "https://test.api.amadeus.com")
CID  = os.environ["AMADEUS_CLIENT_ID"]
SEC  = os.environ["AMADEUS_CLIENT_SECRET"]

SESSION = requests.Session()
SESSION.headers.update({
    "Accept": "application/vnd.amadeus+json",
    "Content-Type": "application/x-www-form-urlencoded",  # token only
    "User-Agent": "AgenticPlanner/0.1 (+python-requests)"
})

# Known IATA airport sets for quick tests
CITY_TO_AIRPORTS = {
    "ROM": ["FCO", "CIA"],
    "NYC": ["JFK", "EWR", "LGA"],
    "SFO": ["SFO"],
    "MEX": ["MEX", "NLU", "TLC"],  # MEX=Benito Juarez, NLU=AIFA, TLC=Toluca
    "PAR": ["CDG", "ORY", "BVA"],
}

ROUTES = [
    ("MEX", "ROM"),   # CDMX -> Rome
    ("SFO", "ROM"),   # SF -> Rome
    ("JFK", "FCO"),   # NYC JFK -> Rome FCO
]

def pretty(label, resp):
    print(f"\n=== {label} ===")
    try:
        url = resp.request.url
    except Exception:
        url = "(POST body request; no URL params)"
    print("URL:", url)
    print("STATUS:", resp.status_code, resp.reason)
    try:
        data = resp.json()
        print(json.dumps(data, indent=2)[:2000])
        return data
    except Exception:
        print(resp.text[:1200])
        return None

def get_token():
    url = f"{HOST}/v1/security/oauth2/token"
    resp = SESSION.post(url, data={
        "grant_type": "client_credentials",
        "client_id": CID,
        "client_secret": SEC
    }, timeout=20)
    data = pretty("TOKEN", resp)
    resp.raise_for_status()
    tok = data["access_token"]
    # Switch headers for JSON calls
    SESSION.headers.pop("Content-Type", None)
    SESSION.headers["Authorization"] = f"Bearer {tok}"
    SESSION.headers["Accept"] = "application/json"
    return tok

def resolve_airports(code_or_city: str):
    """
    If given a city code like 'ROM' or 'NYC', return the known airports from the map.
    If given an airport (3 letters) and it's known, return as-is.
    """
    code_or_city = code_or_city.upper().strip()
    if len(code_or_city) == 3 and code_or_city in {a for v in CITY_TO_AIRPORTS.values() for a in v}:
        return [code_or_city]
    return CITY_TO_AIRPORTS.get(code_or_city, [code_or_city])

def flight_offers_search_v2(origin_air: str, dest_air: str, depart: str, ret: str | None,
                            adults: int = 1, currency: str = "USD", max_results: int = 20,
                            non_stop: bool | None = None):
    """
    POST /v2/shopping/flight-offers
    """
    body = {
        "currencyCode": currency,
        "originDestinations": [
            {
                "id": "1",
                "originLocationCode": origin_air,
                "destinationLocationCode": dest_air,
                "departureDateTimeRange": {"date": depart}
            }
        ],
        "travelers": [{"id": "1", "travelerType": "ADULT"} for _ in range(max(1, adults))],
        "sources": ["GDS"],
        "searchCriteria": {
            "maxFlightOffers": max_results
        }
    }
    if ret:
        body["originDestinations"].append({
            "id": "2",
            "originLocationCode": dest_air,
            "destinationLocationCode": origin_air,
            "departureDateTimeRange": {"date": ret}
        })
    if non_stop is not None:
        body["searchCriteria"]["flightFilters"] = {
            "carrierRestrictions": {},
            "connectionRestriction": {"maxNumberOfConnections": 0 if non_stop else 3}
        }

    resp = SESSION.post(f"{HOST}/v2/shopping/flight-offers", json=body, timeout=40)
    return resp

def summarize_offer(offer: dict) -> dict:
    price = (offer.get("price") or {})
    itineraries = offer.get("itineraries") or []
    carriers = set()
    total_durs = []

    for itin in itineraries:
        segs = itin.get("segments") or []
        total_durs.append(itin.get("duration"))
        for s in segs:
            mk = (s.get("carrierCode") or "") + (s.get("number") or "")
            if s.get("carrierCode"):
                carriers.add(s["carrierCode"])

    return {
        "total_price": price.get("total"),
        "currency": price.get("currency"),
        "carriers": sorted(list(carriers)),
        "one_way_count": len(itineraries),
        "durations": total_durs[:2],  # out + back if present
    }

def main():
    get_token()

    # Use dates ~60–90 days out from today to avoid "no fares" edge cases in test
    today = date.today()
    depart = (today + timedelta(days=60)).isoformat()
    ret    = (today + timedelta(days=67)).isoformat()

    for o_code, d_code in ROUTES:
        print(f"\n\n######## ROUTE {o_code} → {d_code} ########")
        origins = resolve_airports(o_code)
        dests   = resolve_airports(d_code)

        found_any = False
        for org in origins:
            for dst in dests:
                # Basic sanity: skip nonsensical 3-letter that's not airport-ish
                if len(org) != 3 or len(dst) != 3:
                    continue

                r = flight_offers_search_v2(
                    origin_air=org,
                    dest_air=dst,
                    depart=depart,
                    ret=ret,
                    adults=1,
                    currency="USD",
                    max_results=10,
                    non_stop=None,  # set True to force non-stop only
                )
                data = pretty(f"FLIGHTS {org}→{dst} ({depart}..{ret})", r)

                if not r.ok:
                    continue

                offers = (data or {}).get("data") or []
                warnings = (data or {}).get("warnings") or []
                errors = (data or {}).get("errors") or []

                if warnings:
                    print("\nWarnings:", json.dumps(warnings, indent=2)[:1200])
                if errors:
                    print("\nErrors:", json.dumps(errors, indent=2)[:1200])

                if offers:
                    found_any = True
                    print(f"\nParsed {min(len(offers), 3)} sample offers:")
                    for off in offers[:3]:
                        print(json.dumps(summarize_offer(off), indent=2))

            # If we found something for this origin with any dest, skip remaining dests
            if found_any:
                break

        if not found_any:
            print("No offers parsed for this route/date window. Try adjusting dates, airports, or non_stop filter.")

if __name__ == "__main__":
    main()
