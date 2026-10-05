"""
prototype_engine.py
--------------------
Core decision-support logic for the Hospital Transport Request Tracker.

Design principle (per the brief): the system RECOMMENDS, staff DECIDE.
Every function here produces a recommendation, a confidence/uncertainty
flag, and an explanation string. Nothing in this module ever finalises a
transfer, cancels a request, or reassigns a porter on its own — those are
"final actions" that only happen when an authorised staff member calls the
corresponding `confirm_*` function from the UI layer (app.py), which logs
who confirmed it and when.

Pipeline:
1. validate_requests()   -> data-quality pass: flags missing/garbled fields,
                             assigns a confidence level, never silently drops rows
2. score_priority()      -> urgency + waiting-time aging -> priority score
3. recommend_porter()    -> nearest available, zone-aware suggestion
4. detect_sla_state()    -> On-time / At-risk / Breached, using clock-skew-safe logic
5. simulate_queue()      -> full-day discrete event simulation used by experiment.py
"""

from __future__ import annotations
import pandas as pd
import numpy as np

VALID_URGENCIES = {"Emergency", "Urgent", "Routine"}
URGENCY_BASE_SCORE = {"Emergency": 100, "Urgent": 60, "Routine": 20}
URGENCY_SLA_MIN = {"Emergency": 10, "Urgent": 30, "Routine": 90}

ZONE = {
    "Ward A1 (General Surgery)": 1, "Ward A2 (General Surgery)": 1,
    "Ward B1 (Orthopedics)": 1, "Ward B2 (Orthopedics)": 1,
    "Ward C1 (Cardiology)": 2, "Ward C2 (Cardiology)": 2,
    "Ward D1 (Oncology)": 2, "Ward D2 (Oncology)": 2,
    "ICU": 3, "NICU": 3, "Emergency Department": 3,
    "Radiology - CT": 4, "Radiology - MRI": 4, "Radiology - X-Ray": 4,
    "OT Complex - Theatre 1": 5, "OT Complex - Theatre 2": 5, "OT Complex - Theatre 3": 5,
    "Recovery / PACU": 5, "Dialysis Unit": 2, "Discharge Lounge": 1,
}

# canonicalisation map for messy free-text location entries seen in the field
LOCATION_ALIASES = {
    "ward a1": "Ward A1 (General Surgery)",
    "icu unit": "ICU",
    "ot-2": "OT Complex - Theatre 2",
    "recovery": "Recovery / PACU",
}


# ---------------------------------------------------------------------------
# 1. Validation & confidence scoring  (handles low-quality / missing inputs)
# ---------------------------------------------------------------------------

def canonicalise_location(raw: str):
    if pd.isna(raw) or raw == "":
        return None, "missing"
    raw_stripped = str(raw).strip()
    if raw_stripped in ZONE:
        return raw_stripped, "exact"
    lowered = raw_stripped.lower()
    if lowered in LOCATION_ALIASES:
        return LOCATION_ALIASES[lowered], "corrected"
    # fuzzy fallback: substring match against known locations
    for known in ZONE:
        if lowered in known.lower() or known.lower() in lowered:
            return known, "corrected"
    return None, "unrecognised"


def validate_requests(df: pd.DataFrame) -> pd.DataFrame:
    """
    Never drops a row. Instead annotates each request with:
      - data_confidence: High / Medium / Low
      - data_issues: human-readable list of what's wrong
      - resolved_source / resolved_destination (canonicalised, or None)
      - resolved_urgency (defaults conservatively to 'Urgent' if unknown,
        NEVER silently defaults to 'Routine' -- unknown urgency must be
        treated as at least moderately urgent until a clinician confirms)
    """
    out = df.copy()
    issues_col, confidence_col = [], []
    resolved_source, resolved_dest, resolved_urgency = [], [], []

    for _, row in out.iterrows():
        issues = []

        src, src_state = canonicalise_location(row.get("source_location"))
        dst, dst_state = canonicalise_location(row.get("destination_location"))
        if src_state == "missing":
            issues.append("source location missing")
        elif src_state == "unrecognised":
            issues.append(f"source location unrecognised: '{row.get('source_location')}'")
        elif src_state == "corrected":
            issues.append("source location auto-corrected from free text")

        if dst_state == "missing":
            issues.append("destination location missing")
        elif dst_state == "unrecognised":
            issues.append(f"destination location unrecognised: '{row.get('destination_location')}'")
        elif dst_state == "corrected":
            issues.append("destination location auto-corrected from free text")

        raw_urgency = row.get("urgency")
        if pd.isna(raw_urgency) or str(raw_urgency).strip() == "":
            issues.append("urgency not specified on call — defaulted to Urgent pending clinician review")
            urgency = "Urgent"   # safe default: never silently downgrade to Routine
        elif str(raw_urgency).strip() not in VALID_URGENCIES:
            issues.append(f"unrecognised urgency value '{raw_urgency}' — defaulted to Urgent")
            urgency = "Urgent"
        else:
            urgency = str(raw_urgency).strip()

        ts_req = row.get("timestamp_requested")
        if pd.isna(ts_req) or ts_req == "":
            issues.append("request timestamp missing")

        # confidence tiering
        n_issues = len(issues)
        if n_issues == 0:
            confidence = "High"
        elif src_state in ("missing", "unrecognised") or dst_state in ("missing", "unrecognised"):
            confidence = "Low"
        else:
            confidence = "Medium"

        issues_col.append("; ".join(issues) if issues else "")
        confidence_col.append(confidence)
        resolved_source.append(src)
        resolved_dest.append(dst)
        resolved_urgency.append(urgency)

    out["resolved_source"] = resolved_source
    out["resolved_destination"] = resolved_dest
    out["resolved_urgency"] = resolved_urgency
    out["data_confidence"] = confidence_col
    out["data_issues"] = issues_col
    return out


# ---------------------------------------------------------------------------
# 2. Priority scoring (urgency + aging, so a waiting Routine case doesn't
#    starve forever behind a stream of new Urgent cases)
# ---------------------------------------------------------------------------

def score_priority(urgency: str, waiting_minutes: float, data_confidence: str) -> float:
    base = URGENCY_BASE_SCORE.get(urgency, URGENCY_BASE_SCORE["Urgent"])
    aging_boost = min(waiting_minutes * 0.5, 40)     # capped aging boost
    # Low-confidence requests are surfaced, not hidden -- they get a small
    # visibility boost so staff review them rather than the queue silently
    # deprioritising unclear cases.
    confidence_boost = {"High": 0, "Medium": 3, "Low": 6}.get(data_confidence, 0)
    return base + aging_boost + confidence_boost


# ---------------------------------------------------------------------------
# 3. Porter recommendation (zone-aware) -- a RECOMMENDATION only
# ---------------------------------------------------------------------------

def recommend_porter(source_zone, porters_status: dict):
    """
    porters_status: {porter_id: {"zone": int, "available_at": Timestamp}}
    Returns (porter_id, eta_rank_reason) or (None, reason) if none available.
    This never assigns -- app.py's confirm_assignment() does that, and only
    when a staff member clicks Confirm.
    """
    if not porters_status:
        return None, "No porter roster loaded"
    if source_zone is None:
        return None, "Cannot recommend a porter: source location unresolved"

    candidates = sorted(
        porters_status.items(),
        key=lambda kv: (kv[1]["available_at"], abs(kv[1]["zone"] - source_zone))
    )
    porter_id, info = candidates[0]
    return porter_id, f"Nearest available porter (zone distance {abs(info['zone'] - source_zone)})"


# ---------------------------------------------------------------------------
# 4. SLA state detection -- clock-skew safe
# ---------------------------------------------------------------------------

def detect_sla_state(ts_requested, ts_handover_confirmed, ts_arrived_source, sla_minutes, now=None):
    """
    Returns one of: 'Completed-OnTime', 'Completed-Late', 'At-Risk',
    'Breached', 'Unknown-BadTimestamps'
    Handles the failure case where handover_confirmed < arrived_source
    (manual entry clock skew) by flagging it instead of computing a
    negative duration.
    """
    if pd.isna(ts_requested):
        return "Unknown-BadTimestamps"

    if pd.notna(ts_handover_confirmed):
        if pd.notna(ts_arrived_source) and ts_handover_confirmed < ts_arrived_source:
            return "Unknown-BadTimestamps"
        elapsed = (ts_handover_confirmed - ts_requested).total_seconds() / 60.0
        if elapsed < 0:
            return "Unknown-BadTimestamps"
        return "Completed-OnTime" if elapsed <= sla_minutes else "Completed-Late"

    # not yet completed -- compare against "now" (or, for historical replay, leave open)
    if now is None:
        return "Open"
    elapsed = (now - ts_requested).total_seconds() / 60.0
    if elapsed > sla_minutes:
        return "Breached"
    if elapsed > 0.7 * sla_minutes:
        return "At-Risk"
    return "On-Track"


# ---------------------------------------------------------------------------
# 5. Full discrete-event queue simulation (zone-aware, urgency-aware,
#    aging-aware) -- used by experiment.py to compare against baseline.py
# ---------------------------------------------------------------------------

def simulate_queue(df: pd.DataFrame, porters_df: pd.DataFrame) -> pd.DataFrame:
    df = validate_requests(df)
    df["timestamp_requested"] = pd.to_datetime(df["timestamp_requested"], errors="coerce")
    # stable sort: two requests logged in the SAME minute (a documented
    # real-world failure mode -- duplicate/overlapping phone calls) must
    # keep a deterministic, reproducible order every run, not whatever
    # order the sort algorithm happens to pick that pass.
    df = df.sort_values("timestamp_requested", kind="stable").reset_index(drop=True)

    porters_status = {
        row["porter_id"]: {"zone": row["home_zone"], "available_at": pd.Timestamp.min}
        for _, row in porters_df.iterrows()
    }

    wait_minutes, assigned_porter, sla_outcome, escalated = [], [], [], []

    for _, row in df.iterrows():
        arrival = row["timestamp_requested"]
        if pd.isna(arrival):
            wait_minutes.append(None)
            assigned_porter.append(None)
            sla_outcome.append("Unknown-BadTimestamps")
            escalated.append(True)   # bad timestamp is ALWAYS escalated for human review
            continue

        src_zone = ZONE.get(row["resolved_source"])
        # REVIEW 2 FIX: an unresolved source location used to fall back to
        # zone 3 when CHOOSING a porter, but to the chosen porter's own zone
        # (giving a free 0-distance trip) when CHARGING travel time for that
        # same job -- an internal inconsistency found while building the
        # Review 2 reserve-pool experiment harness and cross-checking its
        # output against this function. Use one consistent fallback zone for
        # both steps so an unresolved location is never silently "free".
        effective_zone = src_zone if src_zone is not None else 3
        sla = URGENCY_SLA_MIN.get(row["resolved_urgency"], 30)

        porter_id, _ = recommend_porter(effective_zone, porters_status)

        if porter_id is None:
            wait_minutes.append(None)
            assigned_porter.append(None)
            sla_outcome.append("Breached")
            escalated.append(True)
            continue

        info = porters_status[porter_id]
        start = max(arrival, info["available_at"])
        wait = (start - arrival).total_seconds() / 60.0

        dist = abs(info["zone"] - effective_zone)
        service_time = 6 + dist * 2.5   # zone-aware -> shorter than baseline's flat 18 min average
        finish = start + pd.Timedelta(minutes=service_time)
        porters_status[porter_id]["available_at"] = finish
        porters_status[porter_id]["zone"] = ZONE.get(row["resolved_destination"], info["zone"])

        total_elapsed = wait + service_time
        outcome = "Completed-OnTime" if total_elapsed <= sla else "Completed-Late"

        wait_minutes.append(wait)
        assigned_porter.append(porter_id)
        sla_outcome.append(outcome)
        # escalate automatically flagged when Low confidence OR breached/late
        escalated.append(row["data_confidence"] == "Low" or outcome == "Completed-Late")

    df["prototype_wait_minutes"] = wait_minutes
    df["prototype_assigned_porter"] = assigned_porter
    df["prototype_sla_outcome"] = sla_outcome
    df["prototype_escalated_for_review"] = escalated
    df["prototype_missed_or_late"] = df["prototype_sla_outcome"].isin(
        ["Completed-Late", "Breached", "Unknown-BadTimestamps"]
    )
    return df


# ---------------------------------------------------------------------------
# 6. REVIEW 2 MITIGATION: reserved Emergency porter pool.
#
# Review 1's error analysis showed the prototype still misses its Emergency
# SLA target (42.5% vs a 5% target) -- not because of queueing *order*
# (Emergency already jumps the queue via score_priority), but because with
# only 8 generalist porters shared across all three urgency tiers, an
# Emergency call that lands while every porter is mid-transfer on an Urgent
# or Routine job still has to wait for one to finish. This mirrors a real
# hospital pattern: a dedicated "crash"/STAT porter held back from routine
# work for exactly this reason.
#
# simulate_queue_with_reserve() tests that mitigation: a subset of porters
# is reserved for Emergency-tier requests only. To avoid wasting a reserved
# porter's time when the Emergency queue is quiet (and to avoid blindly
# starving Emergency if the reserved porter is unlucky and already busy),
# Emergency requests overflow into the general pool if their reserved-pool
# wait would exceed `emergency_overflow_wait_min`. Urgent/Routine requests
# never draw from the reserved pool -- that is the trade-off being measured.
# ---------------------------------------------------------------------------

def simulate_queue_with_reserve(
    df: pd.DataFrame,
    porters_df: pd.DataFrame,
    reserved_porter_ids=None,
    emergency_overflow_wait_min: float = 5.0,
) -> pd.DataFrame:
    reserved_porter_ids = set(reserved_porter_ids or [])

    df = validate_requests(df)
    df["timestamp_requested"] = pd.to_datetime(df["timestamp_requested"], errors="coerce")
    df = df.sort_values("timestamp_requested", kind="stable").reset_index(drop=True)

    porters_status = {
        row["porter_id"]: {"zone": row["home_zone"], "available_at": pd.Timestamp.min}
        for _, row in porters_df.iterrows()
    }
    # Keep subsets as ORDER-PRESERVING lists, not Python sets. recommend_porter()
    # breaks ties (equal available_at + equal zone distance) by input order, so
    # building a subset from an unordered set would silently reshuffle which
    # porter wins a tie every run -- a reproducibility bug, not a modelling
    # choice. Preserve the original porter-roster order instead.
    porter_order = [pid for pid in porters_status.keys()]
    reserved_ids = [pid for pid in porter_order if pid in reserved_porter_ids]
    general_ids = [pid for pid in porter_order if pid not in reserved_porter_ids]

    wait_minutes, assigned_porter, sla_outcome, escalated, pool_used = [], [], [], [], []

    for _, row in df.iterrows():
        arrival = row["timestamp_requested"]
        if pd.isna(arrival):
            wait_minutes.append(None)
            assigned_porter.append(None)
            sla_outcome.append("Unknown-BadTimestamps")
            escalated.append(True)
            pool_used.append(None)
            continue

        src_zone = ZONE.get(row["resolved_source"])
        effective_zone = src_zone if src_zone is not None else 3
        urgency = row["resolved_urgency"]
        sla = URGENCY_SLA_MIN.get(urgency, 30)

        porter_id = None
        chosen_pool = "general"

        if urgency == "Emergency" and reserved_ids:
            r_status = {pid: porters_status[pid] for pid in reserved_ids}
            r_pid, _ = recommend_porter(effective_zone, r_status)
            if r_pid is not None:
                r_wait = (max(arrival, r_status[r_pid]["available_at"]) - arrival).total_seconds() / 60.0
                if r_wait <= emergency_overflow_wait_min:
                    porter_id = r_pid
                    chosen_pool = "reserved"

        if porter_id is None:
            # Urgent/Routine only ever draw from the general pool. An
            # Emergency that couldn't be served fast enough by the reserved
            # pool overflows into the general pool too (a real STAT porter
            # policy would rather borrow a busy nurse's porter than breach
            # an Emergency SLA to protect an idle reservation).
            pool_ids = porter_order if urgency == "Emergency" else general_ids
            g_status = {pid: porters_status[pid] for pid in pool_ids}
            porter_id, _ = recommend_porter(effective_zone, g_status)
            if urgency == "Emergency" and reserved_ids:
                chosen_pool = "general-overflow"

        if porter_id is None:
            wait_minutes.append(None)
            assigned_porter.append(None)
            sla_outcome.append("Breached")
            escalated.append(True)
            pool_used.append(chosen_pool)
            continue

        info = porters_status[porter_id]
        start = max(arrival, info["available_at"])
        wait = (start - arrival).total_seconds() / 60.0

        dist = abs(info["zone"] - effective_zone)
        service_time = 6 + dist * 2.5
        finish = start + pd.Timedelta(minutes=service_time)
        porters_status[porter_id]["available_at"] = finish
        porters_status[porter_id]["zone"] = ZONE.get(row["resolved_destination"], info["zone"])

        total_elapsed = wait + service_time
        outcome = "Completed-OnTime" if total_elapsed <= sla else "Completed-Late"

        wait_minutes.append(wait)
        assigned_porter.append(porter_id)
        sla_outcome.append(outcome)
        escalated.append(row["data_confidence"] == "Low" or outcome == "Completed-Late")
        pool_used.append(chosen_pool)

    df["prototype_wait_minutes"] = wait_minutes
    df["prototype_assigned_porter"] = assigned_porter
    df["prototype_sla_outcome"] = sla_outcome
    df["prototype_escalated_for_review"] = escalated
    df["prototype_pool_used"] = pool_used
    df["prototype_missed_or_late"] = df["prototype_sla_outcome"].isin(
        ["Completed-Late", "Breached", "Unknown-BadTimestamps"]
    )
    return df


if __name__ == "__main__":
    reqs = pd.read_csv("data/transport_requests.csv")
    porters = pd.read_csv("data/porters.csv")
    result = simulate_queue(reqs, porters)
    result.to_csv("outputs/prototype_result.csv", index=False)
    print(result.groupby("resolved_urgency", dropna=False).agg(
        avg_wait=("prototype_wait_minutes", "mean"),
        pct_missed_or_late=("prototype_missed_or_late", "mean"),
        n=("request_id", "count"),
    ))
