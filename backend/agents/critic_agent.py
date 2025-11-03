from __future__ import annotations
from typing import Dict, Any, List, Optional
from datetime import datetime, time, timezone


class CriticAgent:
    name = "critic"

    def _parse_iso(self, s: Optional[str]) -> Optional[datetime]:
        """Handle 'Z' suffix and return a UTC-aware datetime if possible."""
        if not s:
            return None
        try:
            # Accept '...Z' or offset; normalize to UTC
            s2 = s.replace("Z", "+00:00")
            dt = datetime.fromisoformat(s2)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return None

    def run(self, *, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Looks for simple plan risks:
          - Activities scheduled on Day 1 before 10:00 (arrival fatigue)
          - >2 paid activities on any single day
          - No refundable lodging option used
        Expects in state:
          - trip (Trip)
          - activities_plan (dict[int, list[activity_dict]])
          - lodging_options (list[dict])
        """
        trip = state["trip"]
        activities = state.get("activities_plan", {}) or {}
        lodging_opts = state.get("lodging_options", []) or []

        issues: List[dict] = []
        suggestions: List[str] = []

        # 1) Day 1 early activities
        for a in activities.get(1, []):
            start = self._parse_iso(a.get("start_iso"))
            if start and start.time() < time(10, 0):
                title = a.get("title", "Activity")
                issues.append({
                    "type": "early_after_arrival",
                    "detail": f"Activity '{title}' before 10:00 on Day 1"
                })
                suggestions.append(
                    "Move first-day activities to afternoon or Day 2.")
                break

        # 2) Overpacked days (>2 paid)
        for idx, acts in activities.items():
            try:
                paid = [a for a in acts if float(
                    a.get("price_usd") or 0.0) > 0.0]
                if len(paid) > 2:
                    issues.append({
                        "type": "overpacked_day",
                        "detail": f"Day {idx} has {len(paid)} paid activities"
                    })
                    suggestions.append(
                        f"Reduce Day {idx} to at most 2 paid activities.")
            except Exception:
                # If anything is malformed, ignore that day instead of crashing
                continue

        # 3) Refundable lodging sanity
        if lodging_opts and not any(bool(o.get("refundable")) for o in lodging_opts):
            issues.append({
                "type": "no_refundable_lodging",
                "detail": "All hotels are non-refundable"
            })
            suggestions.append(
                "Offer at least one refundable hotel for flexibility.")

        decision = "approve" if not issues else "revise"
        return {
            "critic": {
                "issues": issues,
                "suggestions": list(dict.fromkeys(suggestions)),
                "decision": decision
            }
        }
