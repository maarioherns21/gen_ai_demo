from __future__ import annotations
from typing import Dict, Any, List, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from backend.tools.events_api import search_activities
from backend.schemas.trip_schema import LineItem, LineItemType
import uuid

class ActivitiesAgent:
    name = "activities"

    def run(self, *, state: Dict[str, Any]) -> Dict[str, Any]:
        trip = state["trip"]
        city_code = (state.get("primary_city") or trip.destination).upper()
        max_per_day = int(state.get("max_activities_per_day", 2))
        skip_day1 = bool(state.get("skip_day1_activities", True))

        # Build a set of existing activity previews by (day_index, provider_ref)
        existing_keys: set[Tuple[int, str]] = set()
        for li in trip.line_items:
            li_type = li.type.value if hasattr(li.type, "value") else str(li.type)
            if li_type == "activity":
                pr = (li.meta or {}).get("provider_ref")
                # if you store day in meta, use it; otherwise compute from start_iso
                day_idx = (li.meta or {}).get("day_index")
                if pr and day_idx:
                    existing_keys.add((day_idx, pr))

        activities_plan: Dict[int, List[dict]] = {}

        for idx, _day in enumerate(trip.days, start=1):
            trip_day = trip.start_date + timedelta(days=idx - 1)

            # 1) Skip arrival day if configured
            if idx == 1 and state.get("skip_day1_activities", True):
                continue

            # 2) Exclude checkout day (no activities on end_date)
            #    If your "end_date" is intended to be exclusive, this prevents adding 2026-01-05.
            if trip_day >= trip.end_date:
                continue

            acts = search_activities(
                city_code=city_code,
                for_date=trip.start_date + timedelta(days=idx - 1),
                max_results=max_per_day
            )

            # Lock seconds/micros to zero for stability
            def lock_minute(iso: str | None) -> str | None:
                if not iso: return None
                dt = datetime.fromisoformat(iso.replace("Z",""))
                dt = dt.replace(second=0, microsecond=0)
                return dt.isoformat() + "Z"

            for a in acts:
                a["start_iso"] = lock_minute(a.get("start_iso"))
                a["end_iso"]   = lock_minute(a.get("end_iso"))

            activities_plan[idx] = acts

            # === Add exactly ONE preview line item per day (first result) ===
            if acts:
                first = acts[0]
                provider_ref = first.get("provider_ref")
                key = (idx, provider_ref or f"no-ref-{idx}")

                if key not in existing_keys:
                    trip.add_line_item(LineItem(
                        id=str(uuid.uuid4()),
                        trip_id=trip.id,
                        type=LineItemType.ACTIVITY,
                        vendor=first.get("title") or "Activity",
                        price_usd=Decimal(str(first.get("price_usd") or 0.0)),  # Amadeus often lacks price → 0.0
                        refundable=bool(first.get("refundable", True)),
                        terms={
                            "category": first.get("category") or "activity",
                            "provider": first.get("provider") or "amadeus_activities",
                        },
                        meta={
                            "start_iso": first.get("start_iso"),
                            "end_iso": first.get("end_iso"),
                            "provider_ref": provider_ref,
                            "day_index": idx,       # <-- enables idempotency on next runs
                            "date": trip_day.isoformat(),   # <— helpful for clients
                            "preview": True
                        },
                    ))
                    existing_keys.add(key)

        return {"activities_plan": activities_plan}

