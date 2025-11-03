```markdown
# Tool Use Guidelines

- Only call tools exposed by the Tool Registry.
- Keep calls minimal:
  - `search_flights`: ≤ 1 per planning session; `max_results ≤ 12`.
  - `search_hotels`: ≤ 1 per planning session; `max_results ≤ 10`.
  - `search_activities`: ≤ 1 per day you actually need external data for.
- If a tool errors, continue planning with a reasonable estimate and add a note to `assumptions[]`.
- Never expose provider secrets or raw HTTP to the user.