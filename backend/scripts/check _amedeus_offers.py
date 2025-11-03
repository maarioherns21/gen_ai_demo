import os, json
from datetime import date, timedelta
from dotenv import load_dotenv
import requests

load_dotenv()

HOST = os.getenv("AMADEUS_BASE", "https://test.api.amadeus.com")
CID  = os.environ["AMADEUS_CLIENT_ID"]
SEC  = os.environ["AMADEUS_CLIENT_SECRET"]

def get_token(session: requests.Session) -> str:
    r = session.post(
        f"{HOST}/v1/security/oauth2/token",
        headers={"Accept": "application/vnd.amadeus+json"},
        data={"grant_type":"client_credentials","client_id":CID,"client_secret":SEC},
        timeout=15
    )
    r.raise_for_status()
    tok = r.json()["access_token"]
    session.headers.update({
        "Authorization": f"Bearer {tok}",
        "Accept": "application/vnd.amadeus+json"
    })
    return tok

def offers_by_city(session: requests.Session, city: str, check_in: date, check_out: date, adults: int = 1, currency="USD"):
    r = session.get(
        f"{HOST}/v2/shopping/hotel-offers/by-hotel",
        params={
            "cityCode": city,
            "checkInDate": check_in.isoformat(),
            "checkOutDate": check_out.isoformat(),
            "adults": str(adults),
            "currency": currency,
            "bestRateOnly": "true",
            "roomQuantity": "1",
            "view": "FULL",
        },
        timeout=25
    )
    return r

def main():
    session = requests.Session()
    get_token(session)

    city = os.getenv("CITY", "ROM")   # try ROM / PAR / NYC / MEX
    check_in  = date.today() + timedelta(days=30)
    check_out = check_in + timedelta(days=3)

    r = offers_by_city(session, city, check_in, check_out, adults=1, currency="USD")
    print("\n=== OFFERS ===")
    print("URL:", r.request.url)
    print("STATUS:", r.status_code, r.reason)
    data = r.json() if r.ok else {"errors": r.text}
    print(json.dumps(data, indent=2)[:4000])

    # Show a compact summary of the first 3 offers
    items = (data.get("data") or [])[:3]
    print(f"\nSummary ({len(items)} shown):")
    for i, block in enumerate(items, 1):
        hotel = block.get("hotel", {})
        offers = block.get("offers", []) or []
        cheapest = min(offers, key=lambda x: float(x.get("price", {}).get("total", "1e9"))) if offers else {}
        price = cheapest.get("price", {})
        cancel = (cheapest.get("policies", {}) or {}).get("cancellation", {})
        print(f"\n{i}. {hotel.get('name')}  [{hotel.get('hotelId')}]")
        print("   city:", hotel.get("address", {}).get("cityName"), "| rating:", hotel.get("rating"))
        print("   room:", (cheapest.get("room", {}) or {}).get("type"))
        print("   total:", price.get("total"), price.get("currency"), "| avg/night:", (price.get('variations') or {}).get('average', {}).get('base'))
        print("   refundable:", None if not cancel else (cancel.get('type') != 'NON_REFUNDABLE'))
        if cancel: print("   cancellation policy:", cancel)

if __name__ == "__main__":
    main()
