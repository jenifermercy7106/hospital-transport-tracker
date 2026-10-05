"""
app.py
------
Hospital Transport Request Tracker — end-to-end working prototype (Streamlit).

Core principle: the system RECOMMENDS (priority score, suggested porter,
confidence flag). Every final action -- assigning a porter, confirming a
handover, overriding a recommendation, escalating, or cancelling -- is a
button click by an authorised staff member. Nothing happens automatically.
Every action is stamped with who confirmed it and when, in an append-only
action log, so clinician/porter accountability for the actual transfer is
preserved even though the system is doing the coordination legwork that
used to happen over the phone.

Run:  streamlit run app.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scripts"))

import pandas as pd
import streamlit as st
from datetime import datetime

from prototype_engine import (
    validate_requests, score_priority, recommend_porter, detect_sla_state, ZONE
)

st.set_page_config(page_title="Transport Request Tracker", layout="wide")

DATA_PATH = "data/transport_requests.csv"
PORTERS_PATH = "data/porters.csv"

STAFF_ROLES = ["Staff Nurse", "Ward Sister", "OT Coordinator", "Duty Doctor", "Charge Nurse"]


# ---------------------------------------------------------------------------
# Session state init (in-memory "live" system state for this demo session)
# ---------------------------------------------------------------------------

def load_data():
    df = pd.read_csv(DATA_PATH)
    df = validate_requests(df)
    df["timestamp_requested"] = pd.to_datetime(df["timestamp_requested"], errors="coerce")
    # For the live-tracker demo we treat everything as "open" unless it
    # already had a handover_confirmed timestamp in the historical data.
    df["live_status"] = df["timestamp_handover_confirmed"].apply(
        lambda x: "Handover Confirmed" if pd.notna(x) and str(x).strip() != "" else "Open"
    )
    df["assigned_porter_live"] = df["porter_id"].fillna("")
    return df


if "requests" not in st.session_state:
    st.session_state.requests = load_data()
if "porters" not in st.session_state:
    st.session_state.porters = pd.read_csv(PORTERS_PATH)
if "action_log" not in st.session_state:
    st.session_state.action_log = []
if "new_req_counter" not in st.session_state:
    st.session_state.new_req_counter = 1


def log_action(staff_name, staff_role, action, request_id, detail=""):
    st.session_state.action_log.append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "staff_name": staff_name,
        "staff_role": staff_role,
        "action": action,
        "request_id": request_id,
        "detail": detail,
    })


# ---------------------------------------------------------------------------
# Sidebar: "who is logged in" (authorised staff control) + new request intake
# ---------------------------------------------------------------------------

st.sidebar.title("🏥 Staff Console")
staff_name = st.sidebar.text_input("Your name", value="A. Kumar")
staff_role = st.sidebar.selectbox("Your role", STAFF_ROLES)
st.sidebar.caption(
    "All actions below are logged against this name/role. The system only "
    "recommends — nothing is finalised without your confirmation."
)

st.sidebar.markdown("---")
st.sidebar.subheader("🕒 Demo clock")
st.sidebar.caption(
    "The sample dataset is historical (24–30 Aug 2026). In a real deployment "
    "this app would just use the real current time; for this demo, pick a "
    "point inside the dataset's week so SLA/waiting-time colours are meaningful "
    "instead of showing everything as breached against today's real clock."
)
use_real_clock = st.sidebar.checkbox("Use real current time instead", value=False)
if use_real_clock:
    demo_now = pd.Timestamp.now()
else:
    sim_date = st.sidebar.date_input(
        "Simulated date", value=pd.Timestamp("2026-08-28").date(),
        min_value=pd.Timestamp("2026-08-24").date(), max_value=pd.Timestamp("2026-08-30").date(),
    )
    sim_time = st.sidebar.slider("Simulated time of day (hour)", 0, 23, 14)
    demo_now = pd.Timestamp(sim_date) + pd.Timedelta(hours=sim_time)
st.sidebar.caption(f"Tracker is showing the queue as it stood at: **{demo_now}**")

st.sidebar.markdown("---")
st.sidebar.subheader("📞 Log a new transport request")
with st.sidebar.form("new_request_form", clear_on_submit=True):
    patient_id = st.text_input("Patient ID", value="")
    source = st.selectbox("Source location", options=[""] + sorted(ZONE.keys()))
    destination = st.selectbox("Destination location", options=[""] + sorted(ZONE.keys()))
    urgency = st.selectbox("Urgency", options=["", "Emergency", "Urgent", "Routine"])
    reason = st.text_input("Reason", value="")
    submitted = st.form_submit_button("Submit request")

    if submitted:
        new_id = f"NEW{st.session_state.new_req_counter:04d}"
        st.session_state.new_req_counter += 1
        new_row = {
            "request_id": new_id, "patient_id": patient_id or "UNKNOWN",
            "department": staff_role, "reason": reason,
            "timestamp_requested": demo_now,
            "source_location": source, "destination_location": destination,
            "urgency": urgency, "requested_by": f"{staff_name} ({staff_role})",
            "porter_id": "", "timestamp_assigned": "", "timestamp_arrived_source": "",
            "timestamp_handover_confirmed": "",
            "sla_minutes": {"Emergency": 10, "Urgent": 30, "Routine": 90}.get(urgency, 30),
            "status": "", "delay_reason": "",
        }
        new_df = validate_requests(pd.DataFrame([new_row]))
        new_df["timestamp_requested"] = pd.to_datetime(new_df["timestamp_requested"])
        new_df["live_status"] = "Open"
        new_df["assigned_porter_live"] = ""
        st.session_state.requests = pd.concat(
            [new_df, st.session_state.requests], ignore_index=True
        )
        log_action(staff_name, staff_role, "Logged new request", new_id,
                   f"{source or '(missing)'} -> {destination or '(missing)'}, urgency={urgency or '(unspecified)'}")
        st.sidebar.success(f"Request {new_id} logged.")


# ---------------------------------------------------------------------------
# Main: live queue, colour-coded, with per-row recommendation + action buttons
# ---------------------------------------------------------------------------

st.title("🚑 Hospital Transport Request Tracker")
st.caption(
    "Shared operating-theatre transport coordination — replaces the phone-call "
    "board. Staff retain final control over every assignment and handover."
)

df = st.session_state.requests
open_df = df[df["live_status"] == "Open"].copy()

now = demo_now
# use the historical requested time as-is for demo realism (data is dated in the past)
open_df["waiting_minutes"] = (now - open_df["timestamp_requested"]).dt.total_seconds() / 60.0
open_df["waiting_minutes"] = open_df["waiting_minutes"].clip(lower=0)

open_df["priority_score"] = open_df.apply(
    lambda r: score_priority(r["resolved_urgency"], min(r["waiting_minutes"], 180), r["data_confidence"]),
    axis=1,
)

porters_status = {
    row["porter_id"]: {"zone": row["home_zone"], "available_at": pd.Timestamp.min}
    for _, row in st.session_state.porters.iterrows()
}
# mark porters currently holding an unconfirmed assignment as busy (best-effort demo signal)
busy_porters = set(open_df.loc[open_df["assigned_porter_live"] != "", "assigned_porter_live"])

def recommend_row(row):
    if row["assigned_porter_live"]:
        return row["assigned_porter_live"], "Already assigned"
    src_zone = ZONE.get(row["resolved_source"])
    avail = {pid: v for pid, v in porters_status.items() if pid not in busy_porters}
    pid, reason = recommend_porter(src_zone, avail)
    return pid, reason

open_df[["recommended_porter", "recommendation_reason"]] = open_df.apply(
    lambda r: pd.Series(recommend_row(r)), axis=1
)

open_df["sla_state"] = open_df.apply(
    lambda r: detect_sla_state(
        r["timestamp_requested"],
        pd.NaT, pd.NaT,
        {"Emergency": 10, "Urgent": 30, "Routine": 90}.get(r["resolved_urgency"], 30),
        now=now,
    ),
    axis=1,
)

open_df = open_df.sort_values("priority_score", ascending=False)

# --- KPI row ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Open requests", len(open_df))
col2.metric("Breached SLA", int((open_df["sla_state"] == "Breached").sum()))
col3.metric("At risk", int((open_df["sla_state"] == "At-Risk").sum()))
col4.metric("Low-confidence input", int((open_df["data_confidence"] == "Low").sum()))

st.markdown("---")

SLA_COLOR = {
    "Breached": "🔴", "At-Risk": "🟠", "On-Track": "🟢", "Unknown-BadTimestamps": "⚪",
}
CONF_BADGE = {"High": "", "Medium": "🟡 medium confidence", "Low": "🔺 LOW confidence — verify"}

if len(open_df) == 0:
    st.info("No open requests. Use the sidebar to log a new transport request.")
else:
    for _, row in open_df.head(40).iterrows():
        sla_icon = SLA_COLOR.get(row["sla_state"], "⚪")
        conf_badge = CONF_BADGE.get(row["data_confidence"], "")
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 3, 2])
            with c1:
                st.markdown(
                    f"**{sla_icon} {row['request_id']}** — {row['resolved_urgency']} "
                    f"&nbsp; *(priority {row['priority_score']:.0f})*"
                )
                st.write(f"Patient: `{row['patient_id']}`  ·  {row['reason']}")
                st.write(
                    f"📍 {row['resolved_source'] or '⚠️ unresolved'} → "
                    f"{row['resolved_destination'] or '⚠️ unresolved'}"
                )
                if conf_badge:
                    st.caption(conf_badge)
                if row["data_issues"]:
                    st.caption(f"⚠️ Data issue(s): {row['data_issues']}")
            with c2:
                st.write(f"Waiting: **{row['waiting_minutes']:.0f} min**  ·  SLA state: **{row['sla_state']}**")
                if row["assigned_porter_live"]:
                    st.write(f"Assigned porter: **{row['assigned_porter_live']}**")
                else:
                    st.write(f"Suggested porter: **{row['recommended_porter'] or '— none available —'}**")
                    st.caption(row["recommendation_reason"])
            with c3:
                rid = row["request_id"]
                if not row["assigned_porter_live"]:
                    override_porter = st.selectbox(
                        "Assign porter", options=[""] + list(st.session_state.porters["porter_id"]),
                        index=(
                            (["" ] + list(st.session_state.porters["porter_id"])).index(row["recommended_porter"])
                            if row["recommended_porter"] in list(st.session_state.porters["porter_id"])
                            else 0
                        ),
                        key=f"assign_{rid}",
                    )
                    if st.button("✅ Confirm assignment", key=f"btn_assign_{rid}"):
                        idx = st.session_state.requests["request_id"] == rid
                        st.session_state.requests.loc[idx, "assigned_porter_live"] = override_porter
                        is_override = override_porter != row["recommended_porter"] and override_porter != ""
                        log_action(
                            staff_name, staff_role,
                            "Overrode recommendation" if is_override else "Confirmed assignment",
                            rid, f"porter={override_porter} (recommended={row['recommended_porter']})",
                        )
                        st.rerun()
                else:
                    if st.button("🤝 Confirm handover", key=f"btn_handover_{rid}"):
                        idx = st.session_state.requests["request_id"] == rid
                        st.session_state.requests.loc[idx, "live_status"] = "Handover Confirmed"
                        st.session_state.requests.loc[idx, "timestamp_handover_confirmed"] = \
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        log_action(staff_name, staff_role, "Confirmed handover", rid,
                                   f"porter={row['assigned_porter_live']}")
                        st.rerun()
                    if st.button("🔁 Reassign / escalate", key=f"btn_reassign_{rid}"):
                        idx = st.session_state.requests["request_id"] == rid
                        st.session_state.requests.loc[idx, "assigned_porter_live"] = ""
                        log_action(staff_name, staff_role, "Escalated / released porter", rid,
                                   "Returned to queue for reassignment")
                        st.rerun()
                if st.button("🚫 Cancel request", key=f"btn_cancel_{rid}"):
                    idx = st.session_state.requests["request_id"] == rid
                    st.session_state.requests.loc[idx, "live_status"] = "Cancelled"
                    log_action(staff_name, staff_role, "Cancelled request", rid, "")
                    st.rerun()

st.markdown("---")

# ---------------------------------------------------------------------------
# Action log (audit trail — proves staff retained final control)
# ---------------------------------------------------------------------------

with st.expander("📋 Staff action log (audit trail)", expanded=False):
    if st.session_state.action_log:
        st.dataframe(pd.DataFrame(st.session_state.action_log)[::-1], use_container_width=True)
    else:
        st.write("No actions logged yet this session.")

with st.expander("📊 Completed / cancelled today", expanded=False):
    done_df = df[df["live_status"] != "Open"]
    st.dataframe(
        done_df[["request_id", "patient_id", "resolved_urgency", "live_status",
                  "assigned_porter_live", "timestamp_handover_confirmed"]],
        use_container_width=True,
    )
