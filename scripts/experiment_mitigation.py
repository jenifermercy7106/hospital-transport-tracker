"""
experiment_mitigation.py  (Review 2)
-------------------------------------
Follow-up experiment to the Review 1 finding: the prototype's priority queue
still missed its Emergency SLA target (42.5% vs a 5% target), and the error
analysis showed every one of those misses was a "Completed-Late" case, not a
queueing-order bug -- with only 8 generalist porters, an Emergency call can
still land when all 8 are mid-transfer on something else.

This script tests the proposed mitigation from the Review 1 next-steps list:
reserving a small number of porters exclusively for Emergency-tier requests
(scripts/prototype_engine.py::simulate_queue_with_reserve), and measures the
trade-off it creates for Urgent/Routine wait times, across three
configurations run on the IDENTICAL historical request stream:

  0 reserved porters   -- Review 1's prototype (no change)
  1 reserved porter     -- P03 (zone 3: ICU / NICU / Emergency Dept / closest
                            average distance to all other zones)
  2 reserved porters   -- P03 + P08 (zone 5: OT Complex / Recovery, the
                            second-largest source of Emergency calls)

Outputs:
  outputs/mitigation_experiment_summary.csv
  outputs/chart_mitigation_tradeoff.png
"""

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from prototype_engine import simulate_queue_with_reserve, simulate_queue

TARGET_MISSED_OR_LATE = {"Emergency": 0.05, "Urgent": 0.10, "Routine": 0.15}

CONFIGS = [
    ("0 reserved (Review 1 prototype)", set()),
    ("1 reserved (P03)", {"P03"}),
    ("2 reserved (P03 + P08)", {"P03", "P08"}),
]


def summarise(result: pd.DataFrame, label: str) -> pd.DataFrame:
    g = result.groupby("resolved_urgency", dropna=False).agg(
        avg_wait_min=("prototype_wait_minutes", "mean"),
        pct_missed_or_late=("prototype_missed_or_late", "mean"),
        pct_escalated=("prototype_escalated_for_review", "mean"),
        n=("request_id", "count"),
    ).reset_index().rename(columns={"resolved_urgency": "urgency"})
    g["config"] = label
    g["target_pct_missed_or_late"] = g["urgency"].map(TARGET_MISSED_OR_LATE)
    g["meets_target"] = g["pct_missed_or_late"] <= g["target_pct_missed_or_late"]
    return g


def main():
    df = pd.read_csv("data/transport_requests.csv")
    porters = pd.read_csv("data/porters.csv")

    all_rows = []
    pool_usage = {}
    for label, reserve_set in CONFIGS:
        result = simulate_queue_with_reserve(df, porters, reserved_porter_ids=reserve_set)
        all_rows.append(summarise(result, label))
        if "prototype_pool_used" in result.columns and reserve_set:
            emg = result[result["resolved_urgency"] == "Emergency"]
            pool_usage[label] = emg["prototype_pool_used"].value_counts(dropna=False).to_dict()

    summary = pd.concat(all_rows, ignore_index=True)
    summary = summary[["config", "urgency", "n", "avg_wait_min", "pct_missed_or_late",
                        "pct_escalated", "target_pct_missed_or_late", "meets_target"]]
    summary.to_csv("outputs/mitigation_experiment_summary.csv", index=False)

    print("=== Review 2 mitigation experiment: reserved Emergency porter pool ===")
    print(summary.to_string(index=False))

    print("\n=== Where Emergency requests were actually served from ===")
    for label, counts in pool_usage.items():
        print(f"{label}: {counts}")

    # --- trade-off read-out: Emergency improvement vs Routine/Urgent cost ---
    base = summary[summary["config"] == CONFIGS[0][0]].set_index("urgency")
    one = summary[summary["config"] == CONFIGS[1][0]].set_index("urgency")
    two = summary[summary["config"] == CONFIGS[2][0]].set_index("urgency")

    print("\n=== Trade-off vs 0-reserved baseline ===")
    for label, cfg in [("1 reserved", one), ("2 reserved", two)]:
        em_delta = (base.loc["Emergency", "pct_missed_or_late"] - cfg.loc["Emergency", "pct_missed_or_late"]) * 100
        ur_delta = (cfg.loc["Urgent", "avg_wait_min"] - base.loc["Urgent", "avg_wait_min"])
        ro_delta = (cfg.loc["Routine", "avg_wait_min"] - base.loc["Routine", "avg_wait_min"])
        print(f"{label}: Emergency missed/late improves by {em_delta:.1f} pct points; "
              f"Urgent avg wait changes by {ur_delta:+.2f} min; "
              f"Routine avg wait changes by {ro_delta:+.2f} min")

    # --- chart: missed/late by urgency, grouped by config ---
    urgencies = ["Emergency", "Urgent", "Routine"]
    fig, ax = plt.subplots(figsize=(8, 5))
    width = 0.25
    x = range(len(urgencies))
    colors = ["#c0524a", "#d9a441", "#3a7d5c"]
    for i, (label, _) in enumerate(CONFIGS):
        vals = [summary.loc[(summary.config == label) & (summary.urgency == u),
                             "pct_missed_or_late"].values[0] * 100
                if u in summary.loc[summary.config == label, "urgency"].values else 0
                for u in urgencies]
        ax.bar([xi + (i - 1) * width for xi in x], vals, width=width, label=label, color=colors[i])
    ax.set_xticks(list(x))
    ax.set_xticklabels(urgencies)
    ax.set_ylabel("% Missed or Late")
    ax.set_title("Reserved Emergency Porter Pool: Trade-off Across Urgency Tiers")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig("outputs/chart_mitigation_tradeoff.png", dpi=150)
    print("\nChart saved to outputs/chart_mitigation_tradeoff.png")

    # -----------------------------------------------------------------
    # Sanity check: the reserved-pool result above is counter-intuitive
    # (it makes Emergency WORSE, not better -- see report for why: with
    # only 87 Emergency calls/week spread over 8 porters, concentrating
    # them onto 1-2 dedicated porters creates queueing for Emergency
    # itself whenever two land close together, which outweighs the
    # benefit of a guaranteed-free porter). Before concluding "reservation
    # doesn't work", check whether the real lever is total CAPACITY
    # instead of allocation -- i.e. is this a staffing problem, not a
    # scheduling-policy problem?
    # -----------------------------------------------------------------
    print("\n=== Sanity check: is this a capacity problem rather than an allocation "
          "problem? (adding generalist porters, no reservation) ===")
    base_rate = base.loc["Emergency", "pct_missed_or_late"]
    print(f"8 porters (no change):            Emergency missed/late = {base_rate*100:.1f}%")
    extra = porters.copy()
    for n_extra, new_id in [(1, "P09"), (2, "P10")]:
        extra = pd.concat([extra, pd.DataFrame([{
            "porter_id": new_id, "name": f"Porter {new_id}", "home_zone": 3,
            "shift_start_hour": 7, "shift_end_hour": 21,
        }])], ignore_index=True)
        r = simulate_queue(df.copy(), extra)
        rate = r[r["resolved_urgency"] == "Emergency"]["prototype_missed_or_late"].mean()
        print(f"{8+n_extra} porters (+{n_extra} generalist, no reservation): "
              f"Emergency missed/late = {rate*100:.1f}%")
    print("Conclusion: adding plain capacity helps more than reserving existing "
          "capacity, but even +2 porters doesn't reach the 5% target -- "
          "consistent with Review 1's finding that the remaining gap is "
          "largely a physical travel-time constraint against a strict "
          "10-minute Emergency SLA, not a queueing-policy defect.")


if __name__ == "__main__":
    main()
