import os, json, requests, sys
from dotenv import load_dotenv

load_dotenv()

HOST = os.getenv("AMADEUS_BASE", "https://test.api.amadeus.com")
CID  = os.environ["AMADEUS_CLIENT_ID"]
SEC  = os.environ["AMADEUS_CLIENT_SECRET"]

SESSION = requests.Session()
SESSION.headers.update({
    "Accept": "application/vnd.amadeus+json",
    "Content-Type": "application/x-www-form-urlencoded",  # for token only
    "User-Agent": "AgenticPlanner/0.1 (+python-requests)"
})

CITY_CODES   = ["PAR", "ROM", "NYC", "MEX"]  # test a few known-good + your target
CITY_LATLON  = {
    "PAR": (48.8566, 2.3522),
    "ROM": (41.9028, 12.4964),
    "NYC": (40.7128, -74.0060),
    "MEX": (19.4326, -99.1332),
}

def pretty(label, resp):
    print(f"\n=== {label} ===")
    print("URL:", resp.request.url)
    print("STATUS:", resp.status_code, resp.reason)
    try:
        data = resp.json()
        print(json.dumps(data, indent=2)[:2000])
        return data
    except Exception:
        print(resp.text[:1000])
        return None

def get_token():
    url = f"{HOST}/v1/security/oauth2/token"
    resp = SESSION.post(url, data={
        "grant_type": "client_credentials",
        "client_id": CID,
        "client_secret": SEC
    }, timeout=15)
    data = pretty("TOKEN", resp)
    resp.raise_for_status()
    tok = data["access_token"]
    # Subsequent calls should send JSON accept but not the token form content-type
    SESSION.headers.pop("Content-Type", None)
    SESSION.headers["Authorization"] = f"Bearer {tok}"
    return tok

def hotels_by_city(city):
    url = f"{HOST}/v1/reference-data/locations/hotels/by-city"
    resp = SESSION.get(url, params={
        "cityCode": city,
        # Optional tuning; keep simple to avoid format issues first:
        # "radius": "20", "radiusUnit": "KM",
        # "page[limit]": "10",
    }, timeout=20)
    return resp

def hotels_by_geo(city):
    lat, lon = CITY_LATLON[city]
    url = f"{HOST}/v1/reference-data/locations/hotels/by-geocode"
    resp = SESSION.get(url, params={
        "latitude": f"{lat:.4f}",
        "longitude": f"{lon:.4f}",
        "radius": "10",
        "radiusUnit": "KM",
        # "page[limit]": "10",
    }, timeout=20)
    return resp

def map_hotel_list_item(h):
    """Normalize Amadeus Hotel List item -> simple dict for LodgingAgent preview."""
    addr = h.get("address", {})
    out = {
        "hotelId": h.get("hotelId"),
        "name": h.get("name"),
        "iataCity": h.get("iataCode") or h.get("cityCode"),
        "city": addr.get("cityName"),
        "country": addr.get("countryCode"),
        "address": " ".join(addr.get("lines", []) or []),
        "postalCode": addr.get("postalCode"),
        "geo": h.get("geoCode"),
        "chainCode": h.get("chainCode"),
        "dupeId": h.get("dupeId"),
        # Price & refundability come from *Hotel Search* (v3 offers) later:
        "refundable": None,
        "price_per_night_usd": None,
        "total_usd": None,
    }
    return out

def main():
    get_token()

    for city in CITY_CODES:
        print(f"\n\n######## CITY {city} ########")

        # 1) by-city
        r1 = hotels_by_city(city)
        data1 = pretty(f"HOTELS by-city ({city})", r1)

        if r1.ok and data1 and data1.get("data"):
            items = [map_hotel_list_item(x) for x in data1["data"][:5]]
            print(f"\nParsed {len(items)} items (by-city). First item:")
            print(json.dumps(items[0], indent=2))
            continue

        # 2) fallback by-geocode
        r2 = hotels_by_geo(city)
        data2 = pretty(f"HOTELS by-geocode ({city})", r2)
        if r2.ok and data2 and data2.get("data"):
            items = [map_hotel_list_item(x) for x in data2["data"][:5]]
            print(f"\nParsed {len(items)} items (by-geocode). First item:")
            print(json.dumps(items[0], indent=2))
        else:
            print(f"\nNo hotels parsed for {city}. Check error codes above.")

if __name__ == "__main__":
    main()
