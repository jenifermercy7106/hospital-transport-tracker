-- docs/schema.sql  --  PLANNED persistence schema (design only; not yet used by app.py).
-- Written to run unchanged on SQLite (stdlib sqlite3) and, with minor type
-- tweaks (TEXT->TIMESTAMPTZ), on PostgreSQL. Validated by loading it into an
-- in-memory SQLite DB (see docs/API_AND_SCHEMA.md).

PRAGMA foreign_keys = ON;

CREATE TABLE locations (
    location_name TEXT PRIMARY KEY,
    zone          INTEGER NOT NULL CHECK (zone BETWEEN 1 AND 5)
);

CREATE TABLE porters (
    porter_id        TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    home_zone        INTEGER NOT NULL CHECK (home_zone BETWEEN 1 AND 5),
    shift_start_hour INTEGER NOT NULL CHECK (shift_start_hour BETWEEN 0 AND 23),
    shift_end_hour   INTEGER NOT NULL CHECK (shift_end_hour BETWEEN 0 AND 24)
);

CREATE TABLE staff (               -- authenticated users (replaces free-text name/role)
    staff_id TEXT PRIMARY KEY,
    name     TEXT NOT NULL,
    role     TEXT NOT NULL CHECK (role IN ('Ward Sister','OT Coordinator','Duty Doctor','Porter Desk'))
);

CREATE TABLE transport_requests (
    request_id            TEXT PRIMARY KEY,
    patient_id            TEXT NOT NULL,
    department            TEXT,
    reason                TEXT,
    requested_at          TEXT,                       -- ISO-8601; NULL allowed (bad input is flagged, not rejected)
    source_raw            TEXT,                       -- exactly what was typed
    destination_raw       TEXT,
    source_resolved       TEXT REFERENCES locations(location_name),   -- NULL if unresolved
    destination_resolved  TEXT REFERENCES locations(location_name),
    urgency_raw           TEXT,
    urgency_resolved      TEXT NOT NULL CHECK (urgency_resolved IN ('Emergency','Urgent','Routine')),
    data_confidence       TEXT NOT NULL CHECK (data_confidence IN ('High','Medium','Low')),
    data_issues           TEXT NOT NULL DEFAULT '',
    sla_minutes           INTEGER NOT NULL CHECK (sla_minutes > 0),
    status                TEXT NOT NULL DEFAULT 'Open'
                          CHECK (status IN ('Open','Handover Confirmed','Cancelled')),
    assigned_porter_id    TEXT REFERENCES porters(porter_id),         -- set ONLY by a staff action
    assigned_at           TEXT,
    arrived_source_at     TEXT,
    handover_confirmed_at TEXT,
    requested_by_staff_id TEXT REFERENCES staff(staff_id)
);
CREATE INDEX idx_requests_open ON transport_requests(status, urgency_resolved, requested_at);

CREATE TABLE action_log (          -- append-only audit trail
    log_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at   TEXT NOT NULL,                       -- real wall-clock time of the click
    staff_id    TEXT NOT NULL REFERENCES staff(staff_id),
    request_id  TEXT NOT NULL REFERENCES transport_requests(request_id),
    action      TEXT NOT NULL CHECK (action IN
                ('Logged new request','Confirmed assignment','Overrode recommendation',
                 'Confirmed handover','Escalated / released porter','Cancelled request')),
    detail      TEXT NOT NULL DEFAULT ''
);
-- Enforce append-only at the database level (staff-control accountability):
CREATE TRIGGER action_log_no_update BEFORE UPDATE ON action_log
BEGIN SELECT RAISE(ABORT, 'action_log is append-only'); END;
CREATE TRIGGER action_log_no_delete BEFORE DELETE ON action_log
BEGIN SELECT RAISE(ABORT, 'action_log is append-only'); END;
