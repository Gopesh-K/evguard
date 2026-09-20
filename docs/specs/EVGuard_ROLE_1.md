# EVGuard — Role 1: Core Security Engine + Backend API + Final Integration (Gopesh)

> **For the AI assistant reading this (Claude, Claude Code, or Gemini):**
> You are helping the EVGuard team lead build the core engine and API for a 24-hour hackathon.
> Source of truth: `EVGuard_CONTRACT.md` (names, shapes, signatures), then `EVGuard_FINAL_README.md` (behavior).
> Build only what this file lists, in the order given. Prefer simple, readable Python over clever code.
> Do not add dependencies beyond the contract's list. Do not add AI co-author trailers (`Co-Authored-By`, session trailers) to commit messages.
> Before writing code, explain the plan in 3–5 lines. After writing code, give the exact command to test it.

---

## 1. What you own

`contract/`, `core/`, `backend/` (except `schemas.py`), `database/`, `config/`, and `tests/test_core_*.py`. You also own **final integration**, the **final repository**, the final README and submission (see `EVGuard_INTEGRATION_GUIDE.md`).

**Delegated:**
- Videsh (Role 2) builds the simulator, scenarios and baseline.
- Vishwajit (Role 3) builds the dashboard **and `backend/schemas.py`**, the Pydantic input model. You review his `schemas.py` and wire it in.

You do not build these, but you use them all during integration.

## 2. Tool plan

- **H0–H1:** Use Antigravity + Gemini to generate empty files, folders and `__init__.py`, plus FastAPI boilerplate.
- **H1 onward:** Use Claude Code for the engine logic and tests, and later for integration. Paste the contract into the session first.
- Keep one Claude Code session focused on `core/`. If context gets long, start a fresh session with the contract and this file.

## 3. Setup (H0–H1)

```bash
mkdir evguard && cd evguard
git init
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install fastapi uvicorn pydantic pyyaml httpx pytest
mkdir contract core backend database config tests
# create empty __init__.py in contract, core, backend, database, tests
```

`.gitignore`:
```text
.venv/
__pycache__/
*.db
.env
.pytest_cache/
```

Copy `contract/evguard_contract.py` from the contract (§2). Post the contract to the team by **H1**. This is the most important deliverable of the first hour, because both teammates are blocked until it exists.

Create the GitHub repo that will become the **final** repo and push.

## 4. Build order

Each step ends with passing tests before you move on.

### Step 1 — `core/state_engine.py` (H1–H2)

```python
def next_state(current: str, command_type: str) -> str | None:
    """Return next state from TRANSITIONS, or None if invalid."""
```

Tests (`tests/test_core_state.py`): every row of the transition table, plus these must be `None`: START_CHARGING from DISCONNECTED, DISCONNECT from CHARGING, SET_POWER from AUTHORIZED.

### Step 2 — `core/policy_engine.py` (H2–H3)

```python
def check_limits(command: dict, session: dict) -> tuple[bool, str, str]:
    """Returns (ok, rule_id, reason). SET_POWER vs max_power_kw; SET_CURRENT vs max_current_a.
    Other commands -> (True, "ok", "")."""
```

The value must be strictly greater than the limit to fail, so exactly 7.0 passes. Never compare amps to kW. Include a test that `SET_CURRENT 16 A` with a 7 kW power limit is **allowed**.

### Step 3 — `core/auth.py`, `core/authz.py` (H3–H4)

```python
def authenticate(command: dict) -> tuple[bool, str, str, str | None]  # ok, rule, reason, role
def authorize(role: str, command_type: str) -> tuple[bool, str, str]
```

- Look up `source_id` in `DEMO_SOURCES`.
- Missing or empty token → `auth.missing_token`.
- Token not equal to that source's token (or unknown source) → `auth.invalid_token`.
- Token belongs to another source → `auth.source_mismatch`.
- Compare tokens with `hmac.compare_digest`.

**Checkpoint 1 (H4):** show `pytest` passing for the state, policy and auth modules.

### Step 4 — `core/sequence_check.py` (H4–H5)

```python
class RateTracker:
    def record_and_check(self, source_id: str, session_id: str, now: float) -> tuple[bool, str, str]
    def clear(self, session_id: str) -> None
```

- Use a dict of deques keyed by `(source_id, session_id)` and server time from `time.monotonic()`.
- Record a command after auth passes.
- The Gateway calls it after auth, but reports its result only if the state and policy checks passed.

To keep the check order (the first failing check wins): record and check the rate right after auth, store the result, then return a rate BLOCK only if state and policy pass. Write a test for the `rate_burst` expectations: 3 setup commands + 12 × SET_POWER 5 kW, steps 1–10 ALLOW, 11–15 BLOCK.

Duplicate IDs: keep a `set` of processed `command_id`s. A repeat → `sequence.duplicate_command_id`, checked right after input validation.

### Step 5 — `database/db.py` (H5–H6)

- Use `sqlite3` with parameterized queries only (`?` placeholders, never f-strings in SQL).
- Two tables, as in README §19: `command_log` and `sessions`.
- Functions: `init_db(path)`, `insert_decision(d)`, `recent_decisions(limit)`, `get_decision(command_id)`, `upsert_session(s)`, `get_session(id)`, `stats()`.
- Use `check_same_thread=False` and one connection with a `threading.Lock`. FastAPI can call from threads.

### Step 6 — `core/decision.py`, the `Gateway` (H6–H7)

Implement the contract §5 signatures. `handle()` does the following, in this order:

1. Validate the dict: keys, `command_type` in `COMMANDS`, value and unit rules, value finite and > 0. On failure → BLOCK `input.invalid`.
2. Duplicate ID check.
3. Auth → authz.
4. Session lookup → `session.unknown`.
5. Rate record.
6. State → policy → rate result.
7. On ALLOW: update the state in the DB. If a simulator is attached, call `simulator.apply(command)`.
8. Build the decision dict with exactly `DECISION_KEYS` and store it. Never store the token.

Wrap the whole body in `try/except Exception` → BLOCK `engine.internal_error` and log the traceback to the console. Nothing is applied on a BLOCK.

The Gateway takes an optional simulator: `Gateway(db_path, simulator=None)`. During standalone development, pass `None`. At integration, pass Role 2's `ChargerSimulator()`. `create_session` also calls `simulator.reset_session` if one is attached.

`get_session` merges the DB session with `simulator.snapshot()` under `"physical"`. Without a simulator, use a zeroed snapshot with the same keys.

Reason strings should be plain English with numbers, e.g. `Requested power 20.0 kW exceeds session maximum of 7.0 kW`.

### Step 7 — `backend/` FastAPI (H7–H8)

- `schemas.py` is **Vishwajit's** (contract §5). Until his version arrives at about H8, use a 5-line temporary `CommandIn` with the same class name and a `to_command()` method, so swapping it in later is a file replacement with no other changes.
- `main.py`: create one `Gateway`, seed `sess_demo` (Vehicle-01, 7 kW, 32 A), and define every endpoint in contract §6.
- The `/scenarios` endpoints are stubs until integration: return `{"items": []}` / 404.
- Run: `uvicorn backend.main:app --host 127.0.0.1 --port 8000`, then open `http://127.0.0.1:8000/docs` and try `/command`.
- Keep `config/policy_rules.yaml` minimal and loaded with `yaml.safe_load`. Its values must match the contract defaults. If loading fails, raise at startup (fail closed).

**Handoff 1 (H8):** save real JSON responses from `/commands`, `/sessions/sess_demo`, `/stats` and a BLOCK decision into `docs/real_responses/`. Send them to Vishwajit so the mock data matches reality.

## 5. Definition of done (Role 1 MUST)

- [ ] `pytest tests/test_core_*.py` all green
- [ ] Contract keys only; no extra or missing keys in the decision and session dicts
- [ ] A 20 kW SET_POWER while CHARGING returns BLOCK `policy.power_limit` via `/docs`
- [ ] START_CHARGING while DISCONNECTED returns BLOCK `state.invalid_transition`
- [ ] An injected exception returns BLOCK `engine.internal_error` (test it by monkeypatching)
- [ ] No token appears in the DB or console logs
- [ ] Every decision is visible in `GET /commands`

## 6. After H8

Switch to integration (`EVGuard_INTEGRATION_GUIDE.md`). Engine work after that is SHOULD items and bug fixes only.

## 7. Commit hygiene

Use small commits with clear messages (`core: add power limit check`). Before your first Claude Code commit, check that your settings don't add AI co-author trailers, and check `git log` afterwards. Remove any trailer with `git commit --amend` before pushing.
