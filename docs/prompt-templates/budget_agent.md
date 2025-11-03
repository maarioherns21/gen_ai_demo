```markdown
# Budget Agent Prompt

Aggregate flight, hotel, and activity costs and determine status vs. budget.

## Inputs
- budget_cap (USD)
- flight_options (with sample price)
- selected hotel (or sample)
- activity plan with estimated prices

## Rules
- Sum totals; if flight/hotel has a range, use sample or min.
- Mark status:
  - `under` if total <= cap
  - `over` if total > cap
- Provide a 1–2 line summary + tradeoffs.

## Output (STRICT JSON)
```json
{
  "total_usd": 0.0,
  "cap_usd": 0.0,
  "status": "under|over",
  "delta_usd": 0.0,
  "summary": "string",
  "suggested_tradeoffs": ["string"]
}