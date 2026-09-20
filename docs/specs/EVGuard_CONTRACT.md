# EVGuard Shared Contract — v1.1

> **Canonical source: `contract/evguard_contract.py`** (the code imports it). This Markdown file and its twin `docs/specs/EVGuard_CONTRACT.md` are **read-only mirrors** kept byte-for-byte identical; the Python block in §2 is a verbatim copy of the canonical file. To change the contract, edit the `.py` first, then re-sync both mirrors. `tests/test_core_docs_sync.py` fails if they drift.

**Owner:** Role 1 — Gopesh (team lead). Only Gopesh edits this file.
**Team:** Role 1 Gopesh (core engine, backend, final integration) · Role 2 Videsh (simulator, scenarios, baseline) · Role 3 Vishwajit (dashboard, `backend/schemas.py`, QA + demo)
**Everyone:** copy this file into your repo as `contract/CONTRACT.md`, and copy the Python block in §2 into `contract/evguard_contract.py`. Never edit your copy. When a new version is published, replace your copy completely.

This contract is the single source of truth for names, data shapes and function signatures. If the README disagrees with it, **the contract wins** for implementation.

---

## 0. How changes work (read this once)

1. Nobody invents a new command name, state name, rule ID or JSON key on their own.
2. If you need a change, post in the team chat: `CONTRACT REQUEST: <what> — <why>`.
3. Role 1 decides, bumps the version (`1.0 → 1.1`) and posts the new file with a 3-line changelog at the bottom.
4. **Additive changes only** after Hour 8 (new optional key = OK; renaming or removing = not OK unless the whole team agrees).
5. Everyone replaces their copy within 30 minutes and replies "on v1.x".

---

## 1. Final folder layout (every repo mirrors this)

Each person creates **only their own folders**, but uses exactly these names, so integration is copy-and-paste of folders.

```text
evguard/
├── contract/            ← everyone (identical copies, owned by Role 1)
│   ├── CONTRACT.md
│   ├── evguard_contract.py
│   └── __init__.py
├── core/                ← Role 1
├── backend/             ← Role 1, except backend/schemas.py ← Role 3
├── database/            ← Role 1
├── config/              ← Role 1
├── simulator/           ← Role 2
├── dashboard/           ← Role 3
├── tests/               ← everyone, file names prefixed by owner (see §8)
└── docs/                ← Role 3 (demo script, screenshots)
```

Every package folder contains an empty `__init__.py`.
Imports are always absolute from the project root: `from contract.evguard_contract import STATES`, `from simulator.scenarios import run_scenario`.
Always run commands **from the project root folder**.

**Python version:** 3.12 for everyone (3.11 acceptable). Check with `python --version`.

---

## 2. `contract/evguard_contract.py` (copy exactly)

```python
"""EVGuard shared contract. Owned by Role 1. Do not edit your copy."""

# CANONICAL FILE: this is the single source of truth (the code imports it).
# contract/CONTRACT.md and docs/specs/EVGuard_CONTRACT.md are read-only mirrors:
# edit this file first, then re-copy it into their Python block. Never edit a mirror alone.

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
    "input.invalid": "Command is malformed (schema violations return HTTP 422; other malformed commands return BLOCK)",
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
```

---

## 3. Data shapes (JSON / Python dicts)

### 3.1 Command (input)

```json
{
  "command_id": "cmd_7f3a9c",
  "timestamp": "2026-09-20T10:00:03Z",
  "session_id": "sess_demo",
  "source_id": "controller_A",
  "auth_token": "demo-token-controller-A",
  "command_type": "SET_POWER",
  "value": 5.0,
  "unit": "kW"
}
```

- `value` and `unit` are `null`/missing for non-value commands.
- `timestamp` is optional and informational only.
- `command_id` must be unique (use `"cmd_" + uuid4().hex[:12]`).

### 3.2 Decision (output of the engine)

```json
{
  "command_id": "cmd_7f3a9c",
  "session_id": "sess_demo",
  "source_id": "controller_A",
  "command_type": "SET_POWER",
  "value": 20.0,
  "unit": "kW",
  "decision": "BLOCK",
  "rule_triggered": "policy.power_limit",
  "reason": "Requested power 20.0 kW exceeds session maximum of 7.0 kW",
  "state_before": "CHARGING",
  "state_after": "CHARGING",
  "received_at": "2026-09-20T10:00:03.412Z"
}
```

On ALLOW, `rule_triggered` is `"ok"`. On BLOCK, `state_after == state_before`. The token is **never** included.

**Nullable fields (v1.1):** `state_before`/`state_after` are `null` when the command fails input, duplicate-ID or authentication checks (unauthenticated callers never learn session state). `session_id`, `source_id`, `command_type`, `value`, `unit` are `null` when the input is malformed. Consumers (dashboard) must display `null` as "—".

### 3.3 Session (engine view + physical snapshot)

```json
{
  "session_id": "sess_demo",
  "vehicle_id": "Vehicle-01",
  "state": "CHARGING",
  "max_power_kw": 7.0,
  "max_current_a": 32.0,
  "updated_at": "2026-09-20T10:00:03.412Z",
  "physical": {
    "session_id": "sess_demo",
    "vehicle_id": "Vehicle-01",
    "plugged_in": true,
    "charging": true,
    "power_kw": 5.0,
    "current_a": 0.0,
    "last_command": "SET_POWER",
    "updated_at": "2026-09-20T10:00:03.412Z"
  }
}
```

### 3.4 Session definition (used to create/reset a session)

```json
{"session_id": "sess_demo", "vehicle_id": "Vehicle-01", "max_power_kw": 7.0, "max_current_a": 32.0}
```

### 3.5 Scenario file (Role 2 writes, everyone reads)

`simulator/scenario_data/<name>.json`

```json
{
  "name": "excess_power",
  "title": "Excess power attack",
  "description": "Valid controller asks for 20 kW on a 7 kW session.",
  "session": {"session_id": "sess_excess_power", "vehicle_id": "Vehicle-01",
              "max_power_kw": 7.0, "max_current_a": 32.0},
  "steps": [
    {"source_id": "controller_A", "auth_token": "demo-token-controller-A",
     "command_type": "CONNECT", "expect": "ALLOW", "expect_rule": "ok"},
    {"source_id": "controller_A", "auth_token": "demo-token-controller-A",
     "command_type": "SET_POWER", "value": 20.0, "unit": "kW",
     "expect": "BLOCK", "expect_rule": "policy.power_limit"}
  ]
}
```

Steps omit `command_id`, `timestamp` and `session_id`; the runner fills them in.

### 3.6 Scenario result

```json
{
  "scenario": "excess_power",
  "session_id": "sess_excess_power",
  "passed": true,
  "results": [
    {"step": 1, "expect": "ALLOW", "expect_rule": "ok", "passed": true,
     "decision": { "...decision dict...": "" }}
  ]
}
```

---

## 4. Required scenario names (Role 2 delivers all; first 3 are MUST)

| Name | Priority | Session ID | What it proves |
|---|---|---|---|
| `normal_session` | MUST | `sess_normal` | CONNECT → AUTHORIZE_SESSION → START_CHARGING → SET_POWER 5 kW → all ALLOW |
| `excess_power` | MUST | `sess_excess_power` | reach CHARGING, SET_POWER 20 kW → BLOCK `policy.power_limit` |
| `invalid_state` | MUST | `sess_invalid_state` | fresh session, START_CHARGING → BLOCK `state.invalid_transition` |
| `excess_current` | SHOULD | `sess_excess_current` | CHARGING, SET_CURRENT 16 A ALLOW, SET_CURRENT 40 A BLOCK `policy.current_limit` |
| `invalid_token` | SHOULD | `sess_invalid_token` | CONNECT with token `bad-token` → BLOCK `auth.invalid_token` |
| `unauthorized_role` | SHOULD | `sess_unauthorized` | `monitor_01` (valid token) sends CONNECT → BLOCK `authz.command_not_permitted` |
| `rate_burst` | SHOULD | `sess_rate_burst` | 3 setup commands + 12 × SET_POWER 5 kW → steps 1–10 ALLOW, steps 11–15 BLOCK `sequence.rate_exceeded` |
| `full_lifecycle` | SHOULD | `sess_lifecycle` | CONNECT → AUTHORIZE → START → SET_POWER 7 (at limit, ALLOW) → STOP → DISCONNECT all ALLOW, then DISCONNECT again → BLOCK `state.invalid_transition` |

**Rate rule (important):** the window counts every command for the same `(source_id, session_id)` that passed authentication, whether allowed or blocked. Creating/resetting a session clears its window. Each scenario uses its own session, so running scenarios back-to-back never triggers false rate blocks.

---

## 5. Function signatures (Python)

### Role 1 — `core/decision.py`

```python
class Gateway:
    def __init__(self, db_path: str = "evguard.db"): ...
    def create_session(self, session_def: dict) -> dict:
        """Create or reset a session to DISCONNECTED; clears its rate window. Returns session dict (§3.3)."""
    def handle(self, command: dict) -> dict:
        """Evaluate one command. NEVER raises. Returns decision dict (§3.2). Applies to physical sim only on ALLOW."""
    def get_session(self, session_id: str) -> dict | None: ...
    def recent_decisions(self, limit: int = 50) -> list[dict]:  # newest first
    def stats(self) -> dict:  # {"total": int, "allowed": int, "blocked": int}
```

### Role 2 — `simulator/ev_simulator.py`

```python
class ChargerSimulator:
    """Dumb execution layer. Applies whatever it is given. Does NO security checks."""
    def ensure_session(self, session_id: str, vehicle_id: str) -> dict: ...  # returns snapshot
    def reset_session(self, session_id: str, vehicle_id: str) -> dict: ...
    def apply(self, command: dict) -> dict: ...                        # returns snapshot (§3.3 physical)
    def snapshot(self, session_id: str) -> dict | None: ...
```

### Role 2 — `simulator/scenarios.py`

```python
def make_command(session_id: str, source_id: str, auth_token: str,
                 command_type: str, value: float | None = None,
                 unit: str | None = None) -> dict: ...
def list_scenarios() -> list[dict]:   # [{"name","title","description"}]
def load_scenario(name: str) -> dict: # raises ValueError for unknown name
def run_scenario(name: str, send, create_session) -> dict:
    """send(command_dict) -> decision_dict; create_session(session_def) -> any. Returns §3.6."""
```

### Role 2 — `simulator/baseline.py`

```python
def baseline_apply(command: dict) -> dict:
    """Unprotected path: applies command to a SEPARATE ChargerSimulator. Returns
    {"mode": "baseline", "accepted": True, "snapshot": {...}}"""
```

### Role 3 — `backend/schemas.py`

```python
from pydantic import BaseModel
class CommandIn(BaseModel):
    """Validates a Command (§3.1). Rules: command_type in COMMANDS; value+unit REQUIRED for
    VALUE_COMMANDS with exactly the unit in VALUE_COMMANDS, and ABSENT (None) for other commands;
    value finite and > 0; command_id/session_id/source_id match ^[A-Za-z0-9_-]{1,64}$;
    auth_token max 128 chars; timestamp optional string max 40 chars."""
    def to_command(self) -> dict: ...  # returns a dict with exactly COMMAND_KEYS
```

Role 1 uses it as `@app.post("/command") def post_command(cmd: CommandIn): return gateway.handle(cmd.to_command())`. FastAPI turns validation failures into HTTP 422 automatically.

### Role 3 — `dashboard/api_client.py`

Functions with the same names as the endpoints in §6 (`health()`, `get_decisions()`, `get_session(id)`, `get_stats()`, `list_scenarios()`, `run_scenario(name)`, `send_command(cmd)`, `baseline_command(cmd)`). With environment variable `EVGUARD_MOCK=1` they return data from `dashboard/mock_data/*.json` instead of calling the API.

---

## 6. HTTP API (Role 1 builds, Role 3 consumes)

Base URL: `http://127.0.0.1:8000` (override with env var `EVGUARD_API_URL`).

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/health` | — | `{"status": "ok", "contract_version": "1.1"}` |
| POST | `/command` | Command §3.1 | Decision §3.2 (HTTP 422 if the schema rejects it) |
| GET | `/commands?limit=50` | — | `{"items": [Decision, ...]}` newest first, limit ≤ 200 |
| GET | `/commands/{command_id}` | — | Decision or 404 |
| GET | `/sessions/{session_id}` | — | Session §3.3 or 404 |
| POST | `/sessions` | Session definition §3.4 | Session §3.3 (creates or resets) |
| GET | `/stats` | — | `{"total", "allowed", "blocked"}` |
| GET | `/scenarios` | — | `{"items": [{"name","title","description"}]}` |
| POST | `/scenarios/{name}` | — | Scenario result §3.6 (404 unknown name) |
| POST | `/baseline/command` | Command §3.1 | `{"mode":"baseline","accepted":true,"snapshot":{...}}` |

All malformed commands are rejected with HTTP 422 at the API layer by the final `backend/schemas.py` and never reach the engine: missing fields, wrong JSON types (strings and booleans are not accepted as `value`), `value`/`unit` pairing, unit mismatch, non-finite or non-positive `value`, unknown `command_type`, ID patterns, and over-length `auth_token`/`timestamp`. 422 bodies never echo submitted values.

---

## 7. Dependencies (combined `requirements.txt`)

```text
fastapi
uvicorn
pydantic
pyyaml
httpx
pytest
streamlit
requests
```

Nobody adds a new dependency without a CONTRACT REQUEST. At handoff, include the output of `pip freeze` so versions can be matched.

## 8. Test file naming

| Owner | Files |
|---|---|
| Role 1 | `tests/test_core_*.py` |
| Role 2 | `tests/test_sim_*.py` |
| Role 3 | `tests/test_integration_*.py`, `tests/test_api_*.py` (incl. `test_api_schemas.py`), `tests/test_dashboard_*.py` |

## 9. Changelog

- 1.0 — initial contract.
- 1.0a — ownership only: `backend/schemas.py` moved to Role 3. No interface change.
- 1.1 — `RATE_MAX_COMMANDS` 5 → 10 (5 caused false blocks in `full_lifecycle` and the live demo). `rate_burst` is now 3 setup + 12 SET_POWER (1–10 ALLOW, 11–15 BLOCK). Decision fields documented as nullable. The same `command_id` may appear more than once in `/commands`; the duplicate attempt is logged as a BLOCK.
- 1.1a — documentation only (`CONTRACT_VERSION` stays "1.1"): `contract/evguard_contract.py` declared canonical and the two Markdown copies declared read-only mirrors; §6 `/health` example corrected to "1.1"; §6 interim-422 note added; `input.invalid` rule description reworded (text only, no ID or key changes); rate wording aligned everywhere to `RATE_MAX_COMMANDS` = 10 per `RATE_WINDOW_SECONDS` = 10 s.
- 1.1b — final schemas.py landed; malformed commands return HTTP 422
