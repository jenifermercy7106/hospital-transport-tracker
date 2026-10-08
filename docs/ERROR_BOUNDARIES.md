# Error Boundaries

An *error boundary* is a place where bad input or failure is stopped,
labelled, and handed to a human instead of crashing or being silently
guessed. Principle throughout: **fail visible, never fail silent; escalate,
never guess.**

## Boundary map (data flow)

```
phone/UI input -> [B1 validate_requests] -> [B2 score_priority] -> [B3 recommend_porter]
                                                                          |
                                         staff click (human gate) <-------+
                                                |
                          [B5 app.py action handlers] -> [B6 audit log]
 timestamps -> [B4 detect_sla_state]
```

| # | Boundary | Where | Bad input / failure | What the system does | Staff sees | Tested by |
|---|---|---|---|---|---|---|
| B1a | Location parsing | `canonicalise_location` | None / NaN / "" | state `missing`, location `None` | "source location missing", **Low** confidence | `TestCanonicaliseLocation`, EC1 |
| B1b | | | typo / free text | alias or substring match, state `corrected` | "auto-corrected from free text", **Medium** | `TestCanonicaliseLocation`, EC2 |
| B1c | | | unmatched text | state `unrecognised`, **no guess** | "unrecognised: '<text>'", **Low** | `TestCanonicaliseLocation` |
| B1d | Urgency | `validate_requests` | blank / invalid urgency | defaults to **Urgent** (never Routine) | "defaulted to Urgent pending clinician review" | `TestValidateRequests`, EC3 |
| B1e | Timestamp | `validate_requests` | missing request time | row kept, issue recorded | "request timestamp missing" | `TestValidateRequests` |
| B1f | Row loss | `validate_requests` | any defect | **never drops a row**; input not mutated | row still visible | `TestValidateRequests` |
| B2 | Ranking | `score_priority` | unknown urgency; very long wait | scored as Urgent; aging capped at +40 | queue order | `TestScorePriority` |
| B3a | Recommendation | `recommend_porter` | empty roster | `(None, "No porter roster loaded")` | "none available" | `TestRecommendPorter`, EC6 |
| B3b | | | unresolved source | `(None, "...unresolved")` — no guess | "none available", must choose manually | `TestRecommendPorter` |
| B3c | | | all porters busy | still ranks soonest-available; wait shown | waiting time / SLA colour | EC5 |
| B4a | SLA state | `detect_sla_state` | handover before arrival | `Unknown-BadTimestamps` | flagged for review | `TestDetectSlaState`, EC4 |
| B4b | | | negative duration / missing request time | `Unknown-BadTimestamps` | flagged for review | `TestDetectSlaState` |
| B5a | Human gate | `app.py` | blank porter on "Confirm assignment" | **refused** with warning, nothing logged | "choose a porter before confirming" | manual (checklist below) |
| B5b | | | any state change | only reachable via a staff button | action requires name/role | `live_runthrough.py` |
| B6 | Audit | `log_action` | — | append-only record: who, role, action, request, detail, real time | audit-trail expander | `live_runthrough.py` |
| B7 | Reserve config | `simulate_queue_with_reserve` | reserved ID not in roster | degrades to no reserve | (experiment only) | `TestSimulateQueueWithReserve`, EC8 |
| B8 | Reserve overload | same | Emergency burst > reserve | overflows to general pool | (experiment only) | EC7 |

EC# = case number in `scripts/edge_cases.py` / report Section 5.

## Design rules behind the boundaries

1. **Defaults err toward safety.** Unknown urgency -> Urgent. Unknown location -> no recommendation (not a guess).
2. **Uncertainty is displayed, not hidden.** Every request carries `data_confidence` + `data_issues`; Low-confidence requests get a +6 queue boost so they get *looked at*.
3. **No silent drops.** Output row count always equals input row count.
4. **Recommend vs decide.** Engine functions are pure/read-only (asserted by test); only `app.py` buttons change state, each writing an audit record.
5. **Aging can't invert safety.** Max Routine score 66 < min Emergency 100.

## Known residual risks (not yet bounded)

| Risk | Impact | Planned handling |
|---|---|---|
| Substring fallback in `canonicalise_location` is permissive (e.g. "ward") | wrong auto-correction, but always flagged Medium for staff | tighten to alias/edit-distance matching; require staff confirm on corrected locations |
| In-memory session state; refresh loses live actions | lost audit trail in a real deployment | DB-backed persistence (`docs/API_AND_SCHEMA.md`) |
| Free-text staff name/role (no authentication) | audit not tamper-evident | authenticated logins before any pilot |
| Zone distance is a proxy for walking distance | ETA error | real floor-plan / porter-position data |
| SLA minutes (10/30/90) are illustrative | wrong alerting thresholds | clinical sign-off |

## Manual click-through checklist (for `streamlit run app.py`)

- [ ] Open a request with **no suggested porter**; click *Confirm assignment* with blank selection -> warning shown, no new row in audit log.
- [ ] Log a new request with urgency blank + source "ward a1" -> shows Medium confidence, urgency Urgent, issue text visible.
- [ ] Log a request with garbage source -> Low confidence, "unresolved", no porter suggested.
- [ ] Override the suggested porter -> audit log says *Overrode recommendation* with both IDs.
- [ ] Confirm handover -> request leaves the open queue, audit entry present with your name/role.
- [ ] Cancel a request -> appears under *Completed / cancelled*, audit entry present.
- [ ] Move the demo-clock slider -> SLA colours change; audit timestamps still use real time.
- [ ] Refresh the page -> state resets (expected for the prototype; see risks above).
