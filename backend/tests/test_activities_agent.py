import uuid
from datetime import date, datetime

# SUT
from backend.agents.activity_agent import ActivitiesAgent

# ---- Minimal in-test Trip stub so we don't depend on your schemas ----
class FakeLineItem:
    def __init__(self, **kw):
        self.__dict__.update(kw)
        # emulate your enum usage in code: LineItemType.ACTIVITY/HOTEL
        # Here we just pass a string; agent reads str(li.type) or li.type.value
        self.type = kw.get("type")
        self.meta = kw.get("meta", {})

class FakeTrip:
    def __init__(self, *, origin, destination, start_date, end_date, days_count):
        self.id = str(uuid.uuid4())
        self.origin = origin
        self.destination = destination
        self.start_date = start_date
        self.end_date = end_date
        # Just a list with the right length; agent never inspects day objects themselves
        self.days = [object() for _ in range(days_count)]
        self.line_items = []

    def add_line_item(self, li):
        # The real code calls with a dataclass LineItem; accept dict or object
        if isinstance(li, dict):
            self.line_items.append(FakeLineItem(**li))
        else:
            self.line_items.append(li)

# ---- Helpers ----
def _mk_activity(provider_ref="169057", title="Sample Tour", start_iso=None, end_iso=None):
    return {
        "title": title,
        "description": "desc",
        "city": "ROM",
        "start_iso": start_iso or "2026-01-03T10:00:00Z",
        "end_iso": end_iso   or "2026-01-03T12:00:00Z",
        "price_usd": 0.0,
        "refundable": True,
        "category": "activity",
        "provider": "amadeus_activities",
        "provider_ref": provider_ref,
    }

# ------------------ TESTS ------------------

def test_activities_agent_skips_arrival_excludes_checkout_and_idempotent(monkeypatch):
    """
    With start=2026-01-02, end=2026-01-05 (exclusive), and skip_day1=True,
    activities should be created for Jan 3 and Jan 4 ONLY (days 2 and 3),
    not for Jan 2 (arrival) nor Jan 5 (checkout). Running twice should not duplicate.
    """
    agent = ActivitiesAgent()

    # Stub provider: always returns one activity
    def fake_search_activities(city_code, for_date, radius_km=10.0, max_results=10):
        # anchor times to requested for_date
        start_iso = datetime.combine(for_date, datetime.min.time()).replace(hour=10).isoformat() + "Z"
        end_iso   = datetime.combine(for_date, datetime.min.time()).replace(hour=12).isoformat() + "Z"
        return [_mk_activity(start_iso=start_iso, end_iso=end_iso)]

    monkeypatch.setattr("backend.agents.activity_agent.search_activities", fake_search_activities)

    # Trip: 2026-01-02 .. 2026-01-05 (exclusive); 4 days in planner.days is common
    trip = FakeTrip(
        origin="MEX",
        destination="ROM",
        start_date=date(2026, 1, 2),
        end_date=date(2026, 1, 5),
        days_count=4,
    )

    state = {
        "trip": trip,
        "primary_city": "ROM",
        "max_activities_per_day": 2,
        "skip_day1_activities": True,   # skip arrival day
    }

    # First run
    out1 = agent.run(state=state)
    # Second run (should be idempotent; no new preview items)
    out2 = agent.run(state=state)

    # Expect activities_plan only for indices 2 and 3 (not 1 or 4)
    assert 2 in out1["activities_plan"] and 3 in out1["activities_plan"]
    assert 1 not in out1["activities_plan"]
    assert 4 not in out1["activities_plan"]

    # Exactly two activity line items (one per eligible day)
    li_acts = [li for li in trip.line_items if (li.type == "activity" or getattr(li.type, "value", "") == "activity")]
    assert len(li_acts) == 2

    # Timestamps minute-locked and match the right days (10:00–12:00)
    expected = {
        "2026-01-03T10:00:00Z": "2026-01-03T12:00:00Z",
        "2026-01-04T10:00:00Z": "2026-01-04T12:00:00Z",
    }
    got = {li.meta["start_iso"]: li.meta["end_iso"] for li in li_acts}
    assert got == expected

    # Idempotency: running twice didn’t add more
    out2  # just to show we used it
    li_acts_again = [li for li in trip.line_items if (li.type == "activity" or getattr(li.type, "value", "") == "activity")]
    assert len(li_acts_again) == 2
