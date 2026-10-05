# Hospital Transport Request Tracker

Urgency-, location- and handover-aware transport coordination prototype for a
multi-specialty hospital sharing operating theatres across departments.
Built to replace an unreliable phone-call coordination process while keeping
**every final action under authorised staff control**.

See `outputs/Hospital_Transport_Tracker_Report.docx` for the full write-up
(scenario, baseline, solution design, usability walkthrough, edge-case
tests, performance results with error analysis, a Review 2 mitigation
experiment, ethics note, and a deployment checklist). Section 0 of the
report is a short changelog of everything added since Review 1.

## What's new in Review 2

- **Bugfix**: `simulate_queue()` had an inconsistent zone fallback for
  unresolved source locations (picked a porter for zone 3, charged travel
  time for zone 0). Fixed in `prototype_engine.py`; Emergency miss rate
  shifts slightly from 42.5% to 43.7% as a result — reported transparently
  in the report rather than quietly, see Section 0 and 6.1.
- **Determinism fix**: queue simulation now uses a stable sort so
  same-minute duplicate calls produce reproducible results run to run.
- **`scripts/experiment_mitigation.py`** (new): tests Review 1's proposed
  "reserve a porter for Emergency-only" mitigation. Result: it makes
  Emergency performance *worse*, not better — a genuinely useful,
  counter-intuitive finding, explained in Section 6.7 of the report.
- **2 new edge cases** (`edge_cases.py`, now 8 cases / 14 assertions):
  reserve-pool exhaustion under a surge, and a non-existent reserved
  porter ID (config typo).
- **`scripts/live_runthrough.py`** (new): a scripted end-to-end session
  exercising the exact engine calls `app.py`'s buttons use. This sandbox
  has no internet access (`pip install streamlit` fails here), so this is
  a logic-level run-through, not a browser click-through — see the script's
  docstring and Section 4.2 of the report for what that does and doesn't
  prove. Run `streamlit run app.py` locally to see the actual rendered page.
- **`app.py` demo-clock fix**: the live tracker was comparing historical
  (Aug 2026) data against today's real date, making every request show as
  "Breached". Added a sidebar control to pick a simulated point in time
  inside the dataset's week instead.
- **`scripts/generate_historical_charts.py`** (new): Review 1 shipped two
  report figures with no script to reproduce them. Added for full
  pipeline reproducibility.

## Project layout

```
data/
  transport_requests.csv   synthetic dataset: 662 requests over 1 week
  porters.csv               8-porter roster with shifts/home zones
  locations.csv              hospital location -> zone map

scripts/
  data_generator.py         builds the synthetic dataset (re-runnable, seeded)
  baseline.py                naive FIFO baseline coordination policy
  prototype_engine.py        core decision engine: validation, confidence
                              scoring, priority scoring, porter recommendation,
                              SLA/uncertainty detection, and (Review 2) a
                              reserved-porter-pool variant, simulate_queue_with_reserve()
  edge_cases.py               8 automated failure-state tests, 14/14 passing
  experiment.py                runs baseline vs prototype over identical demand,
                                produces outputs/experiment_summary.csv and charts
  experiment_mitigation.py     (Review 2) tests the reserved-porter mitigation
                                and a capacity-addition sanity check
  live_runthrough.py           (Review 2) scripted end-to-end staff-session
                                run-through of app.py's logic path
  generate_historical_charts.py (Review 2) reproduces the two historical/
                                confidence figures used in the report
  build_report.js               generates the Word report from docx (Node)

app.py                        Streamlit end-to-end working prototype (the
                               actual tracker UI staff would use), with a
                               Review 2 sidebar demo-clock control

outputs/
  Hospital_Transport_Tracker_Report.docx   the full project report
  baseline_result.csv / prototype_result.csv
  experiment_summary.csv / error_analysis.csv
  mitigation_experiment_summary.csv         (Review 2)
  live_runthrough_log.txt                   (Review 2) full session transcript
  chart_*.png                              figures used in the report
```

## Running it

```bash
# 1. Regenerate the dataset (optional -- one is already included)
python3 scripts/data_generator.py

# 2. Run the baseline and prototype engines
python3 scripts/baseline.py
python3 scripts/prototype_engine.py

# 3. Run the automated edge-case tests (8 cases, 14 assertions)
cd scripts && python3 edge_cases.py && cd ..

# 4. Run the measurable experiment (baseline vs prototype vs target)
python3 scripts/experiment.py

# 5. (Review 2) Run the reserved-porter mitigation experiment
python3 scripts/experiment_mitigation.py

# 6. (Review 2) Run the scripted live run-through of the staff workflow
python3 scripts/live_runthrough.py

# 7. (Review 2) Regenerate the two historical/confidence report figures
python3 scripts/generate_historical_charts.py

# 8. Launch the interactive tracker (requires streamlit + pandas)
pip install streamlit pandas
streamlit run app.py
```

## Design principle

Every function in `prototype_engine.py` is a `recommend_*`/`detect_*`
**read-only** function — it produces a suggestion, a confidence flag, and a
plain-language reason. The only code that ever writes a final assignment,
handover confirmation, override, escalation, or cancellation lives inside
`app.py`'s button handlers, and requires a named, logged-in staff member to
click it. Every such action is appended to an in-session audit log.
