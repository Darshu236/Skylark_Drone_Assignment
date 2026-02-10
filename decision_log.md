# Decision Log — Drone Operations Coordinator Agent

## Key Assumptions
- Mission data in `missions.csv` is authoritative for project dates, locations, and requirements.
- Pilot and drone `current_assignment` values map to `project_id` in `missions.csv`.
- If Google Sheets credentials are provided, Sheets are the source of truth; otherwise local CSVs are used.
- Capability mapping: Mapping/Survey/Inspection require RGB; Thermal requires Thermal.

## Trade-offs
- **Rule-based intent parsing** instead of a full LLM: faster to implement and deterministic, but less flexible.
- **Whole-sheet writes** for Google Sheets updates: simpler and reliable, but not optimal for large sheets.
- **In-memory processing**: adequate for small rosters, but would need a database for scale.

## Urgent Reassignments (Interpretation)
Urgent or High priority missions should be serviced first. If no eligible pilot/drone is available, the agent proposes reassigning a pilot from a lower-priority mission (Standard/Low) and highlights the trade-off.

## What I’d Do With More Time
- Use a real LLM for richer conversational parsing and explanations.
- Add a scheduling engine with hard/soft constraints and scoring.
- Implement per-row updates for Sheets and optimistic locking.
- Add authentication, audit trails, and user roles.

