# Hospital Transport Request Tracker

Urgency-, location- and handover-aware transport coordination prototype for a
multi-specialty hospital sharing operating theatres across departments.
Built to replace an unreliable phone-call coordination process while keeping
**every final action under authorised staff control**.

See `outputs/Hospital_Transport_Tracker_Report.docx` for the full write-up
(scenario, baseline, solution design, usability walkthrough, edge-case
tests, performance results with error analysis, ethics note, and a
deployment checklist).

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
                              SLA/uncertainty detection (fully unit-testable,
                              framework-independent)
  edge_cases.py               6 automated failure-state tests (10/10 passing)
  experiment.py                runs baseline vs prototype over identical demand,
                                produces outputs/experiment_summary.csv and charts
  build_report.js               generates the Word report from docx (Node)

app.py                        Streamlit end-to-end working prototype (the
                               actual tracker UI staff would use)

outputs/
  Hospital_Transport_Tracker_Report.docx   the full project report
  baseline_result.csv / prototype_result.csv
  experiment_summary.csv / error_analysis.csv
  chart_*.png                              figures used in the report
```

## Running it

```bash
# 1. Regenerate the dataset (optional -- one is already included)
python3 scripts/data_generator.py

# 2. Run the baseline and prototype engines
python3 scripts/baseline.py
python3 scripts/prototype_engine.py

# 3. Run the automated edge-case tests
cd scripts && python3 edge_cases.py && cd ..

# 4. Run the measurable experiment (baseline vs prototype vs target)
python3 scripts/experiment.py

# 5. Launch the interactive tracker (requires streamlit + pandas)
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
