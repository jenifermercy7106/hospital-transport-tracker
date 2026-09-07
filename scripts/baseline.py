"""
baseline.py
-----------
Simple baseline transport coordination method, representing the "next
simplest thing after phone calls" a hospital might try: a single shared
first-come-first-served (FIFO) list with no urgency weighting, no location
awareness, and no data-quality handling.

This mirrors how many hospitals informally operate today (a whiteboard or
spreadsheet where requests are handled in the order they were phoned in),
and is used as the comparison point for the prototype's measurable
improvement.

Rules:
- Requests are served strictly in the order timestamp_requested occurs.
- Any idle porter (by shift hours only — no zone/location matching) takes
  the next request in the queue.
- No SLA-aware prioritisation. No confidence flag. Missing fields simply
  pass through with no exception handling.
"""

import pandas as pd


def run_baseline(df: pd.DataFrame) -> pd.DataFrame:
    """
    Re-simulate handover time using FIFO-only logic to show what would have
    happened under naive queueing (used for the experiment comparison).
    We do not re-simulate physical travel; instead we measure how the FIFO
    *ordering* discipline alone affects Emergency-case waiting time, using
    the same underlying arrival stream as the prototype.
    """
    out = df.copy()
    out["timestamp_requested"] = pd.to_datetime(out["timestamp_requested"], errors="coerce")

    # Baseline has no urgency-aware sorting -> pure arrival order per day
    out = out.sort_values("timestamp_requested").reset_index(drop=True)

    # Baseline naive queue-wait model: every request waits behind every
    # earlier-arriving request that is still "in service" on the SAME porter
    # pool, regardless of urgency. We approximate with a single shared
    # capacity counter (this is intentionally cruder than the prototype).
    CAPACITY = 3  # baseline pretends there are always ~3 effective porters, no zone logic
    finish_times = [pd.Timestamp.min] * CAPACITY
    baseline_wait_minutes = []
    baseline_missed = []

    for _, row in out.iterrows():
        arrival = row["timestamp_requested"]
        if pd.isna(arrival):
            # baseline has no missing-data handling -> silently dropped (this IS the failure mode)
            baseline_wait_minutes.append(None)
            baseline_missed.append(True)
            continue

        # assign to whichever "slot" frees up earliest
        earliest_idx = min(range(CAPACITY), key=lambda i: finish_times[i])
        start = max(arrival, finish_times[earliest_idx])
        wait = (start - arrival).total_seconds() / 60.0

        # baseline uses a flat average service time (no urgency/location adjustment)
        service_time = 18.0
        finish_times[earliest_idx] = start + pd.Timedelta(minutes=service_time)

        baseline_wait_minutes.append(wait)

        # baseline "missed" definition: no re-check, no escalation -> anything
        # that waits past its own SLA is simply late with no alert
        sla = row["sla_minutes"] if not pd.isna(row["sla_minutes"]) else 30
        baseline_missed.append(wait + service_time > sla)

    out["baseline_wait_minutes"] = baseline_wait_minutes
    out["baseline_missed_or_late"] = baseline_missed
    return out


if __name__ == "__main__":
    df = pd.read_csv("data/transport_requests.csv")
    result = run_baseline(df)
    result.to_csv("outputs/baseline_result.csv", index=False)
    print(result[["urgency", "baseline_wait_minutes", "baseline_missed_or_late"]].groupby(
        "urgency", dropna=False).agg(
        avg_wait=("baseline_wait_minutes", "mean"),
        pct_missed_or_late=("baseline_missed_or_late", "mean")
    ))
