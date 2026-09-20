# EVGuard — State-Aware Security Gateway for EV Charging Commands

> **Hackathon:** TLN Cybersecurity Challenge 2026  
> **Project Type:** Cybersecurity / Cyber-Physical Systems / EV Charging Security  
> **Build Type:** Software-only MVP running against a simulated EV/charger  
> **Team:** 3 members  
> **Status:** Hackathon prototype — not a production security product

---

## TL;DR (for judges)

- **Problem:** A charging command can come from a valid, authorized controller and still be unsafe or invalid *right now* — e.g. a 20 kW request on a 7 kW session, or `START_CHARGING` with no vehicle connected.
- **Control:** EVGuard is a pre-execution gateway. Every command passes authentication → authorization → session-state check → safety limits → rate check, and is either **ALLOWED** or **BLOCKED** before it reaches the (simulated) charger.
- **Evidence:** Every decision shows a human-readable reason and a rule ID, and is written to an audit log.
- **Honesty:** Everything runs against a simulator. EVGuard does not implement OCPP or ISO 15118 and does not claim state-based EV security is a new idea (see §4).

---

## 1. Project Overview

### The Problem

Electric vehicle (EV) charging infrastructure is a cyber-physical system: digital commands directly influence physical energy transfer.

A charging command can be:

- sent by an authenticated controller,
- issued by an authorized role,
- correctly formatted,

and still be unsafe or invalid for the **current charging-session state**. For example:

- a controller requests `20 kW` when the simulated session limit is `7 kW`;
- `START_CHARGING` is issued while the session is still `DISCONNECTED`;
- commands are repeated at an abnormal rate during a session.

Identity and authorization checks answer **"Who sent this?"** and **"May they send this type of command?"** On their own, they do not establish that the requested action is valid for the current operational context.

### Our Solution

**EVGuard** is a lightweight gateway that sits logically between a charging controller and the charging execution layer (in the MVP, a simulator).

Before a command is executed, EVGuard checks:

1. **Authentication** — Is the sender's token valid, and does it match the claimed sender?
2. **Authorization** — Is the sender's role allowed to issue this command type?
3. **State validity** — Is this command valid in the current charging-session state?
4. **Safety policy** — Is the requested power/current within the session's configured limits?
5. **Sequence/rate** — Is the sender issuing commands faster than the configured threshold?

The result is:

```text
ALLOW
or
BLOCK + human-readable reason + rule ID
```

Every decision is recorded in an audit log.

---

## 2. Core Security Concept

```text
Identity Trust      "Who sent the command?"                  → Authentication
Permission Trust    "Are they allowed to issue it?"          → Authorization
Context Trust       "Is it valid in the current state?"      → State validation
Safety Policy       "Does it violate configured limits?"     → Policy validation
Behaviour           "Is the command rate abnormal?"          → Rate check
                                   │
                            ┌──────┴──────┐
                            ▼             ▼
                          ALLOW         BLOCK
```

The central idea:

> **An authenticated and authorized command is not automatically a safe or valid command.**

EVGuard therefore treats **command validity in context** as a separate enforcement decision from identity and authorization.

### Two different kinds of "authentication"

The design deliberately separates two concepts that are easy to confuse:

| Concept | What it is | How EVGuard models it |
|---|---|---|
| **Sender authentication** | Is the *controller* sending this command who it claims to be? | Checked on **every** command using `auth_token` → rule prefix `auth.*` |
| **Session authorization** | Has the *vehicle/driver* been authorized to charge in this session (conceptually similar to OCPP `Authorize` / ISO 15118 Plug & Charge)? | A **state** of the session (`AUTHORIZED`), reached via the `AUTHORIZE_SESSION` command |

A valid sender token never moves a session into `AUTHORIZED` by itself, and an `AUTHORIZED` session never excuses an invalid token.

---

## 3. Why This Matters

EV charging security research already covers OCPP and charging-protocol security, authentication and authorization, device and firmware integrity, remote attestation, charging-profile/charge manipulation, ML-based intrusion and anomaly detection, and specification/state-based behavior analysis.

EVGuard does **not** claim that state machines, command semantics, or rule-based validation are new cybersecurity concepts.

The MVP focuses on one engineering layer:

> **A lightweight EV charging command enforcement gateway that combines sender authentication, role authorization, charging-session state, safety constraints, and explainable pre-execution ALLOW/BLOCK decisions.**

It is a **complementary layer**, not a replacement for OCPP security, ISO 15118 security, device attestation, or intrusion detection.

---

## 4. Literature-Informed Positioning

### EV charging is a cyber-physical security problem

Surveys document vulnerabilities across EV chargers, communication interfaces, backend management systems and related infrastructure, with both digital and physical consequences [1–4].

### Protocol security matters but does not answer every question

OCPP has evolved to include security profiles, smart charging and device management. **OCPP 2.1** was released by the Open Charge Alliance in January 2025; it extends OCPP 2.0.1 (which remains supported) and adds, among other things, ISO 15118-20 support and bidirectional/V2X charging. *(OCPP 2.1 was the latest OCA release when this README was written — re-check before submission.)*

### Device integrity is a distinct question

Porter et al. [5] extend ISO 15118-20 with remote attestation so that charger firmware integrity can be verified:

> *"Can I trust the software running on this device?"*

EVGuard addresses a different runtime question:

> *"Should this particular command be allowed under the current session state and policy?"*

These controls are complementary.

### Charge manipulation and anomaly detection already exist

Prior work studies charge-manipulation attacks and detects them with ML/deep learning [6], and detects anomalies in charging sessions and EVSE traffic [7, 8]. EVGuard does not claim to invent malicious-command detection. Its MVP uses **deterministic rules with human-readable reasons** for the core decision instead of an ML anomaly score.

### State/specification-based EVSE security already exists

Park et al. (published 3 June 2026) [9] apply specification-based intrusion detection to EVSE: normal charger behavior is expressed as behavior rules (verified with UPPAAL), and deviations are classified as misbehavior.

Consequences for EVGuard's positioning:

- **State/specification-based EV charging security is established.**
- EVGuard's prototype contribution is an **engineering one**: an inline, API-driven gateway that applies authentication → authorization → state → safety → rate checks **before** a command executes, and explains every decision.

### General CPS literature supports the concept

SCADA/ICS research has long studied state-based intrusion detection [10], semantic analysis of control commands [11], and pre-execution safety verification of controller code [12]. Pre-execution enforcement is therefore also not new in general; EVGuard applies it to a simplified EV charging command path.

---

## 5. Relationship to Existing Approaches

| Approach | Main question | Typical role | EVGuard relationship |
|---|---|---|---|
| Authentication | Who sent this? | Identity | Included (simulated) |
| Authorization | Are they permitted? | Access control | Included (simulated) |
| Remote attestation | Is the device/software trustworthy? | Device integrity | Complementary |
| Protocol security (OCPP / ISO 15118) | Is communication protected? | Secure transport / messaging | Complementary |
| ML / anomaly IDS | Does behavior look abnormal? | Detection | Complementary |
| Specification / state-based IDS | Does behavior violate a specification? | Detection / monitoring | Closely related |
| Pre-execution safety verification | Is execution physically safe? | Enforcement / verification | Closely related |
| **EVGuard** | **Should this command execute right now?** | **Inline runtime enforcement** | **Core focus** |

---

## 6. System Architecture

```text
            COMMAND SOURCE (simulator / API client)
                          │  POST /command
                          ▼
               ┌──────────────────────┐
               │ Input validation     │  Pydantic schema (HTTP 422 if malformed)
               └──────────┬───────────┘
                          ▼
               ┌──────────────────────┐
               │ Authentication       │  token → identity, identity == source_id
               └──────────┬───────────┘
                          ▼
               ┌──────────────────────┐
               │ Authorization        │  role → allowed command types
               └──────────┬───────────┘
                          ▼
               ┌──────────────────────┐
               │ Session lookup       │  unknown session → BLOCK
               └──────────┬───────────┘
                          ▼
               ┌──────────────────────┐
               │ State engine (FSM)   │  command valid in current state?
               └──────────┬───────────┘
                          ▼
               ┌──────────────────────┐
               │ Safety policy        │  kW vs max_power_kw, A vs max_current_a
               └──────────┬───────────┘
                          ▼
               ┌──────────────────────┐
               │ Rate check           │  commands per sender per window
               └──────────┬───────────┘
                          ▼
               ┌──────────────────────┐
               │ Decision             │  first failed check wins
               └──────────┬───────────┘
                 ALLOW ───┴─── BLOCK
                   │              │
         apply to simulator   do not apply
                   └──────┬───────┘
                          ▼
                  SQLite audit log
                          │
             FastAPI read endpoints
                          │
                 Streamlit dashboard
```

The dashboard reads data only through the FastAPI endpoints; it does not bypass the gateway to change session state.

---

## 7. Charging Session State Model

### States

| State | Meaning |
|---|---|
| `DISCONNECTED` | No vehicle connected |
| `CONNECTED` | Vehicle plugged in, not yet authorized to charge |
| `AUTHORIZED` | Vehicle/driver authorized for this session; not yet charging |
| `CHARGING` | Energy transfer in progress (simulated) |
| `STOPPED` | Charging ended; vehicle still connected |

### Transition table (complete)

Any command **not** listed for the current state is blocked with `state.invalid_transition`.

| Current state | Command | Next state |
|---|---|---|
| `DISCONNECTED` | `CONNECT` | `CONNECTED` |
| `CONNECTED` | `AUTHORIZE_SESSION` | `AUTHORIZED` |
| `CONNECTED` | `DISCONNECT` | `DISCONNECTED` |
| `AUTHORIZED` | `START_CHARGING` | `CHARGING` |
| `AUTHORIZED` | `DISCONNECT` | `DISCONNECTED` |
| `CHARGING` | `SET_POWER` | `CHARGING` |
| `CHARGING` | `SET_CURRENT` | `CHARGING` |
| `CHARGING` | `STOP_CHARGING` | `STOPPED` |
| `STOPPED` | `DISCONNECT` | `DISCONNECTED` |

```text
DISCONNECTED ──CONNECT──► CONNECTED ──AUTHORIZE_SESSION──► AUTHORIZED ──START_CHARGING──► CHARGING
      ▲                       │                               │                         │  ▲
      │                   DISCONNECT                      DISCONNECT          SET_POWER / SET_CURRENT
      ├───────────────────────┘                               │                         │  │
      ├───────────────────────────────────────────────────────┘                         └──┘
      │                                                                          STOP_CHARGING
      └─────────────────────DISCONNECT──────────────── STOPPED ◄────────────────────────┘
```

Design notes:

- `DISCONNECT` while `CHARGING` is **blocked**: charging must be stopped first. (A real charger must also handle physical unplugging; the MVP only models commanded transitions.)
- A new charging session after `STOPPED` goes through `DISCONNECT` → `CONNECT` → `AUTHORIZE_SESSION` again.
- The transition table is defined explicitly in code (one dictionary), not inferred.

---

## 8. Security Decision Pipeline

```text
 1. Receive JSON command
 2. Validate schema (types, ranges, unit/command match)   → HTTP 422 if invalid; nothing executed
 3. Authenticate token and check it matches source_id     → auth.*
 4. Authorize role for command_type                       → authz.*
 5. Look up session                                       → session.unknown
 6. Validate state transition                             → state.invalid_transition
 7. Validate power/current against session limits         → policy.*
 8. Validate command rate for this sender                 → sequence.rate_exceeded
 9. Decide: first failed check → BLOCK, otherwise ALLOW
10. Apply state change / setpoint to simulator only if ALLOW
11. Write audit record (ALLOW and BLOCK)
```

Rules for the pipeline:

- **Short-circuit:** the first failing check determines the rule ID shown to the user.
- **Server time:** EVGuard records its own receive time (`received_at`) and uses it for the rate window. The client-supplied `timestamp` is stored for reference but never trusted for security decisions.
- **Rate counting:** every command that passes authentication counts toward its sender's window, whether it is later allowed or blocked, so a flood of invalid commands is still detected.
- **Duplicate IDs:** a `command_id` that was already processed is blocked (`sequence.duplicate_command_id`) — a simple replay guard.

### Fail-closed principle

If any check raises an unexpected exception, or configuration/session data is missing, EVGuard returns:

```text
BLOCK   rule: engine.internal_error
```

and logs the event. Nothing is applied to the simulator unless the decision is an explicit ALLOW.

---

## 9. Example Command

```json
{
  "command_id": "cmd_00123",
  "timestamp": "2026-09-19T10:00:03Z",
  "session_id": "session_001",
  "source_id": "controller_A",
  "auth_token": "sim_token_controller_A",
  "command_type": "SET_POWER",
  "value": 20.0,
  "unit": "kW"
}
```

Validation rules:

| Field | Rule |
|---|---|
| `command_type` | One of the seven supported commands |
| `value`, `unit` | **Required** for `SET_POWER` (`unit` must be `kW`) and `SET_CURRENT` (`unit` must be `A`); **must be absent** for all other commands |
| `value` | Finite number, `> 0` (no NaN/infinity, no negatives) |
| string fields | Length-limited; `command_id`, `session_id`, `source_id` restricted to `[A-Za-z0-9_-]` |

---

## 10. Example Decision

```json
{
  "command_id": "cmd_00123",
  "decision": "BLOCK",
  "reason": "Requested power 20.0 kW exceeds session maximum of 7.0 kW",
  "rule_triggered": "policy.power_limit",
  "state_before": "CHARGING",
  "state_after": "CHARGING",
  "received_at": "2026-09-19T10:00:03.412Z"
}
```

For a BLOCK, `state_after` always equals `state_before`.

---

## 11. Command Types and Power/Current Handling

| Command | Value | Valid in state |
|---|---|---|
| `CONNECT` | — | `DISCONNECTED` |
| `AUTHORIZE_SESSION` | — | `CONNECTED` |
| `START_CHARGING` | — | `AUTHORIZED` |
| `SET_POWER` | kW | `CHARGING` |
| `SET_CURRENT` | A | `CHARGING` |
| `STOP_CHARGING` | — | `CHARGING` |
| `DISCONNECT` | — | `CONNECTED`, `AUTHORIZED`, `STOPPED` |

Power and current are independent policies and are **never compared against each other**:

```text
SET_POWER    value (kW) → compared with max_power_kw   → policy.power_limit
SET_CURRENT  value (A)  → compared with max_current_a  → policy.current_limit
```

A value **equal** to the limit is allowed; only values strictly greater are blocked. The MVP does not convert between current and power (that would require voltage and phase information that the simulation does not model).

---

## 12. Threat / Attack Scenarios

All scenarios run against the simulator.

### Attack 1 — Excessive charging power (core)

```text
State = CHARGING, max = 7 kW
SET_POWER 5 kW   → ALLOW
SET_POWER 20 kW  → BLOCK   rule: policy.power_limit
```

The sender is authenticated and authorized; the value is unsafe for this session.

### Attack 2 — Invalid-state command (core)

```text
State = DISCONNECTED
START_CHARGING   → BLOCK   rule: state.invalid_transition
```

The sender is authenticated and authorized; the command is inconsistent with the session state.

### Attack 3 — Abnormal command rate

```text
Policy: max 10 commands per source+session per 10 s
3 setup commands + 12 rapid SET_POWER 5 kW commands
→ steps 1–10 ALLOW, steps 11–15 BLOCK   rule: sequence.rate_exceeded
```

Thresholds are demo values, not EV industry limits.

### Attack 4 — Invalid credential

```text
auth_token = unknown / expired / belongs to another source_id
→ BLOCK   rule: auth.invalid_token  (or auth.source_mismatch)
```

### Attack 5 — Unauthorized command type

```text
source_id = monitor_01 (role: monitor), command = SET_POWER
→ BLOCK   rule: authz.command_not_permitted
```

---

## 13. Rule ID Catalog

| Rule ID | Meaning |
|---|---|
| `auth.missing_token` | No token supplied |
| `auth.invalid_token` | Token unknown or expired |
| `auth.source_mismatch` | Token belongs to a different `source_id` |
| `authz.command_not_permitted` | Sender's role may not issue this command type |
| `session.unknown` | `session_id` does not exist |
| `state.invalid_transition` | Command not valid in the current state |
| `policy.power_limit` | Requested kW > `max_power_kw` |
| `policy.current_limit` | Requested A > `max_current_a` |
| `sequence.rate_exceeded` | Sender exceeded commands-per-window threshold |
| `sequence.duplicate_command_id` | `command_id` already processed |
| `engine.internal_error` | Unexpected error — fail closed |
| `ok` | All checks passed (ALLOW) |

Schema-invalid requests are rejected by FastAPI with HTTP 422 before reaching the engine and are not executed.

> All malformed commands (missing fields, wrong types, value/unit pairing, non-finite or non-positive values, unknown `command_type`, ID patterns) return HTTP 422 from the final `backend/schemas.py`. See CONTRACT §6.

---

## 14. Baseline vs EVGuard Demonstration

| | Baseline simulated controller | EVGuard-protected simulated controller |
|---|---|---|
| Path | Command → simulator | Command → EVGuard checks → simulator only if ALLOW |
| `SET_POWER 20 kW` on 7 kW session | Simulator applies 20 kW setpoint | BLOCK, setpoint unchanged |

The baseline runs on its **own separate simulated session**, so it cannot change the protected session's state or audit log.

This comparison shows what our *baseline simulator* does without the gateway. It is **not** a claim about how any real EV charger, OCPP implementation or ISO 15118 stack would behave — many real systems enforce their own limits.

---

## 15. Dashboard

Designed so a judge can understand a decision without reading code.

**Latest decision card (largest element)** — big green **ALLOW** or red **BLOCK**, the reason in one sentence, and the rule ID.

```text
┌────────────────────────────────────────────────────┐
│  ⛔ BLOCK                                           │
│  SET_POWER 20.0 kW  (session max 7.0 kW)            │
│  State: CHARGING → CHARGING                         │
│  Rule: policy.power_limit                           │
│  Requested charging power exceeds the configured    │
│  maximum for this session.                          │
└────────────────────────────────────────────────────┘
```

**Session state** — current state, session/vehicle ID, current setpoint, max power, max current.

**Live security feed** — table of recent commands: time, command, value, decision, rule.

**Statistics** — total / allowed / blocked counts.

**Demo buttons** — Normal Session · Excess Power · Invalid State · Rate Burst · Invalid Token · Unauthorized Role · Baseline Comparison.

---

## 16. Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Backend | Python + FastAPI (Pydantic) | API and input validation |
| Security engine | Pure Python | Auth, authz, state, policy, rate logic |
| Simulation | Python | Simulated EV / charger / session |
| Database | SQLite (`sqlite3`, parameterized queries) | Audit trail and session records |
| Configuration | YAML via `yaml.safe_load` | Limits, roles, demo tokens |
| Dashboard | Streamlit | Demo interface |
| Testing | pytest | Unit and API tests |
| Version control | Git + GitHub | Collaboration |

Everything runs locally; no charging hardware is required.

---

## 17. Quick Start

```bash
git clone <repo-url> && cd evguard
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Terminal 1 — API (bound to localhost only)
uvicorn backend.main:app --host 127.0.0.1 --port 8000

# Terminal 2 — dashboard
streamlit run dashboard/app.py

# Tests
pytest -q
```

---

## 18. Repository Structure

```text
evguard/
├── backend/
│   ├── main.py              # FastAPI app, startup config validation
│   ├── api_routes.py
│   └── schemas.py           # Pydantic request/response models
├── core/
│   ├── auth.py
│   ├── authz.py
│   ├── state_engine.py      # explicit transition table
│   ├── policy_engine.py
│   ├── sequence_check.py
│   └── decision.py          # pipeline + fail-closed wrapper
├── simulator/
│   ├── ev_simulator.py
│   ├── baseline.py          # unprotected baseline controller
│   └── scenarios.py         # fixed, named demo scenarios
├── database/
│   ├── db.py
│   └── schema.sql
├── dashboard/
│   └── app.py
├── config/
│   └── policy_rules.yaml
├── tests/
│   ├── test_state_engine.py
│   ├── test_policy_engine.py
│   ├── test_sequence_check.py
│   └── test_api.py
├── requirements.txt
└── README.md
```

---

## 19. Database Design

### `command_log`

| Column | Type | Description |
|---|---|---|
| id | INTEGER PRIMARY KEY | Row ID |
| command_id | TEXT UNIQUE | Command identifier (duplicates blocked before insert) |
| received_at | TEXT | Server receive time (ISO 8601, UTC) — used for rate checks |
| client_timestamp | TEXT | Timestamp claimed by the client (informational only) |
| session_id | TEXT | Charging session |
| source_id | TEXT | Claimed sender |
| role | TEXT | Role resolved from token (NULL if authentication failed) |
| command_type | TEXT | Command |
| value | REAL | kW or A when applicable, else NULL |
| unit | TEXT | `kW` / `A` / NULL |
| decision | TEXT | `ALLOW` / `BLOCK` |
| reason | TEXT | Human-readable explanation |
| rule_triggered | TEXT | Rule ID (§13) |
| state_before | TEXT | State before the command |
| state_after | TEXT | State after the command (= before on BLOCK) |

Tokens are **never** written to the database or logs.

### `sessions`

| Column | Type | Description |
|---|---|---|
| session_id | TEXT PRIMARY KEY | Session identifier |
| vehicle_id | TEXT | Simulated vehicle |
| max_power_kw | REAL | Session power limit |
| max_current_a | REAL | Session current limit |
| current_state | TEXT | Current FSM state |
| current_power_kw | REAL | Last allowed power setpoint |
| current_current_a | REAL | Last allowed current setpoint |
| created_at | TEXT | Creation time |
| updated_at | TEXT | Last state change |

Demo sessions are seeded at startup (e.g. `session_001`, `Vehicle-01`, 7 kW, 32 A).

---

## 20. API

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Service health |
| `/command` | POST | Submit one command through EVGuard |
| `/commands` | GET | Recent decisions (paginated, `limit` capped) |
| `/commands/{command_id}` | GET | One decision |
| `/sessions/{session_id}` | GET | Current session state and limits |
| `/scenarios/{name}` | POST | Run a named demo scenario (fixed allow-list only) |
| `/baseline/command` | POST | Send a command to the unprotected baseline simulator |

Prototype note: read endpoints are unauthenticated and the API binds to `127.0.0.1`. That is acceptable only for a local demo.

---

## 21. Policy Configuration

```yaml
defaults:
  max_power_kw: 7.0
  max_current_a: 32.0

sequence:
  window_seconds: 10
  max_commands_per_source: 10

roles:
  controller:
    - CONNECT
    - AUTHORIZE_SESSION
    - START_CHARGING
    - SET_POWER
    - SET_CURRENT
    - STOP_CHARGING
    - DISCONNECT
  monitor: []            # read-only: may use GET endpoints, may not send commands

# Demo-only identities. Real deployments would use PKI / hardware-backed credentials.
sources:
  controller_A: { role: controller, token_env: EVGUARD_TOKEN_CONTROLLER_A }
  monitor_01:   { role: monitor,    token_env: EVGUARD_TOKEN_MONITOR_01 }
```

- Loaded with `yaml.safe_load` and validated at startup (positive limits, known roles, known command names). **Invalid config → the service refuses to start** rather than running with a partial policy.
- Demo tokens are read from environment variables / a git-ignored `.env`, not committed.
- 7 kW and 32 A are **illustrative demo values** (roughly a single-phase AC home charger), not universal EV specifications.

---

## 22. Testing Plan

Only **actually executed** test results will be shown in the presentation.

| Scenario | Expected |
|---|---|
| `SET_POWER 5` while CHARGING, max 7 kW | ALLOW |
| `SET_POWER 7` (exactly at limit) | ALLOW |
| `SET_POWER 20` while CHARGING, max 7 kW | BLOCK `policy.power_limit` |
| `SET_CURRENT 40` A, max 32 A | BLOCK `policy.current_limit` |
| `SET_CURRENT 16` A, max 32 A (must not be compared with kW) | ALLOW |
| `START_CHARGING` while DISCONNECTED | BLOCK `state.invalid_transition` |
| `DISCONNECT` while CHARGING | BLOCK `state.invalid_transition` |
| Full normal lifecycle CONNECT → … → DISCONNECT | all ALLOW |
| Invalid token | BLOCK `auth.invalid_token` |
| Valid token, wrong `source_id` | BLOCK `auth.source_mismatch` |
| Monitor role sends `SET_POWER` | BLOCK `authz.command_not_permitted` |
| Unknown session | BLOCK `session.unknown` |
| `SET_POWER` missing value / negative / wrong unit | HTTP 422 with the final schema (temporary schema: HTTP 200 BLOCK `input.invalid`) |
| `CONNECT` with a value | HTTP 422 with the final schema (temporary schema: HTTP 200 BLOCK `input.invalid`) |
| 15 commands in 10 s from one source+session (limit 10) | 11th onward BLOCK `sequence.rate_exceeded` |
| Reused `command_id` | BLOCK `sequence.duplicate_command_id` |
| Engine exception (injected in test) | BLOCK `engine.internal_error`, simulator unchanged |
| Any BLOCK | simulator state and setpoint unchanged |
| Invalid YAML config | service fails to start |

---

## 23. Security of EVGuard Itself

| Area | Prototype (this MVP) | Production would need |
|---|---|---|
| Sender authentication | Static demo tokens from env vars, constant-time comparison | Mutual TLS / PKI, hardware-backed keys, rotation, expiry |
| Authorization | Role → command allow-list in YAML | Centrally managed, audited policy |
| Input handling | Pydantic schemas, strict types/ranges, length limits | Same, plus protocol-level validation (OCPP/ISO 15118 messages) |
| Decision safety | Fail-closed wrapper; apply only on explicit ALLOW | Same, plus independent safety interlocks in the charger |
| Configuration | `yaml.safe_load`, validated at startup, no secrets in repo | Signed, versioned configuration |
| Database | Parameterized SQL only | Tamper-evident / append-only audit storage |
| Logging | No tokens or secrets logged | SIEM integration, retention policy |
| Exposure | Bound to `127.0.0.1`; read endpoints unauthenticated | Authenticated, rate-limited, network-segmented API |
| Code | No `eval`/`exec`/`pickle` on external input; scenarios chosen from a fixed list | Code review, SAST, dependency scanning |
| State source | Trusts the simulator's state | Trusted, integrity-protected telemetry |

EVGuard's own security is **prototype-grade**. It demonstrates the enforcement concept; it is not hardened for deployment.

---

## 24. MVP Scope

### MUST HAVE (the demo depends on these)

- Session state machine with the explicit transition table
- Sender authentication + role authorization (simulated)
- Power-limit and current-limit enforcement (separate units)
- State-validity enforcement
- Fail-closed decision wrapper
- `POST /command` + SQLite audit log
- Streamlit dashboard: decision card, session state, feed
- Scenarios: normal session, excess power, invalid state
- pytest for state engine and policy engine

### SHOULD HAVE

- Rate check
- Invalid-token and unauthorized-role scenarios
- Duplicate `command_id` guard
- Baseline comparison
- Allow/block statistics

### ONLY IF TIME REMAINS

- Charts (Plotly)
- CSV export of the audit log
- Deployment to Replit for a shareable link

### DELIBERATELY OUT OF SCOPE

ML models, real OCPP/ISO 15118 message handling, real hardware, blockchain, cloud infrastructure, editable policies from the dashboard, NetworkX graphs.

---

## 25. Demo Script (target ≈ 4 minutes; video must be under 5)

| Time | Step | What judges see |
|---|---|---|
| 0:00–0:30 | Problem in one sentence + architecture diagram | "Authenticated ≠ safe" |
| 0:30–1:10 | **Normal session:** CONNECT → AUTHORIZE_SESSION → START_CHARGING → SET_POWER 5 kW | Four green ALLOWs |
| 1:10–1:50 | **Unsafe command:** SET_POWER 20 kW from the same valid controller | Red BLOCK, `policy.power_limit`, "20 kW > 7 kW" |
| 1:50–2:30 | **Invalid state:** STOP_CHARGING → DISCONNECT, then START_CHARGING | BLOCK, `state.invalid_transition` |
| 2:30–3:00 | **Rate burst** (optional) | First 10 commands ALLOW (3 setup + 7 × SET_POWER), rest BLOCK `sequence.rate_exceeded` |
| 3:00–3:30 | **Baseline comparison:** same 20 kW command to baseline simulator | Baseline applies 20 kW; EVGuard blocked it |
| 3:30–4:00 | **Audit log** | time, command, decision, rule, reason, state before/after |

Rehearse with the scripted scenario buttons; do not type commands live.

One-sentence pitch:

> **"EVGuard is a gateway that stops authenticated, authorized EV charging commands from executing when they are invalid for the current charging state or exceed safety limits — and explains why."**

---

## 26. Limitations

- **Simulated environment** — no physical EVSE or vehicle.
- **Simulated authentication** — static demo tokens, not PKI or hardware credentials.
- **Illustrative thresholds** — power/current/rate limits are demo values.
- **No protocol implementation** — no OCPP or ISO 15118 interoperability is claimed; command names are simplified abstractions.
- **Trust in state** — if the state data EVGuard relies on were compromised, decisions would be made against a false baseline. Production would need trusted telemetry.
- **Simple rate check** — fixed window per sender, not a calibrated anomaly model; a slow, low-rate attacker would not trigger it.
- **Single process** — in-memory rate counters and a local SQLite file; not designed for concurrency or scale.
- **Gateway bypass** — EVGuard only protects commands routed through it; an attacker with direct access to the execution layer is out of scope.

---

## 27. Future Scope

1. Ingest real OCPP 2.0.1 / 2.1 messages (e.g. mapping `SetChargingProfile` to power/current policy)
2. ISO 15118-20 message awareness
3. Trusted charger/vehicle telemetry as the state source
4. Hardware-backed / PKI authentication
5. Signed, versioned policy configuration
6. Formal verification of the transition table and rules
7. ML-assisted detection **alongside** deterministic enforcement
8. SIEM/SOC integration
9. Bidirectional (V2X) policies
10. Limits calibrated from real EVSE and vehicle capabilities

---

## 28. What EVGuard Does NOT Claim

- It does **not** replace OCPP or ISO 15118 security.
- It does **not** provide production-grade authentication.
- It does **not** protect against every EV charging attack.
- It does **not** claim state-machine, specification-based or pre-execution validation is new.
- It does **not** claim its thresholds are real-world universal values.
- It does **not** claim the baseline simulator represents real charging controllers.
- It does **not** use ML for its core decisions.

---

## 29. Positioning Statement

> **EVGuard is an application-focused prototype of a lightweight, inline enforcement gateway for EV charging commands. It combines sender authentication, role authorization, explicit charging-session state validation, safety limits and rate checks in one pre-execution pipeline, and explains every ALLOW/BLOCK decision.**

Architectural framing (not a novelty claim):

> Authentication and attestation establish trust in identities and devices; IDS/ML and specification-based monitors detect abnormal or non-compliant behavior. EVGuard is designed as an **enforcement point** that decides whether a single command may execute. Policy enforcement points and pre-execution safety checks are established ideas; EVGuard applies them to a simplified EV charging command path.

---

## 30. Alignment with TLN Cybersecurity Challenge 2026

Criteria as listed in the challenge brief; confirm against the official rules before submission.

| Criterion | How EVGuard addresses it |
|---|---|
| **Impact & Relevance** | EV chargers are networked cyber-physical devices; unsafe or out-of-sequence commands can affect vehicles and energy delivery. Target users: charging operators, security teams, researchers, students. |
| **Technical Implementation** | Working FastAPI gateway, explicit FSM, unit-safe policy engine, fail-closed design, SQLite audit trail, pytest suite. |
| **Innovation & Creativity** | Integrates identity, permission, state, safety and rate checks into one explainable pre-execution decision — an engineering integration, positioned honestly against prior work (§4). |
| **User Experience & Design** | One large ALLOW/BLOCK card with a plain-English reason and rule ID; one-click scenarios. |
| **Presentation & Demo** | ~4-minute scripted demo (§25) within the under-5-minute video limit. |

Cybersecurity relevance: EVGuard enforces authentication, authorization, input validation and policy on a control path, and produces an audit trail.

---

## 31. AI / External Tools Disclosure

The hackathon requires disclosure of significant AI/external-tool use. This project uses:

| Tool | Used for |
|---|---|
| Replit | Development, execution, optional hosting |
| Claude (Claude Code / Claude chat) | Coding assistance, refactoring, debugging, test generation, README review |
| Gemini / Antigravity | Architecture discussion, code assistance, UI iteration, debugging |

*(Update this table to reflect actual usage at submission time.)*

The team remains responsible for understanding the code, validating generated output, running the tests, making final design decisions and explaining the security model to judges. No AI-generated output is presented as a tested result unless it was actually executed and verified.

---

## 32. References

**Verified during this revision**

1. J. Johnson, T. Berg, B. Anderson, B. Wright (2022). "Review of Electric Vehicle Charger Cybersecurity Vulnerabilities, Potential Impacts, and Defenses." *Energies*, 15(11), 3931.
5. R. Porter, M. Biglari-Abhari, B. Tan, D. Thrimawithana (2025). "Enhancing Security in the ISO 15118-20 EV Charging System." *Green Energy and Intelligent Transportation*, 4(6), 100262. https://doi.org/10.1016/j.geits.2025.100262
6. "Charge Manipulation Attacks Against Smart Electric Vehicle Charging Stations and Deep Learning-Based Detection Mechanisms." *IEEE Transactions on Smart Grid*, 15(5), 5182–5194, 2024. (arXiv:2310.12254)
7. D. Kern, C. Krauß, M. Hollick (2023). "Detection of Anomalies in Electric Vehicle Charging Sessions." *ACSAC '23*, 298–309. https://doi.org/10.1145/3627106.3627127
9. H. Park, V. Abella, J. Kim, S. Ju, I. You (2026). "SMDEVC: Specification-Based Misbehavior Detection for Electric Vehicle Charging Stations." *Applied Sciences*, 16(11), 5605 (published 3 June 2026). https://doi.org/10.3390/app16115605

**Well-known works — confirm exact bibliographic details before submission**

2. Garofalaki et al. (2022). "Electric Vehicle Charging: A Survey on the Security Issues and Challenges of the Open Charge Point Protocol (OCPP)."
3. Alcaraz, Cumplido & Triviño (2023). "OCPP in the spotlight: threats and countermeasures for electric vehicle charging infrastructures 4.0." *International Journal of Information Security*.
4. Plaka, Asplund & Nadjm-Tehrani (2024). "Vulnerability Analysis of an Electric Vehicle Charging Ecosystem."
8. Yang, Cai & Wu (2026). "An intrusion detection model for electric vehicle supply equipment based on multi-task learning and probability transfer mechanism." *Scientific Reports*.
10. Carcano et al. (2009). "State-Based Network Intrusion Detection Systems for SCADA Protocols: A Proof of Concept."
11. Lin et al. (2013). "Semantic Security Analysis of SCADA Networks to Detect Malicious Control Commands in Power Grids."
12. McLaughlin et al. (2014). "A Trusted Safety Verifier for Process Controller Code." *NDSS*.

**Standards / industry**

- Open Charge Alliance — OCPP 2.1 (released January 2025; extends OCPP 2.0.1) and OCPP 2.0.1 / 1.6 specifications.
- ISO 15118 family (ISO 15118-2, ISO 15118-20) — vehicle-to-grid communication. Referenced conceptually only; not implemented.

---

## 33. Summary

| | |
|---|---|
| **Project** | EVGuard — State-Aware Security Gateway for EV Charging Commands |
| **Problem** | A charging command can be authenticated and authorized yet unsafe or invalid for the current session |
| **Solution** | Inline gateway: authentication → authorization → state → safety limits → rate → ALLOW/BLOCK |
| **Focus** | Pre-execution enforcement with plain-English reasons, rule IDs and an audit trail |
| **Demo** | Normal → ALLOW · 20 kW → BLOCK · invalid state → BLOCK · rate burst → BLOCK · audit log |
| **Stack** | Python · FastAPI · Streamlit · SQLite · PyYAML · pytest |
| **Scope** | Prototype / simulation only |
| **Next** | Protocol-aware, trusted-state, hardware-backed gateway |
