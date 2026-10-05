"""
edge_cases.py
-------------
Realistic failure-state tests for the Hospital Transport Request Tracker
prototype. Each test feeds the engine a deliberately broken / ambiguous
input and asserts that the system degrades SAFELY:
  - it never crashes
  - it never silently drops a request
  - it never auto-finalises an action without staff confirmation
  - it always communicates uncertainty rather than guessing silently

Run: python3 scripts/edge_cases.py
"""

import pandas as pd
from prototype_engine import (
    validate_requests, simulate_queue, simulate_queue_with_reserve, detect_sla_state,
)

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, condition, detail=""):
    results.append((name, PASS if condition else FAIL, detail))


def base_row(**overrides):
    row = {
        "request_id": "REQX",
        "patient_id": "PT0001",
        "department": "General Surgery",
        "reason": "Pre-op transfer to OT",
        "timestamp_requested": "2026-08-24 10:00:00",
        "source_location": "Ward A1 (General Surgery)",
        "destination_location": "OT Complex - Theatre 1",
        "urgency": "Urgent",
        "requested_by": "Staff Nurse",
        "porter_id": "",
        "timestamp_assigned": "",
        "timestamp_arrived_source": "",
        "timestamp_handover_confirmed": "",
        "sla_minutes": 30,
        "status": "",
        "delay_reason": "",
    }
    row.update(overrides)
    return row


porters = pd.DataFrame([
    {"porter_id": "P01", "name": "Porter 1", "home_zone": 1,
     "shift_start_hour": 7, "shift_end_hour": 21},
    {"porter_id": "P02", "name": "Porter 2", "home_zone": 5,
     "shift_start_hour": 7, "shift_end_hour": 21},
])


# ---------------------------------------------------------------------------
# Edge case 1: Missing / blank source location on the call log
# ---------------------------------------------------------------------------
df1 = pd.DataFrame([base_row(source_location="")])
v1 = validate_requests(df1)
check(
    "EC1 - Missing source location does not crash and is flagged Low confidence",
    v1.loc[0, "data_confidence"] == "Low" and "source location missing" in v1.loc[0, "data_issues"],
    v1.loc[0, "data_issues"],
)

# ---------------------------------------------------------------------------
# Edge case 2: Free-text / typo'd location ("ward a1", "icu unit") must be
# auto-corrected but still visibly flagged, not silently trusted as exact
# ---------------------------------------------------------------------------
df2 = pd.DataFrame([base_row(source_location="ward a1", destination_location="icu unit")])
v2 = validate_requests(df2)
check(
    "EC2 - Free-text location is canonicalised correctly",
    v2.loc[0, "resolved_source"] == "Ward A1 (General Surgery)"
    and v2.loc[0, "resolved_destination"] == "ICU",
    f"resolved_source={v2.loc[0,'resolved_source']}, resolved_destination={v2.loc[0,'resolved_destination']}",
)
check(
    "EC2 - Auto-corrected location is still flagged (not treated as High confidence silently)",
    v2.loc[0, "data_confidence"] in ("Medium", "Low"),
    v2.loc[0, "data_issues"],
)

# ---------------------------------------------------------------------------
# Edge case 3: Missing urgency tag -- must default conservatively to
# 'Urgent' (never silently to 'Routine', which would hide a possible
# emergency) and must be surfaced for clinician review
# ---------------------------------------------------------------------------
df3 = pd.DataFrame([base_row(urgency="")])
v3 = validate_requests(df3)
check(
    "EC3 - Missing urgency defaults to 'Urgent' (safe default), not 'Routine'",
    v3.loc[0, "resolved_urgency"] == "Urgent",
    v3.loc[0, "resolved_urgency"],
)
check(
    "EC3 - Missing urgency is flagged for clinician review",
    "urgency not specified" in v3.loc[0, "data_issues"],
    v3.loc[0, "data_issues"],
)

# ---------------------------------------------------------------------------
# Edge case 4: Clock-skew / bad manual entry -- handover confirmed BEFORE
# arrival at source (a real error mode: staff back-filling timestamps from
# memory after the fact)
# ---------------------------------------------------------------------------
state = detect_sla_state(
    ts_requested=pd.Timestamp("2026-08-24 10:00:00"),
    ts_handover_confirmed=pd.Timestamp("2026-08-24 10:05:00"),
    ts_arrived_source=pd.Timestamp("2026-08-24 10:12:00"),   # arrived AFTER handover?! bad entry
    sla_minutes=30,
)
check(
    "EC4 - Handover-before-arrival timestamp is flagged Unknown, never a negative duration",
    state == "Unknown-BadTimestamps",
    state,
)

# ---------------------------------------------------------------------------
# Edge case 5: Simultaneous surge -- 5 Emergency requests fire in the same
# minute with only 2 porters available (capacity << demand). System must
# not crash, must not fabricate a porter, and must escalate every request
# it cannot safely serve rather than silently queuing them as if fine.
# ---------------------------------------------------------------------------
surge_rows = [
    base_row(request_id=f"SURGE{i}", urgency="Emergency",
             timestamp_requested="2026-08-24 09:00:00")
    for i in range(5)
]
df5 = pd.DataFrame(surge_rows)
sim5 = simulate_queue(df5, porters)
assigned = sim5["prototype_assigned_porter"].notna().sum()
escalated = sim5["prototype_escalated_for_review"].sum()
check(
    "EC5 - Surge of 5 emergencies vs 2 porters: engine completes without error",
    len(sim5) == 5,
    f"{len(sim5)} rows returned",
)
check(
    "EC5 - Requests beyond porter capacity are escalated for staff review, not silently queued as normal",
    escalated >= 3,
    f"assigned={assigned}, escalated={escalated}",
)

# ---------------------------------------------------------------------------
# Edge case 6 (bonus): Empty / all-null porter roster -- total infrastructure
# failure (e.g. porter roster system down). System must degrade to "escalate
# everything" rather than crash or hallucinate a porter.
# ---------------------------------------------------------------------------
empty_porters = pd.DataFrame(columns=["porter_id", "name", "home_zone",
                                       "shift_start_hour", "shift_end_hour"])
df6 = pd.DataFrame([base_row(request_id="NOPORTERS")])
sim6 = simulate_queue(df6, empty_porters)
check(
    "EC6 - Empty porter roster does not crash the engine",
    len(sim6) == 1,
    "engine returned a row",
)
check(
    "EC6 - Empty porter roster results in escalation, not a fabricated assignment",
    bool(sim6.loc[0, "prototype_escalated_for_review"]) and pd.isna(sim6.loc[0, "prototype_assigned_porter"]),
    f"assigned={sim6.loc[0,'prototype_assigned_porter']}, escalated={sim6.loc[0,'prototype_escalated_for_review']}",
)


# ---------------------------------------------------------------------------
# Edge case 7 (Review 2): reserved Emergency porter pool itself gets
# overwhelmed -- a burst of Emergency calls exceeds even the dedicated
# reserve. The engine must overflow into the general pool rather than
# queue an Emergency request behind an idle-but-"not allowed" porter.
# ---------------------------------------------------------------------------
reserve_surge_rows = [
    base_row(request_id=f"RSURGE{i}", urgency="Emergency",
             timestamp_requested="2026-08-24 09:00:00")
    for i in range(4)
]
df7 = pd.DataFrame(reserve_surge_rows)
sim7 = simulate_queue_with_reserve(df7, porters, reserved_porter_ids={"P01"})
check(
    "EC7 - Reserve-pool surge (4 Emergencies, 1 reserved porter): engine completes without error",
    len(sim7) == 4,
    f"{len(sim7)} rows returned",
)
check(
    "EC7 - Reserve-pool overflow uses the general pool rather than leaving requests unassigned",
    sim7["prototype_assigned_porter"].notna().all(),
    sim7[["request_id", "prototype_pool_used", "prototype_assigned_porter"]].to_dict("records"),
)

# ---------------------------------------------------------------------------
# Edge case 8 (Review 2): reserved porter ID doesn't actually exist in the
# roster (a config/typo error -- e.g. a porter ID retired or mistyped in
# the reservation list). Must degrade to "no reserve", not crash or
# silently drop every Emergency request.
# ---------------------------------------------------------------------------
df8 = pd.DataFrame([base_row(request_id="BADCONFIG", urgency="Emergency")])
sim8 = simulate_queue_with_reserve(df8, porters, reserved_porter_ids={"P99-DOES-NOT-EXIST"})
check(
    "EC8 - Non-existent reserved porter ID does not crash the engine",
    len(sim8) == 1,
    "engine returned a row",
)
check(
    "EC8 - Non-existent reserved porter ID falls back to the general pool instead of failing",
    pd.notna(sim8.loc[0, "prototype_assigned_porter"]),
    f"assigned={sim8.loc[0, 'prototype_assigned_porter']}",
)


def report():
    print(f"{'TEST':75s} {'RESULT':6s}  DETAIL")
    print("-" * 110)
    n_pass = 0
    for name, res, detail in results:
        print(f"{name:75s} {res:6s}  {detail}")
        if res == PASS:
            n_pass += 1
    print("-" * 110)
    print(f"{n_pass}/{len(results)} checks passed")


if __name__ == "__main__":
    report()
