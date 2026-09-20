# EVGuard — State-Aware Security Gateway for EV Charging Commands

> **Hackathon:** TLN Cybersecurity Challenge 2026  
> **Project Type:** Cybersecurity / Cyber-Physical Systems / EV Charging Security  
> **Build Type:** Software-only MVP running against a simulated EV/charger  
> **Team:** 3 members  
> **Status:** Hackathon prototype — not a production security product
---

## Try it in 3 minutes

**You need:** Python 3.12 (3.11 also works) and Git. Nothing else: the launcher installs the dependencies into a local `.venv`. The first run needs an internet connection for `pip`.

```bash
git clone https://github.com/Gopesh-K/evguard.git
cd evguard
```

Then start everything with one command:

| System | Command |
|---|---|
| Windows (PowerShell) | `.\run.ps1` |
| macOS / Linux | `./run.sh` |

> **Windows tip:** if PowerShell refuses to run the script ("running scripts is disabled on this system"), start it like this instead:
> `powershell -ExecutionPolicy Bypass -File .\run.ps1`

The launcher creates `.venv` if it is missing, installs `requirements.txt`, starts the EVGuard backend on `http://127.0.0.1:8000`, waits until `/health` answers, starts the dashboard on **http://127.0.0.1:8501**, opens it in your default browser, and stops the backend again when you press `Ctrl+C`. If no browser opens, open the URL yourself. The launchers create no files outside the repository folder, apart from pip's normal download cache.

**What you will see:** one self-explaining dashboard page. At the top, a short *What is EVGuard?* panel and a *How to use this dashboard* guide. Below them, scenario cards grouped into *Normal operation* and *Attacks*, a *What just happened* panel after every run, a *Baseline vs EVGuard* comparison, and then live metrics, the latest decision, session health and the full audit trail.

_Screenshots: `docs/screenshots/dashboard-overview.png`, `docs/screenshots/what-just-happened.png`, `docs/screenshots/baseline-vs-evguard.png` (placeholders, to be added)._

**Click this first**

1. In **Normal operation**, press **Run** on *Normal charging session*. All four commands are ALLOWED.
2. In **Attacks**, press **Run** on *Excess power attack*. Read the *What just happened* panel.
3. In *Baseline vs EVGuard*, press **Send 20 kW to both**.
4. Scroll down to the **Audit Trail** to see every recorded decision. Press **Reset demo** to start over.

**What to look for**

- **The 20 kW BLOCK.** The controller is fully authenticated, yet EVGuard blocks `SET_POWER 20 kW` (`policy.power_limit`) because the session is limited to 7 kW.
- **The invalid-state BLOCK.** `START_CHARGING` on a session that was never connected is blocked (`state.invalid_transition`).
- **The baseline comparison.** The same 20 kW command sets an unprotected simulated charger to 20 kW. With EVGuard it is BLOCKED and the charger stays at 5 kW.
- **The audit trail.** Every ALLOW and BLOCK is recorded with its rule ID and a plain-English reason, and can be downloaded as CSV.

### No browser? Run the demo in the terminal

```bash
.venv\Scripts\python demo.py      # Windows
.venv/bin/python demo.py          # macOS / Linux
```

(`.venv` exists once you have run `run.ps1` / `run.sh` once, or created it yourself as shown below.) `demo.py` runs all 8 scenarios through the real gateway in-process (no server needed), prints every step with its decision, rule and reason, ends with the baseline comparison, and exits with code 0 only if everything matched. A sample of its real output (trimmed):

```text
EVGuard demo: every scenario runs through the real gateway, in this process.

=== Normal charging session (normal_session) ===
Normal operation: a legitimate controller connects, authorizes, starts charging and sets a safe 5 kW.
   1. CONNECT                ALLOW ok                           All checks passed  ✔
   2. AUTHORIZE_SESSION      ALLOW ok                           All checks passed  ✔
   3. START_CHARGING         ALLOW ok                           All checks passed  ✔
   4. SET_POWER 5 kW         ALLOW ok                           All checks passed  ✔
  ✔ Matched expectations

...

=== Excess power attack (excess_power) ===
ATTACK: a fully authenticated controller asks the charger for 20 kW on a session limited to 7 kW.
   1. CONNECT                ALLOW ok                           All checks passed  ✔
   2. AUTHORIZE_SESSION      ALLOW ok                           All checks passed  ✔
   3. START_CHARGING         ALLOW ok                           All checks passed  ✔
   4. SET_POWER 20 kW        BLOCK policy.power_limit           Requested power 20.0 kW exceeds session maximum of 7.0 kW  ✔
  ✔ Matched expectations

... (6 more scenarios) ...

=== Baseline vs EVGuard: the same 20 kW command ===
(The baseline is a simulated unprotected controller, not a real charger.)
  Without EVGuard: charger set to 20 kW
  With EVGuard:    BLOCK (policy.power_limit), charger stays at 5 kW

=== Summary ===
8 scenarios, all matched expectations ✔
```

### Prefer to start things yourself?

Run these from the **repository root** (the folder that contains `run.ps1`), with the virtual environment active:

```bash
# one-time setup
python -m venv .venv
.venv\Scripts\activate          # macOS / Linux: source .venv/bin/activate
pip install -r requirements.txt

# terminal 1: the API (localhost only)
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

# terminal 2: the dashboard
python -m streamlit run dashboard/app.py
```

> Always start the dashboard from the repository root with `python -m streamlit run dashboard/app.py`. Do not `cd dashboard` first: Streamlit reads `.streamlit/config.toml` from the folder you start it in, and the launchers and this README use root-relative paths.

**Demo video:** _link coming soon_ (placeholder: `<DEMO-VIDEO-URL>`).

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
            COMMAND SOURCE (scenario runner / API client / dashboard)
                          │  POST /command
                          ▼
               ┌──────────────────────┐
               │ Input validation     │  Pydantic schema, strict types (HTTP 422 if malformed)
               └──────────┬───────────┘
                          ▼
               ┌──────────────────────┐
               │ Duplicate command_id │  replay guard
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
               │ Rate check           │  commands per (source, session) per window
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

The dashboard talks to the FastAPI service only (`dashboard/api_client.py`); it does not import `core/` and cannot change session state except through the API.

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
 3. Engine input check (defence in depth)                 → input.invalid
 4. Reject an already-processed command_id                → sequence.duplicate_command_id
 5. Authenticate token and check it matches source_id     → auth.*
 6. Authorize role for command_type                       → authz.*
 7. Look up session                                       → session.unknown
 8. Validate state transition                             → state.invalid_transition
 9. Validate power/current against session limits         → policy.*
10. Report rate-limit result for this sender + session     → sequence.rate_exceeded
11. Decide: first failed check → BLOCK, otherwise ALLOW
12. Apply state change / setpoint to simulator only if ALLOW
13. Write audit record (ALLOW and BLOCK)
```

Rules for the pipeline:

- **Short-circuit:** the first failing check determines the rule ID shown to the user.
- **Server time:** EVGuard uses its own clock for `received_at` and for the rate window. The client-supplied `timestamp` is stored for reference but never trusted for security decisions.
- **Rate counting:** the window is keyed by `(source_id, session_id)`. Every command that gets past authentication, authorization and session lookup is counted, whether it is later allowed or blocked, so a flood of invalid commands is still detected. Creating or resetting a session clears its window.
- **Duplicate IDs:** a `command_id` that was already processed is blocked (`sequence.duplicate_command_id`), a simple replay guard. The duplicate attempt is logged as its own BLOCK row.
- **Schema errors never reach the engine.** The HTTP layer rejects them with 422 first. The engine's own `input.invalid` check exists for callers that use the `Gateway` directly.

### Fail-closed principle

If any check raises an unexpected exception, or configuration/session data is missing, EVGuard returns:

```text
BLOCK   rule: engine.internal_error
```

and logs the event. Nothing is applied to the simulator unless the decision is an explicit ALLOW.

---

## 9. Example Command and Input Validation

```json
{
  "command_id": "cmd_00123",
  "timestamp": "2026-09-19T10:00:03Z",
  "session_id": "sess_demo",
  "source_id": "controller_A",
  "auth_token": "demo-token-controller-A",
  "command_type": "SET_POWER",
  "value": 20.0,
  "unit": "kW"
}
```

`backend/schemas.py` (the `CommandIn` model) validates every request before the engine sees it:

| Field | Rule |
|---|---|
| `command_type` | One of the seven supported commands |
| `value`, `unit` | **Required** for `SET_POWER` (`unit` must be `kW`) and `SET_CURRENT` (`unit` must be `A`); **must be absent** for all other commands |
| `value` | A real JSON number, finite and `> 0`. Strings and booleans are rejected (`"5"` and `true` are not numbers); NaN and Infinity are rejected |
| `command_id`, `session_id`, `source_id` | 1–64 characters, only `[A-Za-z0-9_-]` |
| `auth_token` | String, at most 128 characters |
| `timestamp` | Optional string, at most 40 characters |
| unknown fields | Rejected |

**Any malformed command returns HTTP 422 and is never executed.** The 422 body lists only the error `type`, `loc` and `msg` for each problem. It never echoes the submitted input, so an `auth_token` in a rejected request is not sent back.

---

## 10. Example Decision

```json
{
  "command_id": "cmd_00123",
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
  "received_at": "2026-09-19T10:00:03.412Z"
}
```

For a BLOCK, `state_after` always equals `state_before`. The decision never contains the token.

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

All eight scenarios ship in `simulator/scenario_data/` and run against the simulator, through the real gateway. Each session uses its own `session_id`, so scenarios never interfere with each other.

| Scenario | What happens | Expected |
|---|---|---|
| `normal_session` | CONNECT → AUTHORIZE_SESSION → START_CHARGING → SET_POWER 5 kW | all ALLOW |
| `full_lifecycle` | CONNECT → AUTHORIZE → START → SET_POWER 5 kW → SET_CURRENT 16 A → STOP → DISCONNECT | all ALLOW |
| `excess_power` | Authenticated controller reaches CHARGING, then asks for SET_POWER 20 kW on a 7 kW session | BLOCK `policy.power_limit` |
| `invalid_state` | START_CHARGING on a fresh, disconnected session | BLOCK `state.invalid_transition` |
| `excess_current` | Authenticated controller reaches CHARGING, then asks for SET_CURRENT 40 A on a 32 A session | BLOCK `policy.current_limit` |
| `invalid_token` | CONNECT with token `bad-token` | BLOCK `auth.invalid_token` |
| `unauthorized_role` | `monitor_01` (valid token, read-only role) sends CONNECT | BLOCK `authz.command_not_permitted` |
| `rate_burst` | 3 setup commands + 12 × SET_POWER 5 kW in quick succession | steps 1–10 ALLOW, steps 11–15 BLOCK `sequence.rate_exceeded` |

Notes:

- In `excess_power` the request is blocked before any power was ever set, so the simulated charger stays at 0 kW. (The dashboard's *Baseline vs EVGuard* card and `demo.py` use a session that is already charging at 5 kW, which is why they show "stays at 5 kW".)
- The rate thresholds are demo values, not EV industry limits: max 10 commands per source+session per 10 s.

---

## 13. Rule ID Catalog

| Rule ID | Meaning |
|---|---|
| `input.invalid` | Command is malformed. The API answers HTTP 422 for schema violations; the engine returns BLOCK `input.invalid` for a malformed command passed to it directly |
| `auth.missing_token` | No token supplied |
| `auth.invalid_token` | Token unknown |
| `auth.source_mismatch` | Token belongs to a different `source_id` |
| `authz.command_not_permitted` | Sender's role may not issue this command type |
| `session.unknown` | `session_id` does not exist |
| `state.invalid_transition` | Command not valid in the current state |
| `policy.power_limit` | Requested kW > `max_power_kw` |
| `policy.current_limit` | Requested A > `max_current_a` |
| `sequence.rate_exceeded` | Too many commands for this source+session in the window |
| `sequence.duplicate_command_id` | `command_id` already processed |
| `engine.internal_error` | Unexpected error, failed closed |
| `ok` | All checks passed (ALLOW) |

The canonical list is `RULES` in `contract/evguard_contract.py`.

---

## 14. Baseline vs EVGuard Demonstration

| | Baseline simulated controller | EVGuard-protected simulated controller |
|---|---|---|
| Path | Command → simulator | Command → EVGuard checks → simulator only if ALLOW |
| `SET_POWER 20 kW` on a 7 kW session already charging at 5 kW | Simulator applies 20 kW setpoint | BLOCK, setpoint unchanged |

The baseline (`simulator/baseline.py`) runs on its **own separate simulated session**, so it cannot change the protected session's state or audit log. You can run this comparison from the dashboard (*Baseline vs EVGuard* card) or in the terminal (`python demo.py`).

This comparison shows what our *baseline simulator* does without the gateway. It is **not** a claim about how any real EV charger, OCPP implementation or ISO 15118 stack would behave, since many real systems enforce their own limits.

---

## 15. Dashboard

A single Streamlit page, designed so a judge can understand it without reading code. Top to bottom:

1. **What is EVGuard?** and **How to use this dashboard** panels, with the pipeline in one line.
2. **Scenario cards**, grouped into *Normal operation* and *Attacks*. Each card shows a description, the expected result (`ALLOW`, or `BLOCK` plus the rule ID) and a **Run** button. A **Reset demo** button re-creates `sess_demo` and clears the displayed run.
3. **What just happened**: a step-by-step table (command, value, decision, rule, reason, expected vs actual) and a plain-English conclusion that is computed from the run's actual decisions and the session's actual state, plus a raw-JSON expander.
4. **Baseline vs EVGuard**: sends the same 20 kW command to the unprotected simulated baseline and to EVGuard, side by side.
5. **Statistics** (total / allowed / blocked / block rate) and the **latest decision card**.
6. **Charging session health** for the session of the last run (default `sess_demo`).
7. **Audit trail** with filters (decision, command, rule) and a CSV download (UTF-8 with BOM, so Excel shows the characters correctly).

Technical details (rule IDs, command IDs, raw JSON) sit in expanders so the default view stays clean. If the backend is not running, the page explains how to start it instead of showing an error. `EVGUARD_MOCK=1` switches the dashboard to bundled sample data; it is off by default.

---

## 16. Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Backend | Python + FastAPI (Pydantic) | API and input validation |
| Security engine | Pure Python | Auth, authz, state, policy, rate logic |
| Simulation | Python | Simulated EV / charger / session, plus the unprotected baseline |
| Database | SQLite (`sqlite3`, parameterized queries) | Audit trail and session records |
| Configuration | YAML via `yaml.safe_load` | Limits and roles |
| Dashboard | Streamlit (talks to the API with `requests`) | Demo interface |
| Testing | pytest | Unit, API, integration and dashboard tests |
| Version control | Git + GitHub | Collaboration |

Everything runs locally; no charging hardware is required.

---

## 17. Running EVGuard, Configuration and Tests

The one-command launchers and the manual commands are at the top of this README. Handy options:

| Setting | Effect |
|---|---|
| `.\run.ps1 -NoDashboard` / `./run.sh --no-dashboard` | Start the backend, check `/health`, stop again (smoke test) |
| `EVGUARD_NO_BROWSER=1` | Launchers do not open a browser |
| `EVGUARD_PORT=8010` | Launchers use another backend port (default 8000) |
| `EVGUARD_API_URL` | Where the dashboard finds the API (default `http://127.0.0.1:8000`) |
| `EVGUARD_MOCK=1` | Dashboard shows bundled sample data instead of calling the API (default: off) |

Interactive API documentation is at `http://127.0.0.1:8000/docs` while the backend is running.

Run the tests from the repository root:

```bash
python -m pytest -q
```

---

## 18. Repository Structure

```text
evguard/
├── run.ps1 / run.sh         # one-command launchers (Windows / macOS+Linux)
├── demo.py                  # no-browser demo: all scenarios through the real gateway
├── backend/
│   ├── main.py              # FastAPI app; policy validated at startup
│   └── schemas.py           # CommandIn: strict request validation (HTTP 422)
├── core/
│   ├── auth.py
│   ├── authz.py
│   ├── state_engine.py      # explicit transition table (from the contract)
│   ├── policy_engine.py
│   ├── sequence_check.py    # sliding-window rate tracker
│   └── decision.py          # Gateway: pipeline + fail-closed wrapper
├── contract/
│   ├── evguard_contract.py  # canonical shared contract (v1.1)
│   └── CONTRACT.md          # read-only mirror
├── simulator/
│   ├── ev_simulator.py      # simulated charger (does no security checks)
│   ├── baseline.py          # unprotected baseline controller
│   ├── scenarios.py         # scenario loader and runner
│   └── scenario_data/       # the 8 scenarios as JSON
├── database/
│   ├── db.py
│   └── schema.sql
├── dashboard/
│   ├── app.py               # single-page Streamlit dashboard
│   ├── api_client.py        # the dashboard's only link to the backend
│   └── mock_data/           # sample data for EVGUARD_MOCK=1
├── config/
│   ├── loader.py
│   └── policy_rules.yaml
├── tests/                   # pytest suite
├── docs/                    # specs, real API responses, screenshots/
├── .streamlit/config.toml   # Streamlit settings (usage stats off)
├── requirements.txt
└── README.md
```

---

## 19. Database Design

### `command_log`

| Column | Type | Description |
|---|---|---|
| id | INTEGER PRIMARY KEY | Row ID |
| command_id | TEXT (indexed) | Command identifier. Not UNIQUE: a duplicate-ID attempt is logged as its own BLOCK row |
| received_at | TEXT | Server receive time (ISO 8601, UTC) |
| client_timestamp | TEXT | Timestamp claimed by the client (informational only) |
| session_id | TEXT | Charging session (NULL if unknown) |
| source_id | TEXT | Claimed sender (NULL if unknown) |
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

The demo session `sess_demo` (`Vehicle-01`, 7 kW, 32 A) is seeded at startup. The database file `evguard.db` is created in the working directory and is git-ignored.

---

## 20. API

Contract v1.1. The base URL is `http://127.0.0.1:8000`.

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Service health and contract version |
| `/command` | POST | Submit one command through EVGuard. Returns the decision, or HTTP 422 for a malformed command |
| `/commands` | GET | Recent decisions, newest first (`limit`, capped at 200) |
| `/commands/{command_id}` | GET | One decision, or 404 |
| `/sessions/{session_id}` | GET | Session state, limits and the simulated charger's physical snapshot, or 404 |
| `/sessions` | POST | Create or reset a session |
| `/stats` | GET | `total`, `allowed`, `blocked` counts |
| `/scenarios` | GET | List the available scenarios |
| `/scenarios/{name}` | POST | Run a named scenario (fixed allow-list only) and return its result |
| `/baseline/command` | POST | Send a command to the unprotected baseline simulator |

Prototype note: read endpoints are unauthenticated and the API binds to `127.0.0.1`. That is acceptable only for a local demo.

---

## 21. Policy Configuration

`config/policy_rules.yaml`:

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
  monitor: []            # read-only: may not send commands
```

- Loaded with `yaml.safe_load` and checked against the contract at startup. **A missing file or a config that does not match the contract makes the service refuse to start** rather than run with a partial policy.
- The demo identities and tokens (`controller_A`, `monitor_01`) are constants in `contract/evguard_contract.py`. They are **demo values, not secrets**, and are checked with a constant-time comparison.
- 7 kW and 32 A are **illustrative demo values** (roughly a single-phase AC home charger), not universal EV specifications.

---

## 22. Testing

```bash
python -m pytest -q
```

Real output from the current repository state:

```text
........................................................................ [ 30%]
........................................................................ [ 61%]
........................................................................ [ 92%]
..................                                                       [100%]

(2 third-party deprecation warnings omitted here)
234 passed, 2 warnings in 38.30s
```

What is covered:

- **All 8 scenarios pass end-to-end** through the real `Gateway` and simulator (`tests/test_integration_scenarios.py`, one test per scenario) and through `python demo.py` (`tests/test_demo.py`).
- Core engine: authentication, authorization, state engine, limits (including a value exactly at the limit), rate window, duplicate `command_id`, unknown session, fail-closed behaviour.
- API: input validation returns HTTP 422 for every malformed case, nothing reaches the engine, and 422 bodies never echo the submitted input or token.
- Contract: the canonical contract file and its Markdown mirrors stay in sync.
- Dashboard: the page renders against a real in-process backend, scenario cards, the *What just happened* panel, reset, the baseline comparison and the backend-down message.

`SET_POWER 7 kW` (exactly the limit) is allowed; only strictly greater values are blocked.

---

## 23. Security of EVGuard Itself

| Area | Prototype (this MVP) | Production would need |
|---|---|---|
| Sender authentication | Static demo tokens defined in the contract file, constant-time comparison | Mutual TLS / PKI, hardware-backed keys, rotation, expiry |
| Authorization | Role → command allow-list in YAML | Centrally managed, audited policy |
| Input handling | Pydantic schemas, strict types/ranges, length limits, unknown fields rejected, 422 bodies never echo input | Same, plus protocol-level validation (OCPP/ISO 15118 messages) |
| Decision safety | Fail-closed wrapper; apply only on explicit ALLOW | Same, plus independent safety interlocks in the charger |
| Configuration | `yaml.safe_load`, validated against the contract at startup | Signed, versioned configuration |
| Database | Parameterized SQL only; tokens never stored | Tamper-evident / append-only audit storage |
| Logging | No tokens or secrets logged | SIEM integration, retention policy |
| Exposure | Bound to `127.0.0.1`; read endpoints unauthenticated | Authenticated, rate-limited, network-segmented API |
| Code | No `eval`/`exec`/`pickle` in the application code; scenarios chosen from a fixed list | Code review, SAST, dependency scanning |
| State source | Trusts the simulator's state | Trusted, integrity-protected telemetry |

EVGuard's own security is **prototype-grade**. It demonstrates the enforcement concept; it is not hardened for deployment.

---

## 24. Scope: What Is Implemented

### Implemented

- Session state machine with the explicit transition table
- Sender authentication and role authorization (simulated, demo tokens)
- Power-limit and current-limit enforcement (separate units)
- State-validity enforcement, rate check, duplicate `command_id` guard
- Fail-closed decision wrapper
- `POST /command` with strict input validation (HTTP 422) and a SQLite audit log
- Eight scenarios, the unprotected baseline and the baseline comparison
- Streamlit dashboard: guided single page, decision card, session health, statistics, audit trail with CSV export
- One-command launchers and a no-browser terminal demo
- pytest suite

### Deliberately out of scope

ML models, real OCPP/ISO 15118 message handling, real hardware, blockchain, cloud infrastructure, editable policies from the dashboard, NetworkX graphs, charts, hosted deployment.

---

## 25. Demo Script (target ≈ 4 minutes; video must be under 5)

| Time | Step | What judges see |
|---|---|---|
| 0:00–0:30 | Problem in one sentence + the *What is EVGuard?* panel | "Authenticated ≠ safe" |
| 0:30–1:10 | Run **Normal charging session** | Four green ALLOWs |
| 1:10–1:50 | Run **Excess power attack** | Red BLOCK, `policy.power_limit`, conclusion in plain English |
| 1:50–2:30 | Run **Invalid state transition** | BLOCK, `state.invalid_transition` |
| 2:30–3:00 | Run **Rate limit exceeded** (optional) | First 10 commands ALLOW (3 setup + 7 × SET_POWER), the rest BLOCK `sequence.rate_exceeded` |
| 3:00–3:30 | **Baseline vs EVGuard**: send 20 kW to both | Baseline applies 20 kW; EVGuard blocks it |
| 3:30–4:00 | **Audit trail** | time, command, decision, rule, reason |

Rehearse with the scenario cards; do not type commands live.

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
| **Technical Implementation** | Working FastAPI gateway, explicit FSM, unit-safe policy engine, fail-closed design, strict input validation, SQLite audit trail, pytest suite. |
| **Innovation & Creativity** | Integrates identity, permission, state, safety and rate checks into one explainable pre-execution decision, an engineering integration positioned honestly against prior work (§4). |
| **User Experience & Design** | A guided single-page dashboard: scenario cards, a plain-English *What just happened* panel, and a one-command launcher. |
| **Presentation & Demo** | ~4-minute scripted demo (§25) within the under-5-minute video limit. |

Cybersecurity relevance: EVGuard enforces authentication, authorization, input validation and policy on a control path, and produces an audit trail.

---

## 31. AI / External Tools Disclosure

The hackathon requires disclosure of significant AI/external-tool use. This project uses:

| Tool | Used for |
|---|---|
| Claude (Claude Code / Claude chat) | Coding assistance, refactoring, debugging, test generation, README review |
| Antigravity + Gemini | Architecture discussion, code assistance, UI iteration, debugging |

> **Note for Gopesh (delete before submission):** please confirm the exact usage of each tool (which parts of the code, tests and documentation they touched) and update this table so it matches reality. The wording above is carried over from the planning draft, and the tool list is the one you gave me. Replit, which the planning draft listed, is not in it, so I removed it.

The team remains responsible for understanding the code, validating generated output, running the tests, making final design decisions and explaining the security model to judges. No AI-generated output is presented as a tested result unless it was actually executed and verified.

---

## Team & Contributions

| Member | Contribution |
|---|---|
| **Gopesh** | Core engine (authentication, authorization, state, policy, rate, fail-closed decision pipeline, audit database), FastAPI API, shared contract, and integration of all parts |
| **Videsh** | EV/charger simulator, the eight attack and normal scenarios, and the unprotected baseline controller |
| **Vishwajit** | Streamlit dashboard and the input-validation schema (`backend/schemas.py`) |

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
| **Try it** | `.\run.ps1` / `./run.sh`, or `python demo.py` |
| **Stack** | Python · FastAPI · Streamlit · SQLite · PyYAML · pytest |
| **Scope** | Prototype / simulation only |
| **Next** | Protocol-aware, trusted-state, hardware-backed gateway |
