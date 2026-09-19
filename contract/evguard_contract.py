"""EVGuard shared contract. Owned by Role 1. Do not edit your copy."""

CONTRACT_VERSION = "1.1"

# ---- States -----------------------------------------------------------
STATES = ["DISCONNECTED", "CONNECTED", "AUTHORIZED", "CHARGING", "STOPPED"]
INITIAL_STATE = "DISCONNECTED"

# ---- Commands ---------------------------------------------------------
COMMANDS = [
    "CONNECT",
    "AUTHORIZE_SESSION",
    "START_CHARGING",
    "SET_POWER",
    "SET_CURRENT",
    "STOP_CHARGING",
    "DISCONNECT",
]

# Commands that carry a value, and the ONLY unit allowed for each.
VALUE_COMMANDS = {"SET_POWER": "kW", "SET_CURRENT": "A"}

# (current_state, command) -> next_state. Anything not listed is invalid.
TRANSITIONS = {
    ("DISCONNECTED", "CONNECT"): "CONNECTED",
    ("CONNECTED", "AUTHORIZE_SESSION"): "AUTHORIZED",
    ("CONNECTED", "DISCONNECT"): "DISCONNECTED",
    ("AUTHORIZED", "START_CHARGING"): "CHARGING",
    ("AUTHORIZED", "DISCONNECT"): "DISCONNECTED",
    ("CHARGING", "SET_POWER"): "CHARGING",
    ("CHARGING", "SET_CURRENT"): "CHARGING",
    ("CHARGING", "STOP_CHARGING"): "STOPPED",
    ("STOPPED", "DISCONNECT"): "DISCONNECTED",
}

# ---- Decisions and rules -----------------------------------------------
ALLOW = "ALLOW"
BLOCK = "BLOCK"

RULES = {
    "ok": "All checks passed",
    "input.invalid": "Command is malformed (direct Python calls only; HTTP returns 422)",
    "auth.missing_token": "No token supplied",
    "auth.invalid_token": "Token unknown",
    "auth.source_mismatch": "Token belongs to a different source_id",
    "authz.command_not_permitted": "Role may not issue this command",
    "session.unknown": "session_id does not exist",
    "state.invalid_transition": "Command not valid in current state",
    "policy.power_limit": "Requested kW exceeds max_power_kw",
    "policy.current_limit": "Requested A exceeds max_current_a",
    "sequence.rate_exceeded": "Too many commands for this source+session in the window",
    "sequence.duplicate_command_id": "command_id already processed",
    "engine.internal_error": "Unexpected error - failed closed",
}

# Order of checks. The FIRST failing check decides the rule.
CHECK_ORDER = ["input", "auth", "authz", "session", "state", "policy", "sequence"]

# ---- Demo identities (prototype only, NOT secrets) --------------------
DEMO_SOURCES = {
    "controller_A": {"role": "controller", "token": "demo-token-controller-A"},
    "monitor_01": {"role": "monitor", "token": "demo-token-monitor-01"},
}
ROLE_PERMISSIONS = {
    "controller": list(COMMANDS),
    "monitor": [],  # read-only
}

# ---- Demo policy defaults ---------------------------------------------
DEFAULT_MAX_POWER_KW = 7.0
DEFAULT_MAX_CURRENT_A = 32.0
RATE_WINDOW_SECONDS = 10
RATE_MAX_COMMANDS = 10  # per (source_id, session_id) per window

# ---- Shared key lists (for tests) --------------------------------------
COMMAND_KEYS = ["command_id", "timestamp", "session_id", "source_id",
                "auth_token", "command_type", "value", "unit"]
DECISION_KEYS = ["command_id", "session_id", "source_id", "command_type",
                 "value", "unit", "decision", "rule_triggered", "reason",
                 "state_before", "state_after", "received_at"]
SESSION_KEYS = ["session_id", "vehicle_id", "state", "max_power_kw",
                "max_current_a", "updated_at", "physical"]
SNAPSHOT_KEYS = ["session_id", "vehicle_id", "plugged_in", "charging",
                 "power_kw", "current_a", "last_command", "updated_at"]
