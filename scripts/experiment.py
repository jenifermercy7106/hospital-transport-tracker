"""
experiment.py
-------------
Measurable experiment comparing the FIFO baseline against the urgency +
location aware prototype, replaying the SAME historical request-arrival
stream through both policies. Produces:
  - outputs/experiment_summary.csv   (baseline vs prototype vs target)
  - outputs/chart_missed_by_urgency.png
  - outputs/chart_wait_time.png
  - outputs/error_analysis.csv
"""

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from baseline import run_baseline
from prototype_engine import validate_requests, simulate_queue

TARGET_MISSED_OR_LATE = {"Emergency": 0.05, "Urgent": 0.10, "Routine": 0.15}


def main():
    df = pd.read_csv("data/transport_requests.csv")

    baseline_result = run_baseline(df)
    prototype_result = simulate_queue(df, pd.read_csv("data/porters.csv"))

    # --- historical ground truth (today's phone-based system) ---
    hist = df.copy()
    hist_missed_rate = (hist["status"].isin(["Missed", "Delayed"])).mean()

    # --- summarise by urgency ---
    b = baseline_result.groupby("urgency", dropna=False).agg(
        baseline_avg_wait_min=("baseline_wait_minutes", "mean"),
        baseline_pct_missed_or_late=("baseline_missed_or_late", "mean"),
        n=("request_id", "count"),
    ).reset_index()

    p = prototype_result.groupby("resolved_urgency", dropna=False).agg(
        prototype_avg_wait_min=("prototype_wait_minutes", "mean"),
        prototype_pct_missed_or_late=("prototype_missed_or_late", "mean"),
        prototype_pct_escalated=("prototype_escalated_for_review", "mean"),
    ).reset_index().rename(columns={"resolved_urgency": "urgency"})

    summary = b.merge(p, on="urgency", how="outer")
    summary["target_pct_missed_or_late"] = summary["urgency"].map(TARGET_MISSED_OR_LATE)
    summary["improvement_pct_points"] = (
        (summary["baseline_pct_missed_or_late"] - summary["prototype_pct_missed_or_late"]) * 100
    )
    summary["meets_target"] = summary["prototype_pct_missed_or_late"] <= summary["target_pct_missed_or_late"]

    summary.to_csv("outputs/experiment_summary.csv", index=False)
    print("=== Historical (phone-based) system ===")
    print(f"Missed or Delayed rate: {hist_missed_rate*100:.1f}%\n")
    print("=== Baseline vs Prototype vs Target (by urgency) ===")
    print(summary.to_string(index=False))

    # --- error analysis: where does the prototype still fail? ---
    proto = prototype_result.copy()
    errors = proto[proto["prototype_missed_or_late"]].copy()
    error_breakdown = errors.groupby(
        ["resolved_urgency", "prototype_sla_outcome"], dropna=False
    ).size().reset_index(name="count").sort_values("count", ascending=False)
    error_breakdown.to_csv("outputs/error_analysis.csv", index=False)
    print("\n=== Error analysis: remaining prototype failures ===")
    print(error_breakdown.to_string(index=False))

    # low-confidence rows and their outcome, to show the uncertainty-handling story
    low_conf = proto[proto["data_confidence"] == "Low"]
    print(f"\nLow-confidence (messy input) requests: {len(low_conf)} "
          f"({len(low_conf)/len(proto)*100:.1f}% of all requests)")
    print(f"  -> of these, {low_conf['prototype_escalated_for_review'].mean()*100:.0f}% "
          f"were escalated to staff instead of auto-processed")

    # --- charts ---
    fig, ax = plt.subplots(figsize=(7, 4.5))
    urgencies = ["Emergency", "Urgent", "Routine"]
    x = range(len(urgencies))
    bw = 0.35
    b_vals = [summary.loc[summary.urgency == u, "baseline_pct_missed_or_late"].values[0] * 100
              if u in summary.urgency.values else 0 for u in urgencies]
    p_vals = [summary.loc[summary.urgency == u, "prototype_pct_missed_or_late"].values[0] * 100
              if u in summary.urgency.values else 0 for u in urgencies]
    ax.bar([i - bw/2 for i in x], b_vals, width=bw, label="Baseline (FIFO)", color="#c0524a")
    ax.bar([i + bw/2 for i in x], p_vals, width=bw, label="Prototype", color="#3a7d5c")
    ax.set_xticks(list(x))
    ax.set_xticklabels(urgencies)
    ax.set_ylabel("% Missed or Late")
    ax.set_title("Missed/Late Transfers by Urgency: Baseline vs Prototype")
    ax.legend()
    fig.tight_layout()
    fig.savefig("outputs/chart_missed_by_urgency.png", dpi=150)

    fig2, ax2 = plt.subplots(figsize=(7, 4.5))
    b_wait = [summary.loc[summary.urgency == u, "baseline_avg_wait_min"].values[0]
              if u in summary.urgency.values else 0 for u in urgencies]
    p_wait = [summary.loc[summary.urgency == u, "prototype_avg_wait_min"].values[0]
              if u in summary.urgency.values else 0 for u in urgencies]
    ax2.bar([i - bw/2 for i in x], b_wait, width=bw, label="Baseline (FIFO)", color="#c0524a")
    ax2.bar([i + bw/2 for i in x], p_wait, width=bw, label="Prototype", color="#3a7d5c")
    ax2.set_xticks(list(x))
    ax2.set_xticklabels(urgencies)
    ax2.set_ylabel("Average Porter Wait (minutes)")
    ax2.set_title("Average Wait for Porter Assignment: Baseline vs Prototype")
    ax2.legend()
    fig2.tight_layout()
    fig2.savefig("outputs/chart_wait_time.png", dpi=150)

    print("\nCharts saved to outputs/chart_missed_by_urgency.png and outputs/chart_wait_time.png")


if __name__ == "__main__":
    main()
