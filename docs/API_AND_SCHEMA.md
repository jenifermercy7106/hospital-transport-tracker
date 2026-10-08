# API & Data Schema

> **Honest scope note.** The prototype today is a single Streamlit app over
> CSV files: it has **no HTTP endpoints and no database**. This document has
> three parts, clearly separated:
> 1. **Implemented** — the engine's Python function API (what `app.py` really calls)
> 2. **Implemented** — the CSV data schemas
> 3. **Planned design** — REST endpoints + SQL schema for the persistence phase
>    (`docs/schema.sql` is validated in SQLite; the endpoints are a spec, not code)

---

## 1. Engine function API (implemented) — `scripts/prototype_engine.py`

| Function | Input | Output | Side effects | Errors |
|---|---|---|---|---|
| `canonicalise_location(raw)` | str / None / NaN | `(location or None, state)`; state ∈ exact, corrected, missing, unrecognised | none | never raises |
| `validate_requests(df)` | DataFrame of requests | **copy** + `resolved_source`, `resolved_destination`, `resolved_urgency`, `data_confidence`, `data_issues` | none (input not mutated) | never raises on bad values; never drops rows |
| `score_priority(urgency, waiting_minutes, data_confidence)` | str, float, str | float score (higher = first) | none | unknown urgency scored as Urgent |
| `recommend_porter(source_zone, porters_status)` | int or None; `{porter_id: {"zone": int, "available_at": Timestamp}}` | `(porter_id or None, reason)` | none (read-only) | empty roster / unresolved zone -> `(None, reason)` |
| `detect_sla_state(ts_requested, ts_handover, ts_arrived, sla_minutes, now=None)` | Timestamps (NaT ok), int, optional Timestamp | Completed-OnTime, Completed-Late, On-Track, At-Risk, Breached, Open, Unknown-BadTimestamps | none | bad/missing times -> `Unknown-BadTimestamps` |
| `simulate_queue(df, porters_df)` | requests, roster | requests + `prototype_*` outcome columns | none | empty roster -> all escalated |
| `simulate_queue_with_reserve(df, porters_df, reserved_porter_ids, emergency_overflow_wait_min=5)` | as above + reserve set | as above + `prototype_pool_used` | none | unknown reserved IDs ignored |
| `baseline.py: run_baseline(...)` | requests | FIFO outcome columns | none | — |

Constants: `URGENCY_BASE_SCORE` (100/60/20), `URGENCY_SLA_MIN` (10/30/90),
`ZONE` (location -> 1..5), `LOCATION_ALIASES`. Service-time model used in
simulations: `6 + 2.5 x zone_distance` minutes.

**Contract that matters most:** every function above is read-only. State
changes exist only in `app.py` button handlers (assign, override, handover,
release, cancel), each of which calls `log_action(...)`.

---

## 2. CSV schemas (implemented) — `data/`

### `transport_requests.csv` (662 rows, 16 columns)

| Column | Type | Meaning | Messiness deliberately included |
|---|---|---|---|
| `request_id` | str, unique | e.g. `REQ00567` | — |
| `patient_id` | str | synthetic `PTnnnn` | — |
| `department` | str | requesting department | — |
| `reason` | str | free text | — |
| `timestamp_requested` | datetime str | when the call came in | some blank |
| `source_location` / `destination_location` | str | location as logged | blanks, typos, free text |
| `urgency` | Emergency / Urgent / Routine | as stated on the call | some blank |
| `requested_by` | str | role of caller | — |
| `porter_id` | str | assigned porter (historical) | blank if missed |
| `timestamp_assigned` / `timestamp_arrived_source` / `timestamp_handover_confirmed` | datetime str | lifecycle times | blank if missed; some out of order (clock skew) |
| `sla_minutes` | int | target minutes | — |
| `status` | Completed / Delayed / Missed / Cancelled | historical outcome | — |
| `delay_reason` | str | reason for delay/miss | blank when Completed |

Historical outcome mix: Completed 426, Missed 138, Delayed 75, Cancelled 23.

### `porters.csv` (8 rows)
`porter_id` (str, PK) · `name` · `home_zone` (1..5) · `shift_start_hour` · `shift_end_hour`

### `locations.csv` (20 rows)
`location` (str, PK) · `zone` (1..5)

### Columns added at runtime
- By `validate_requests`: `resolved_source`, `resolved_destination`, `resolved_urgency`, `data_confidence`, `data_issues`
- By `app.py`: `live_status` (Open / Handover Confirmed / Cancelled), `assigned_porter_live`, plus per-render `waiting_minutes`, `priority_score`, `recommended_porter`, `recommendation_reason`, `sla_state`
- By simulations: `prototype_wait_minutes`, `prototype_assigned_porter`, `prototype_sla_outcome`, `prototype_escalated_for_review`, `prototype_missed_or_late` (and `prototype_pool_used` for the reserve variant)

### In-session audit log (`st.session_state.action_log`)
`timestamp` (real clock) · `staff_name` · `staff_role` · `action` · `request_id` · `detail`

---

## 3. PLANNED: REST API (design only — not implemented)

Base path `/api/v1`. All writes require an authenticated staff identity; the
server stamps `staff_id` and time itself (client cannot supply them).
Recommendations are `GET` (safe, no state change); every state change is an
explicit `POST` by a human, mirroring the app's button handlers.

| Method & path | Purpose | Request body | Success | Errors |
|---|---|---|---|---|
| `POST /requests` | log a request (runs validation) | `patient_id, source, destination, urgency?, reason` | `201` + request with `data_confidence`, `data_issues` | `400` only if `patient_id` missing; messy location/urgency is **accepted and flagged**, not rejected |
| `GET /requests?status=Open` | live queue, sorted by priority | — | `200` list with `priority_score`, `sla_state` | — |
| `GET /requests/{id}` | one request + its action history | — | `200` | `404` |
| `GET /requests/{id}/recommendation` | porter suggestion (read-only) | — | `200 {porter_id\|null, reason, confidence}` | `404` |
| `POST /requests/{id}/assignment` | **staff** confirms/overrides porter | `{porter_id}` | `200`; logs *Confirmed assignment* or *Overrode recommendation* | `404`; `409` already assigned or not Open; `422` blank/unknown porter |
| `POST /requests/{id}/handover` | **staff** confirms handover | — | `200`; sets `handover_confirmed_at` | `409` not assigned / not Open |
| `POST /requests/{id}/release` | release porter back to queue | `{reason}` | `200`; logs *Escalated / released porter* | `409` not assigned |
| `POST /requests/{id}/cancel` | cancel duplicate/erroneous | `{reason}` | `200` | `409` already closed |
| `GET /porters` | roster + current availability | — | `200` | — |
| `GET /audit?request_id=` | read-only audit trail | — | `200` | — |
| `GET /metrics/sla` | missed/late rate by urgency | — | `200` | — |

Error body (uniform): `{"error": "<code>", "message": "<human text>", "request_id": "<id|null>"}`.
Rule carried over from the prototype: **no endpoint assigns, completes, or cancels without a human-initiated call.**

## 4. PLANNED: database schema — `docs/schema.sql`

Tables: `locations`, `porters`, `staff`, `transport_requests`, `action_log`.

Design decisions:
- Raw input kept next to resolved values (`source_raw` vs `source_resolved`) so uncertainty and original wording are never lost.
- `CHECK` constraints reject invalid urgency/confidence/status at the database level.
- `action_log` is append-only, enforced by triggers (UPDATE/DELETE abort) — the accountability guarantee is a property of the database, not just app code.
- `assigned_porter_id` and `handover_confirmed_at` are written only by the staff-action endpoints.
- Validated by loading into SQLite and checking that illegal updates/deletes and invalid enum values are rejected:

```bash
python - <<'PY'
import sqlite3; c = sqlite3.connect(":memory:"); c.executescript(open("docs/schema.sql").read()); print("schema OK")
PY
```

Migration path: SQLite for a single-ward pilot (zero install, stdlib) ->
PostgreSQL when multiple wards need concurrent writes.
