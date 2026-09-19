-- EVGuard database schema
-- Based on EVGuard_FINAL_README.md §19
-- Note: No token column is stored anywhere.
--
-- Columns that can be unknown for a malformed or unauthenticated command
-- (session_id, source_id, command_type, state_before, state_after) are nullable.
-- command_id is indexed but not UNIQUE: a duplicate-ID attempt is logged too.

CREATE TABLE IF NOT EXISTS command_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    command_id TEXT NOT NULL,
    received_at TEXT NOT NULL,
    client_timestamp TEXT,
    session_id TEXT,
    source_id TEXT,
    role TEXT,
    command_type TEXT,
    value REAL,
    unit TEXT,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL,
    rule_triggered TEXT NOT NULL,
    state_before TEXT,
    state_after TEXT
);

CREATE INDEX IF NOT EXISTS idx_command_log_command_id ON command_log (command_id);

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
