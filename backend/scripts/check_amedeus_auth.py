# scripts/check_amadeus_auth.py
import os, requests
from dotenv import load_dotenv
load_dotenv()

cid = os.getenv("AMADEUS_CLIENT_ID")
sec = os.getenv("AMADEUS_CLIENT_SECRET")
host = "https://test.api.amadeus.com"

assert cid and sec, "Missing AMADEUS_CLIENT_ID/SECRET"

r = requests.post(
    f"{host}/v1/security/oauth2/token",
    data={"grant_type":"client_credentials","client_id":cid,"client_secret":sec},
    timeout=15,
)
print("STATUS:", r.status_code)
print("BODY (truncated):", r.text[:300])
r.raise_for_status()
token = r.json()["access_token"]
print("OK token starts with:", token[:12], "...")
