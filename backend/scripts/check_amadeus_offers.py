import os, json, requests
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

CITY_CODES = ["ROM", "NYC", "MEX"]
CHECK_IN_OFFSET_DAYS = int(os.getenv("CHECK_IN_OFFSET_DAYS", "30"))
LENGTH_OF_STAY_DAYS  = int(os.getenv("LENGTH_OF_STAY_DAYS", "3"))
CURRENCY             = os.getenv("CURRENCY", "USD")
ADULTS               = int(os.getenv("ADULTS", "1"))

# ----------- utils -----------
def pretty(label, obj_or_resp, maxchars=4000):
    print(f"\n=== {label} ===")
    if hasattr(obj_or_resp, "request"):
        try:
            print("URL:", obj_or_resp.request.url)
        except Exception:
            pass
        if hasattr(obj_or_resp, "status_code"):
            print("STATUS:", obj_or_resp.status_code, getattr(obj_or_resp, "reason", ""))
    try:
        data = obj_or_resp.json() if hasattr(obj_or_resp, "json") else obj_or_resp
        print(json.dumps(data, indent=2)[:maxchars])
        return data
    except Exception:
        print(getattr(obj_or_resp, "text", str(obj_or_resp))[:1200])
        return None

def get_token():
    r = SESSION.post(
        f"{HOST}/v1/security/oauth2/token",
        data={"grant_type":"client_credentials","client_id":CID,"client_secret":SEC},
        timeout=15
    )
    data = pretty("TOKEN", r)
    r.raise_for_status()
    SESSION.headers.pop("Content-Type", None)
    SESSION.headers["Authorization"] = f"Bearer {data['access_token']}"

def hotels_by_city(city_code):
    return SESSION.get(f"{HOST}/v1/reference-data/locations/hotels/by-city",
                       params={"cityCode": city_code}, timeout=20)

def offers_v3_by_ids(hotel_ids, check_in, check_out, adults=1, currency="USD"):
    return SESSION.get(f"{HOST}/v3/shopping/hotel-offers",
                       params={
                           "hotelIds": ",".join(hotel_ids[:20]),
                           "checkInDate": check_in.isoformat(),
                           "checkOutDate": check_out.isoformat(),
                           "adults": str(adults),
                           "currency": currency,
                           "bestRateOnly": "true",
                           "roomQuantity": "1",
                           "view": "FULL",
                       }, timeout=25)

def hotels_by_hotels(hotel_ids):
    """Enrich: address/city/rating often live here."""
    return SESSION.get(f"{HOST}/v1/reference-data/locations/hotels/by-hotels",
                       params={"hotelIds": ",".join(hotel_ids[:20])}, timeout=20)

# ----------- normalization -----------
def parse_refundability(offer):
    # v3: policies.refundable.cancellationRefund in {"NON_REFUNDABLE", "REFUNDABLE_UP_TO_DEADLINE", ...}
    pol = offer.get("policies") or {}
    ref = pol.get("refundable") or {}
    val = ref.get("cancellationRefund")
    if not val:
        # fallback: some providers only give cancellations[]
        cancels = pol.get("cancellations") or []
        if cancels:
            return True  # has cancellation rules ⇒ refundable up to deadline
        return None
    return False if val == "NON_REFUNDABLE" else True

def first_cancel_deadline(offer):
    cancels = (offer.get("policies") or {}).get("cancellations") or []
    if not cancels:
        return None
    # pick earliest deadline if present
    deadlines = [c.get("deadline") for c in cancels if c.get("deadline")]
    return sorted(deadlines)[0] if deadlines else None

def avg_per_night(price, nights):
    # Prefer variations.average.base/total; otherwise compute base/total per night
    var = (price or {}).get("variations") or {}
    avg = (var.get("average") or {})
    return avg.get("base") or avg.get("total") or (
        None if not price else
        f"{float(price.get('total', price.get('base', '0'))) / max(nights,1):.2f}"
    )

def normalize_block_v3(block, hotel_map, nights):
    hotel = block.get("hotel") or {}
    offers = block.get("offers") or []
    if not offers:
        return None

    # choose cheapest
    cheapest = min(offers, key=lambda x: float((x.get("price") or {}).get("total", "1e9")))

    # enrich with details
    hid = hotel.get("hotelId")
    enrich = hotel_map.get(hid, {})
    addr = enrich.get("address") or {}

    price = cheapest.get("price") or {}
    return {
        "hotelId": hid,
        "name": enrich.get("name") or hotel.get("name"),
        "city": addr.get("cityName"),
        "country": addr.get("countryCode"),
        "rating": enrich.get("rating"),
        "geo": {
            "latitude": enrich.get("geoCode", {}).get("latitude", hotel.get("latitude")),
            "longitude": enrich.get("geoCode", {}).get("longitude", hotel.get("longitude"))
        },
        "room_type": (cheapest.get("room") or {}).get("type"),
        "total": price.get("total") or price.get("base"),
        "currency": price.get("currency"),
        "avg_per_night": avg_per_night(price, nights),
        "refundable": parse_refundability(cheapest),
        "cancel_deadline": first_cancel_deadline(cheapest),
        "raw_offer_id": cheapest.get("id"),
    }

# ----------- main flow -----------
def main():
    get_token()
    check_in  = date.today() + timedelta(days=CHECK_IN_OFFSET_DAYS)
    check_out = check_in + timedelta(days=LENGTH_OF_STAY_DAYS)
    nights = (check_out - check_in).days

    for city in CITY_CODES:
        print(f"\n\n######## CITY {city} ########")

        # 1) list hotels → hotelIds
        r_hot = hotels_by_city(city)
        d_hot = pretty(f"HOTELS by-city ({city})", r_hot)
        if not r_hot.ok or not d_hot or not d_hot.get("data"):
            print("No hotels; skipping.")
            continue
        ids = [h.get("hotelId") for h in d_hot["data"] if h.get("hotelId")][:20]
        print(f"\nCollected {len(ids)} hotelIds (first 5): {ids[:5]}")

        # 2) v3 offers by hotelIds
        r_off = offers_v3_by_ids(ids, check_in, check_out, adults=ADULTS, currency=CURRENCY)
        d_off = pretty(f"OFFERS v3 (by hotelIds) {city}", r_off)
        blocks = (d_off or {}).get("data") or []

        # If warnings indicate invalid IDs, we'll still proceed with the valid blocks.
        warns = (d_off or {}).get("warnings") or []
        if warns:
            print("\nWarnings from provider:")
            for w in warns:
                print("-", w.get("title"), "|", w.get("detail"), "| source:", (w.get("source") or {}).get("parameter"))

        if not blocks:
            print("No offers returned; skip enrichment.")
            continue

        # 3) Enrich via by-hotels
        enrich_ids = list({(b.get("hotel") or {}).get("hotelId") for b in blocks if (b.get("hotel") or {}).get("hotelId")})
        r_enrich = hotels_by_hotels(enrich_ids)
        d_enrich = pretty(f"ENRICH by-hotels ({city})", r_enrich)
        hotel_map = {h["hotelId"]: h for h in (d_enrich or {}).get("data", []) if h.get("hotelId")}

        # 4) Summaries
        print(f"\nSummary v3 enriched (up to 5):")
        shown = 0
        for b in blocks:
            n = normalize_block_v3(b, hotel_map, nights)
            if not n:
                continue
            print(json.dumps(n, indent=2))
            shown += 1
            if shown >= 5:
                break

if __name__ == "__main__":
    main()

