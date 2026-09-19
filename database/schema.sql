-- EVGuard database schema
-- Based on EVGuard_FINAL_README.md §19
-- Note: No token column is stored anywhere.

CREATE TABLE IF NOT EXISTS command_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    command_id TEXT UNIQUE NOT NULL,
    received_at TEXT NOT NULL,
    client_timestamp TEXT,
    session_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    role TEXT,
    command_type TEXT NOT NULL,
    value REAL,
    unit TEXT,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL,
    rule_triggered TEXT NOT NULL,
    state_before TEXT NOT NULL,
    state_after TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    vehicle_id TEXT NOT NULL,
    max_power_kw REAL NOT NULL,
    max_current_a REAL NOT NULL,
    current_state TEXT NOT NULL,
    current_power_kw REAL,
    current_current_a REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

