# Testing Guide

Three layers, each answering a different question. All use only the Python
standard library + pandas (no pytest, no extra installs).

| Layer | File | Question it answers | Run |
|---|---|---|---|
| Unit tests (42) | `tests/test_engine.py` | Does each engine function behave correctly at its boundaries? | `python -m unittest discover -s tests -v` |
| Scenario / failure-state tests (8 cases, 14 checks) | `scripts/edge_cases.py` | Does the *whole pipeline* degrade safely on realistic messy situations? | `cd scripts && python edge_cases.py` |
| Workflow run-through | `scripts/live_runthrough.py` | Does a full staff session (log -> recommend -> override -> handover) work and get audited? | `python scripts/live_runthrough.py` |

Run everything in one go from the project root:

```bash
python -m unittest discover -s tests && (cd scripts && python edge_cases.py) && python scripts/live_runthrough.py
```

## Unit test map (what each class protects)

| Test class | # | Function under test | Key boundaries pinned |
|---|---|---|---|
| `TestCanonicaliseLocation` | 5 | `canonicalise_location` | exact vs corrected vs missing vs unrecognised; whitespace; None/NaN/"" all -> `missing`; garbage is never guessed |
| `TestValidateRequests` | 10 | `validate_requests` | never drops a row; input not mutated; missing/unrecognised location -> **Low**; auto-corrected -> **Medium**; blank/invalid urgency -> **Urgent, never Routine**; missing timestamp flagged |
| `TestScorePriority` | 6 | `score_priority` | tier ordering; aging capped; low-confidence boosted (never hidden); unknown urgency scored as Urgent; **aged Routine (max 66) can never outrank fresh Emergency (min 100)** |
| `TestRecommendPorter` | 5 | `recommend_porter` | empty roster -> `(None, reason)`; unresolved source -> `(None, reason)`; earliest-available wins; zone distance breaks ties; **does not mutate roster (read-only guarantee)** |
| `TestDetectSlaState` | 7 | `detect_sla_state` | missing request time; on-time vs late; exactly-at-SLA is on time; handover-before-arrival (clock skew) and negative duration -> `Unknown-BadTimestamps`; open-request thresholds (On-Track / At-Risk >70% / Breached) |
| `TestSimulateQueue` | 5 | `simulate_queue` | empty roster doesn't crash and escalates all; every row gets an outcome; bad timestamp flagged not dropped; deterministic across runs; **regression: unresolved source is not a free zero-distance trip** |
| `TestSimulateQueueWithReserve` | 4 | `simulate_queue_with_reserve` | empty reserve == plain simulation exactly; unknown reserved ID degrades to no-reserve; Emergency overflow still assigns everyone; non-Emergency never uses reserved porters |

## Do the tests actually catch bugs? (mutation check)

Passing tests prove little unless they fail when the code is wrong, so three
bugs were injected on purpose and each was caught:

| Injected bug | Caught by |
|---|---|
| unknown urgency silently defaults to `Routine` | `TestValidateRequests` (default-to-Urgent tests) |
| aging boost cap removed | `TestScorePriority` (cap + no-inversion tests) |
| the original Review 1 zone-fallback bug re-introduced | `test_unresolved_source_is_not_a_free_zero_distance_trip` |

The third was **not** caught by the first version of the regression test (the
sample data never made distance affect an SLA outcome). It was rewritten with a
single zone-5 porter so a 2-zone trip (11 min) visibly breaches the 10-min
Emergency SLA. Lesson recorded: a regression test must make the bug change an
observable result.

## What is NOT unit-tested (honest gaps)

- `app.py` button handlers (Streamlit needs a browser/runtime). Mitigation:
  handlers are thin and call only tested engine functions; `live_runthrough.py`
  exercises the same call path; a manual click-through checklist is in
  `docs/ERROR_BOUNDARIES.md`.
- `data_generator.py` realism (checked statistically in the report, not asserted).
- Performance/load: single-session CSV-backed prototype, no load target yet.

## Adding a test

1. Put it in the class for the function it exercises (or add a class).
2. Build input with `make_row(field=bad_value)` — one defect per test.
3. Assert on the **observable output column / return value**, not on internals.
4. Name it `test_<situation>_<expected_behaviour>`.
