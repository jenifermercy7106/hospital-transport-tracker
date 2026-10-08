"""
tests/test_engine.py  (Review 2 follow-up)
------------------------------------------
Granular unit tests for scripts/prototype_engine.py using ONLY the Python
standard library (unittest) + pandas -- no pytest or extra installs needed.

Run from the project root:
    python -m unittest discover -s tests -v

Layout: one TestCase class per engine function, so a failure name tells you
exactly which function and which boundary broke. docs/TESTING.md maps each
test to the error boundary it protects.

How these differ from scripts/edge_cases.py: edge_cases.py is a *scenario*
suite (messy whole-dataset situations, prints a PASS/FAIL table for the
report). These are *unit* tests: one function, one behaviour, one assertion
focus, fast, runnable in CI.
"""
import os
import sys
import unittest

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import prototype_engine as pe  # noqa: E402


def make_row(**overrides):
    """A clean, valid request row; override fields to inject one defect."""
    row = {
        "request_id": "T1", "patient_id": "PT0001", "department": "Cardiology",
        "reason": "test", "timestamp_requested": "2026-08-24 10:00:00",
        "source_location": "Ward A1 (General Surgery)",
        "destination_location": "Radiology - CT", "urgency": "Urgent",
        "requested_by": "Staff Nurse", "porter_id": "", "timestamp_assigned": "",
        "timestamp_arrived_source": "", "timestamp_handover_confirmed": "",
        "sla_minutes": 30, "status": "", "delay_reason": "",
    }
    row.update(overrides)
    return row


def porters(n=3):
    """Small roster: porter i sits in zone i."""
    return pd.DataFrame([
        {"porter_id": f"P{i:02d}", "home_zone": i, "name": f"P{i}",
         "shift_start_hour": 7, "shift_end_hour": 21}
        for i in range(1, n + 1)
    ])


class TestCanonicaliseLocation(unittest.TestCase):
    def test_exact_match(self):
        self.assertEqual(pe.canonicalise_location("ICU"), ("ICU", "exact"))

    def test_exact_match_ignores_surrounding_whitespace(self):
        self.assertEqual(pe.canonicalise_location("  ICU  "), ("ICU", "exact"))

    def test_alias_is_corrected_not_exact(self):
        loc, state = pe.canonicalise_location("ward a1")
        self.assertEqual((loc, state), ("Ward A1 (General Surgery)", "corrected"))

    def test_none_nan_and_empty_are_missing(self):
        for bad in (None, float("nan"), ""):
            self.assertEqual(pe.canonicalise_location(bad), (None, "missing"))

    def test_garbage_is_unrecognised_never_guessed(self):
        self.assertEqual(pe.canonicalise_location("xyzzy"), (None, "unrecognised"))


class TestValidateRequests(unittest.TestCase):
    def run_one(self, **overrides):
        return pe.validate_requests(pd.DataFrame([make_row(**overrides)])).iloc[0]

    def test_clean_row_is_high_confidence_no_issues(self):
        r = self.run_one()
        self.assertEqual(r["data_confidence"], "High")
        self.assertEqual(r["data_issues"], "")

    def test_never_drops_rows(self):
        df = pd.DataFrame([make_row(request_id=f"T{i}", source_location=None) for i in range(5)])
        self.assertEqual(len(pe.validate_requests(df)), 5)

    def test_does_not_mutate_input_dataframe(self):
        df = pd.DataFrame([make_row()])
        cols_before = list(df.columns)
        pe.validate_requests(df)
        self.assertEqual(list(df.columns), cols_before)

    def test_missing_source_is_low_confidence(self):
        r = self.run_one(source_location=None)
        self.assertEqual(r["data_confidence"], "Low")
        self.assertIn("source location missing", r["data_issues"])

    def test_unrecognised_destination_is_low_confidence(self):
        self.assertEqual(self.run_one(destination_location="Narnia")["data_confidence"], "Low")

    def test_auto_corrected_location_is_medium_confidence(self):
        self.assertEqual(self.run_one(source_location="ward a1")["data_confidence"], "Medium")

    def test_blank_urgency_defaults_to_urgent_never_routine(self):
        for blank in (None, "", "   "):
            self.assertEqual(self.run_one(urgency=blank)["resolved_urgency"], "Urgent")

    def test_invalid_urgency_defaults_to_urgent(self):
        r = self.run_one(urgency="ASAP!!")
        self.assertEqual(r["resolved_urgency"], "Urgent")
        self.assertIn("unrecognised urgency", r["data_issues"])

    def test_valid_urgency_preserved(self):
        self.assertEqual(self.run_one(urgency="Emergency")["resolved_urgency"], "Emergency")

    def test_missing_timestamp_is_flagged(self):
        self.assertIn("request timestamp missing", self.run_one(timestamp_requested=None)["data_issues"])


class TestScorePriority(unittest.TestCase):
    def test_tier_ordering_at_zero_wait(self):
        e, u, r = (pe.score_priority(t, 0, "High") for t in ("Emergency", "Urgent", "Routine"))
        self.assertGreater(e, u)
        self.assertGreater(u, r)

    def test_aging_boost_is_capped(self):
        self.assertEqual(pe.score_priority("Routine", 10_000, "High"),
                         pe.score_priority("Routine", 80, "High"))   # cap = 40 pts

    def test_aging_increases_score_below_cap(self):
        self.assertGreater(pe.score_priority("Routine", 20, "High"),
                           pe.score_priority("Routine", 0, "High"))

    def test_low_confidence_gets_visibility_boost(self):
        self.assertGreater(pe.score_priority("Urgent", 0, "Low"), pe.score_priority("Urgent", 0, "High"))

    def test_unknown_urgency_treated_as_urgent_not_routine(self):
        self.assertEqual(pe.score_priority("???", 0, "High"), pe.score_priority("Urgent", 0, "High"))

    def test_aged_routine_cannot_overtake_fresh_emergency(self):
        # max Routine = 20 + 40 + 6 = 66 < min Emergency = 100  -> aging never inverts safety order
        self.assertLess(pe.score_priority("Routine", 10_000, "Low"),
                        pe.score_priority("Emergency", 0, "High"))


class TestRecommendPorter(unittest.TestCase):
    def status(self, **kw):
        t0 = pd.Timestamp("2026-08-24 10:00:00")
        return {pid: {"zone": z, "available_at": t0 + pd.Timedelta(minutes=m)}
                for pid, (z, m) in kw.items()}

    def test_empty_roster_returns_none_with_reason(self):
        pid, reason = pe.recommend_porter(1, {})
        self.assertIsNone(pid)
        self.assertIn("roster", reason.lower())

    def test_unresolved_source_returns_none_not_a_guess(self):
        pid, reason = pe.recommend_porter(None, self.status(P1=(1, 0)))
        self.assertIsNone(pid)
        self.assertIn("unresolved", reason.lower())

    def test_earliest_available_wins(self):
        self.assertEqual(pe.recommend_porter(1, self.status(P1=(1, 30), P2=(5, 0)))[0], "P2")

    def test_zone_distance_breaks_availability_tie(self):
        self.assertEqual(pe.recommend_porter(1, self.status(P1=(5, 0), P2=(2, 0)))[0], "P2")

    def test_does_not_mutate_roster_state(self):
        s = self.status(P1=(1, 0))
        before = {k: dict(v) for k, v in s.items()}
        pe.recommend_porter(1, s)
        self.assertEqual(s, before)           # read-only: staff control guarantee


class TestDetectSlaState(unittest.TestCase):
    T0 = pd.Timestamp("2026-08-24 10:00:00")

    def m(self, minutes):
        return self.T0 + pd.Timedelta(minutes=minutes)

    def test_missing_request_time_is_unknown(self):
        self.assertEqual(pe.detect_sla_state(pd.NaT, pd.NaT, pd.NaT, 30), "Unknown-BadTimestamps")

    def test_completed_on_time_and_late(self):
        self.assertEqual(pe.detect_sla_state(self.T0, self.m(20), pd.NaT, 30), "Completed-OnTime")
        self.assertEqual(pe.detect_sla_state(self.T0, self.m(45), pd.NaT, 30), "Completed-Late")

    def test_exactly_at_sla_counts_as_on_time(self):
        self.assertEqual(pe.detect_sla_state(self.T0, self.m(30), pd.NaT, 30), "Completed-OnTime")

    def test_handover_before_arrival_is_clock_skew(self):
        self.assertEqual(pe.detect_sla_state(self.T0, self.m(10), self.m(15), 30), "Unknown-BadTimestamps")

    def test_handover_before_request_never_gives_negative_duration(self):
        self.assertEqual(pe.detect_sla_state(self.T0, self.m(-5), pd.NaT, 30), "Unknown-BadTimestamps")

    def test_open_without_now_stays_open(self):
        self.assertEqual(pe.detect_sla_state(self.T0, pd.NaT, pd.NaT, 30), "Open")

    def test_open_state_thresholds(self):
        f = lambda mins: pe.detect_sla_state(self.T0, pd.NaT, pd.NaT, 30, now=self.m(mins))
        self.assertEqual(f(10), "On-Track")
        self.assertEqual(f(22), "At-Risk")      # > 70% of SLA
        self.assertEqual(f(31), "Breached")


class TestSimulateQueue(unittest.TestCase):
    def test_empty_roster_escalates_everything_and_does_not_crash(self):
        df = pd.DataFrame([make_row(request_id=f"T{i}", timestamp_requested=f"2026-08-24 10:0{i}:00") for i in range(3)])
        # an empty roster must not raise; behaviour is documented in docs/ERROR_BOUNDARIES.md
        out = pe.simulate_queue(df, porters(0))
        self.assertEqual(len(out), 3)
        self.assertTrue(out["prototype_escalated_for_review"].all())

    def test_every_input_row_gets_an_outcome(self):
        df = pd.DataFrame([make_row(request_id=f"T{i}", timestamp_requested=f"2026-08-24 10:0{i}:00") for i in range(5)])
        out = pe.simulate_queue(df, porters(3))
        self.assertEqual(len(out), 5)
        self.assertFalse(out["prototype_sla_outcome"].isna().any())

    def test_bad_timestamp_row_is_flagged_not_dropped(self):
        df = pd.DataFrame([make_row(timestamp_requested=None)])
        out = pe.simulate_queue(df, porters(2))
        self.assertEqual(out.iloc[0]["prototype_sla_outcome"], "Unknown-BadTimestamps")
        self.assertTrue(out.iloc[0]["prototype_escalated_for_review"])

    def test_unresolved_source_is_not_a_free_zero_distance_trip(self):
        """Regression (Review 2 bug): unresolved source must fall back to zone 3
        for BOTH porter choice and travel time. One porter in zone 5 -> distance 2
        -> 6 + 2*2.5 = 11 min, which breaches the 10-min Emergency SLA."""
        lone = pd.DataFrame([{"porter_id": "P01", "home_zone": 5, "name": "P1",
                              "shift_start_hour": 7, "shift_end_hour": 21}])
        df = pd.DataFrame([make_row(urgency="Emergency", source_location=None)])
        for sim in (pe.simulate_queue,
                    lambda d, p: pe.simulate_queue_with_reserve(d, p, reserved_porter_ids=set())):
            out = sim(df.copy(), lone)
            self.assertEqual(out.iloc[0]["prototype_sla_outcome"], "Completed-Late")

    def test_deterministic_across_runs(self):
        df = pd.DataFrame([make_row(request_id=f"T{i}", timestamp_requested="2026-08-24 10:00:00") for i in range(6)])
        a = pe.simulate_queue(df.copy(), porters(3))["prototype_assigned_porter"].tolist()
        b = pe.simulate_queue(df.copy(), porters(3))["prototype_assigned_porter"].tolist()
        self.assertEqual(a, b)


class TestSimulateQueueWithReserve(unittest.TestCase):
    def burst(self, n=4):
        return pd.DataFrame([make_row(request_id=f"E{i}", urgency="Emergency",
                                      timestamp_requested="2026-08-24 10:00:00") for i in range(n)])

    def test_empty_reserve_matches_plain_simulation_exactly(self):
        # regression test for the Review 2 zone-fallback bug
        df = pd.DataFrame([make_row(request_id=f"T{i}", source_location=(None if i % 3 == 0 else "ICU"),
                                    timestamp_requested=f"2026-08-24 10:{i:02d}:00") for i in range(12)])
        a = pe.simulate_queue(df.copy(), porters(3))["prototype_sla_outcome"].tolist()
        b = pe.simulate_queue_with_reserve(df.copy(), porters(3), reserved_porter_ids=set())["prototype_sla_outcome"].tolist()
        self.assertEqual(a, b)

    def test_unknown_reserved_id_degrades_to_no_reserve(self):
        out = pe.simulate_queue_with_reserve(self.burst(1), porters(3), reserved_porter_ids={"P99"})
        self.assertTrue(out["prototype_assigned_porter"].notna().all())

    def test_reserve_overflow_still_assigns_every_emergency(self):
        out = pe.simulate_queue_with_reserve(self.burst(4), porters(3), reserved_porter_ids={"P01"})
        self.assertTrue(out["prototype_assigned_porter"].notna().all())

    def test_non_emergency_never_uses_reserved_porter(self):
        df = pd.DataFrame([make_row(request_id=f"U{i}", urgency="Urgent",
                                    timestamp_requested=f"2026-08-24 10:0{i}:00") for i in range(5)])
        out = pe.simulate_queue_with_reserve(df, porters(3), reserved_porter_ids={"P01"})
        self.assertNotIn("P01", out["prototype_assigned_porter"].tolist())


if __name__ == "__main__":
    unittest.main(verbosity=2)
