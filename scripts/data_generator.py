"""
data_generator.py
------------------
Generates a realistic synthetic dataset for the Hospital Transport Request
Tracker project. Simulates one week of patient transport requests across a
multi-specialty hospital sharing operating theatres.

Deliberately injects real-world messiness:
- Missing / malformed locations
- Missing porter assignment
- Duplicate requests (phone-call re-entry)
- Clock-skew / out-of-order timestamps
- Occasional missing urgency tag

Output: data/transport_requests.csv, data/porters.csv, data/locations.csv
"""

import csv
import random
from datetime import datetime, timedelta

random.seed(42)

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

LOCATIONS = [
    "Ward A1 (General Surgery)", "Ward A2 (General Surgery)",
    "Ward B1 (Orthopedics)", "Ward B2 (Orthopedics)",
    "Ward C1 (Cardiology)", "Ward C2 (Cardiology)",
    "Ward D1 (Oncology)", "Ward D2 (Oncology)",
    "ICU", "NICU", "Emergency Department",
    "Radiology - CT", "Radiology - MRI", "Radiology - X-Ray",
    "OT Complex - Theatre 1", "OT Complex - Theatre 2", "OT Complex - Theatre 3",
    "Recovery / PACU", "Dialysis Unit", "Discharge Lounge",
]

# rough walking-time matrix substitute: zone id per location (adjacency proxy)
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

URGENCY_LEVELS = ["Emergency", "Urgent", "Routine"]
URGENCY_WEIGHTS = [0.12, 0.33, 0.55]          # emergencies are rarer but critical
URGENCY_SLA_MIN = {"Emergency": 10, "Urgent": 30, "Routine": 90}  # minutes to handover

DEPARTMENTS = ["General Surgery", "Orthopedics", "Cardiology", "Oncology",
               "Emergency Medicine", "Radiology", "Nephrology"]

REASONS = ["Pre-op transfer to OT", "Post-op transfer to Recovery/Ward",
           "Diagnostic imaging", "ICU transfer", "Dialysis session",
           "Ward-to-ward transfer", "Discharge transport"]

N_PORTERS = 8
PORTER_SHIFT_START_HOUR = 7
PORTER_SHIFT_END_HOUR = 21

SIM_START = datetime(2026, 8, 24, 0, 0, 0)   # a Monday
SIM_DAYS = 7
N_REQUESTS = 650


def gen_porters():
    porters = []
    for i in range(1, N_PORTERS + 1):
        porters.append({
            "porter_id": f"P{i:02d}",
            "name": f"Porter {i}",
            "home_zone": random.choice([1, 2, 3, 4, 5]),
            "shift_start_hour": PORTER_SHIFT_START_HOUR,
            "shift_end_hour": PORTER_SHIFT_END_HOUR,
        })
    return porters


def zone_distance(z1, z2):
    return abs(z1 - z2)


def random_timestamp():
    day_offset = random.randint(0, SIM_DAYS - 1)
    # transport requests skew towards daytime hours, long tail overnight (emergencies)
    hour = random.choices(
        population=list(range(24)),
        weights=[1, 1, 1, 1, 1, 2, 4, 6, 8, 9, 9, 8, 7, 8, 9, 9, 8, 7, 6, 5, 4, 3, 2, 1],
        k=1,
    )[0]
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    return SIM_START + timedelta(days=day_offset, hours=hour, minutes=minute, seconds=second)


def maybe_corrupt(value, corruption_rate=0.06):
    """Simulate missing/garbled real-world data entry."""
    if random.random() < corruption_rate:
        return ""
    return value


def maybe_typo_location(loc):
    """Simulate free-text call logging producing near-duplicate / malformed,
    missing, or unrecognisable locations -- the messiness a phone-call
    intake system realistically produces."""
    r = random.random()
    if r < 0.05:
        variants = {
            "Ward A1 (General Surgery)": "ward a1",
            "ICU": "icu unit",
            "OT Complex - Theatre 2": "OT-2",
            "Recovery / PACU": "recovery",
        }
        return variants.get(loc, loc.lower())
    elif r < 0.08:
        return ""   # caller didn't specify / staff forgot to log it
    elif r < 0.10:
        return "unknown / see nursing station"   # genuinely unrecognisable free text
    return loc


def generate_requests(porters):
    requests = []
    request_id = 1
    for _ in range(N_REQUESTS):
        ts_requested = random_timestamp()
        source = random.choice(LOCATIONS)
        # destination should differ and be plausible (not itself)
        destination = random.choice([l for l in LOCATIONS if l != source])
        urgency = random.choices(URGENCY_LEVELS, weights=URGENCY_WEIGHTS, k=1)[0]
        department = random.choice(DEPARTMENTS)
        reason = random.choice(REASONS)
        patient_id = f"PT{random.randint(1000, 9999)}"
        requested_by = random.choice(["Staff Nurse", "Ward Sister", "OT Coordinator",
                                       "Duty Doctor", "Radiology Tech"])

        sla_min = URGENCY_SLA_MIN[urgency]

        # --- porter assignment simulation (used later for "actual outcome" ground truth) ---
        eligible = [p for p in porters
                    if p["shift_start_hour"] <= ts_requested.hour < p["shift_end_hour"]]
        porter = random.choice(eligible) if eligible else None

        # base handling time depends on urgency + zone distance + random hospital noise
        if porter:
            dist = zone_distance(ZONE[source], ZONE.get(destination, ZONE[source]))
        else:
            dist = 3

        # response delay before a porter is actually free/dispatched (queueing effect)
        queue_noise = random.gauss(mu=8, sigma=6)
        response_delay = max(0, queue_noise)

        travel_time = 3 + dist * 2.5 + random.gauss(0, 2)
        travel_time = max(2, travel_time)

        handover_wait = random.gauss(4, 2)          # time spent confirming handover at destination
        handover_wait = max(1, handover_wait)

        # Missed-call effect: some requests simply never get logged to a porter in time
        # (phone line busy / call not picked up) -> no porter assigned at all
        missed_call = random.random() < 0.09
        if missed_call:
            porter = None

        ts_assigned = None
        ts_arrived_source = None
        ts_handover_confirmed = None
        status = ""
        delay_reason = ""

        if porter is None:
            status = "Missed"
            delay_reason = "No porter reached / call not picked up"
        else:
            ts_assigned = ts_requested + timedelta(minutes=response_delay)
            ts_arrived_source = ts_assigned + timedelta(minutes=travel_time * 0.4)
            ts_handover_confirmed = ts_arrived_source + timedelta(minutes=travel_time * 0.6 + handover_wait)

            total_minutes = (ts_handover_confirmed - ts_requested).total_seconds() / 60.0
            if total_minutes <= sla_min:
                status = "Completed"
            elif total_minutes <= sla_min * 2:
                status = "Delayed"
                delay_reason = random.choice([
                    "Porter occupied with another transfer",
                    "Lift / corridor congestion",
                    "Patient not ready (prep incomplete)",
                    "Equipment (wheelchair/trolley) unavailable",
                ])
            else:
                status = "Delayed"
                delay_reason = random.choice([
                    "Porter shift change during transfer",
                    "Multiple concurrent emergencies diverted porter",
                    "Ward could not release patient on time",
                    "Handover receiving unit unavailable",
                ])

        # cancellations (small fraction, e.g. patient condition changed / duplicate call)
        if status != "Missed" and random.random() < 0.03:
            status = "Cancelled"
            delay_reason = random.choice(["Duplicate request", "Patient condition changed",
                                           "Procedure postponed"])
            ts_handover_confirmed = None

        row = {
            "request_id": f"REQ{request_id:05d}",
            "patient_id": patient_id,
            "department": department,
            "reason": reason,
            "timestamp_requested": ts_requested.strftime("%Y-%m-%d %H:%M:%S"),
            "source_location": maybe_typo_location(source),
            "destination_location": maybe_typo_location(destination),
            "urgency": maybe_corrupt(urgency, 0.04),   # sometimes urgency not specified on call
            "requested_by": requested_by,
            "porter_id": porter["porter_id"] if porter else "",
            "timestamp_assigned": ts_assigned.strftime("%Y-%m-%d %H:%M:%S") if ts_assigned else "",
            "timestamp_arrived_source": ts_arrived_source.strftime("%Y-%m-%d %H:%M:%S") if ts_arrived_source else "",
            "timestamp_handover_confirmed": ts_handover_confirmed.strftime("%Y-%m-%d %H:%M:%S") if ts_handover_confirmed else "",
            "sla_minutes": sla_min,
            "status": status,
            "delay_reason": delay_reason,
        }
        requests.append(row)
        request_id += 1

    # inject a handful of duplicate calls (same patient/move logged twice within minutes)
    dupes = []
    for r in random.sample(requests, 12):
        d = dict(r)
        d["request_id"] = d["request_id"] + "-DUP"
        try:
            t = datetime.strptime(r["timestamp_requested"], "%Y-%m-%d %H:%M:%S")
            d["timestamp_requested"] = (t + timedelta(minutes=random.randint(1, 4))).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
        dupes.append(d)
    requests.extend(dupes)

    # inject a few clock-skew rows: handover timestamp logged BEFORE arrival (bad manual entry)
    for r in random.sample([r for r in requests if r["timestamp_handover_confirmed"]], 6):
        r["timestamp_handover_confirmed"], r["timestamp_arrived_source"] = (
            r["timestamp_arrived_source"], r["timestamp_handover_confirmed"]
        )

    random.shuffle(requests)
    return requests


def main():
    porters = gen_porters()
    requests = generate_requests(porters)

    with open("data/porters.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(porters[0].keys()))
        writer.writeheader()
        writer.writerows(porters)

    with open("data/locations.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["location", "zone"])
        for loc, z in ZONE.items():
            writer.writerow([loc, z])

    fieldnames = list(requests[0].keys())
    with open("data/transport_requests.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(requests)

    print(f"Generated {len(requests)} transport requests, {len(porters)} porters.")


if __name__ == "__main__":
    main()
