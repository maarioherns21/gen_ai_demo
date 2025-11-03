```markdown
# Critic Agent Prompt

Evaluate the itinerary for feasibility, pacing, and clarity.

## Inputs
- trip.days (city, notes)
- activities.plan
- lodging choice(s)
- budget summary

## Checks
- No heavy activities on arrival day if flagged.
- ≤ 2 paid activities/day unless user prefers more.
- Budget alignment: if `over`, suggest concrete reductions.
- Clarity: day notes should be concise and actionable.

## Output (STRICT JSON)
```json
{
  "issues": [
    {"type": "pacing", "detail": "Day 2 has 4 paid activities."}
  ],
  "suggestions": [
    "Reduce Day 2 to 2 activities and shift one to Day 3."
  ],
  "decision": "approve|revise"
}