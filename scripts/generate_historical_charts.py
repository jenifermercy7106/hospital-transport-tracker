"""
generate_historical_charts.py  (Review 2)
-------------------------------------------
Review 1 shipped outputs/chart_historical_problem.png and
outputs/chart_data_confidence.png (used in the report, Figures 1 and 3),
but no script to reproduce them -- a reproducibility gap found while
rebuilding the full pipeline for Review 2. Both charts are derived purely
from the raw historical dataset (not from the prototype/baseline engines),
so they were unaffected by the Section 6.1 engine bugfix, but they should
still be regenerable like everything else.

Outputs:
  outputs/chart_historical_problem.png  -- outcomes by urgency, phone-based system
  outputs/chart_data_confidence.png     -- data-confidence distribution
"""

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import sys
sys.path.insert(0, ".")
from prototype_engine import validate_requests

STATUS_COLORS = {"Completed": "#3a7d5c", "Delayed": "#d9a441", "Missed": "#c0524a", "Cancelled": "#9e9e9e"}
CONF_COLORS = {"High": "#3a7d5c", "Medium": "#d9a441", "Low": "#c0524a"}


def main():
    df = pd.read_csv("data/transport_requests.csv")

    # --- Figure 1: historical outcomes by urgency ---
    urgencies = ["Emergency", "Urgent", "Routine"]
    statuses = ["Completed", "Delayed", "Missed", "Cancelled"]
    counts = {s: [] for s in statuses}
    for u in urgencies:
        sub = df[df["urgency"] == u]
        for s in statuses:
            counts[s].append((sub["status"] == s).sum())

    fig, ax = plt.subplots(figsize=(7, 4.5))
    bottom = [0] * len(urgencies)
    for s in statuses:
        ax.bar(urgencies, counts[s], bottom=bottom, label=s, color=STATUS_COLORS[s])
        bottom = [b + c for b, c in zip(bottom, counts[s])]
    ax.set_ylabel("Number of requests")
    ax.set_title("Current Phone-Based System: Outcomes by Urgency (1 week)")
    ax.legend(title="status")
    fig.tight_layout()
    fig.savefig("outputs/chart_historical_problem.png", dpi=150)
    print("Saved outputs/chart_historical_problem.png")
    for u in urgencies:
        sub = df[df["urgency"] == u]
        n = len(sub)
        completed = (sub["status"] == "Completed").sum()
        print(f"  {u}: {completed}/{n} Completed on time "
              f"({completed/n*100:.1f}%)" if n else f"  {u}: n=0")

    # --- Figure 3: data-confidence distribution ---
    v = validate_requests(df)
    conf_counts = v["data_confidence"].value_counts().reindex(["High", "Medium", "Low"]).fillna(0)

    fig2, ax2 = plt.subplots(figsize=(5.5, 4.5))
    ax2.bar(conf_counts.index, conf_counts.values,
            color=[CONF_COLORS[c] for c in conf_counts.index])
    ax2.set_ylabel("Number of requests")
    ax2.set_title("Input Data Confidence (1-week dataset)")
    for i, v_ in enumerate(conf_counts.values):
        ax2.text(i, v_ + 5, str(int(v_)), ha="center")
    fig2.tight_layout()
    fig2.savefig("outputs/chart_data_confidence.png", dpi=150)
    print("Saved outputs/chart_data_confidence.png")
    total = len(v)
    low = conf_counts.get("Low", 0)
    print(f"  Low-confidence: {int(low)}/{total} ({low/total*100:.1f}%)")


if __name__ == "__main__":
    main()
