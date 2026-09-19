"""State-aware security gateway for EV charging commands."""

import math
import re
import threading
import time
import traceback
import typing
import uuid
from datetime import datetime, timezone

from contract.evguard_contract import (
    ALLOW,
    BLOCK,
    COMMANDS,
    DEFAULT_MAX_CURRENT_A,
    DEFAULT_MAX_POWER_KW,
    INITIAL_STATE,
    RULES,
    SNAPSHOT_KEYS,
    VALUE_COMMANDS,
)
from core.auth import authenticate
from core.authz import authorize
from core.policy_engine import check_limits
from core.sequence_check import RateTracker
from core.state_engine import next_state
from database.db import init_db

ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
MAX_TOKEN_LENGTH = 128
MAX_TIMESTAMP_LENGTH = 40


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _is_number(x: typing.Any) -> bool:
    """True for a finite int/float (bool excluded)."""
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return False
    try:
        return math.isfinite(x)
    except OverflowError:
        return False


def _validate(command: typing.Any) -> str | None:
    """Return a plain-English problem with the command, or None if it is well formed."""
    if not isinstance(command, dict):
        return "Command must be an object"

    for key in ("command_id", "session_id", "source_id", "command_type"):
        if key not in command:
            return f"Missing field '{key}'"
    for key in ("command_id", "session_id", "source_id"):
        value = command[key]
        if not isinstance(value, str) or not ID_PATTERN.match(value):
            return f"Field '{key}' must be 1-64 letters, digits, '_' or '-'"

    token = command.get("auth_token")
    if token is not None and (not isinstance(token, str) or len(token) > MAX_TOKEN_LENGTH):
        return f"Field 'auth_token' must be a string of at most {MAX_TOKEN_LENGTH} characters"
    timestamp = command.get("timestamp")
    if timestamp is not None and (
        not isinstance(timestamp, str) or len(timestamp) > MAX_TIMESTAMP_LENGTH
    ):
        return f"Field 'timestamp' must be a string of at most {MAX_TIMESTAMP_LENGTH} characters"

    command_type = command["command_type"]
    if command_type not in COMMANDS:
        return "Unknown command_type"

    value, unit = command.get("value"), command.get("unit")
    if command_type in VALUE_COMMANDS:
        if not _is_number(value) or value <= 0:
            return f"{command_type} requires a finite value greater than 0"
        if unit != VALUE_COMMANDS[command_type]:
            return f"{command_type} requires unit {VALUE_COMMANDS[command_type]}"
    elif value is not None or unit is not None:
        return f"{command_type} must not carry a value or unit"
    return None


def _safe_summary(command: typing.Any) -> dict:
    """Identifying fields for the log. Anything malformed becomes None, never echoed."""
    command = command if isinstance(command, dict) else {}

    def ident(key: str) -> str | None:
        v = command.get(key)
        return v if isinstance(v, str) and ID_PATTERN.match(v) else None

    command_type = command.get("command_type")
    value = command.get("value")
    unit = command.get("unit")
    return {
        "command_id": ident("command_id") or "invalid_" + uuid.uuid4().hex[:12],
        "session_id": ident("session_id"),
        "source_id": ident("source_id"),
        "command_type": command_type if command_type in COMMANDS else None,
        "value": float(value) if _is_number(value) else None,
        "unit": unit if unit in ("kW", "A") else None,
    }


def _zeroed_snapshot(session: dict) -> dict:
    """Physical snapshot used when no simulator is attached."""
    snapshot = dict.fromkeys(SNAPSHOT_KEYS)
    snapshot.update(
        session_id=session["session_id"],
        vehicle_id=session["vehicle_id"],
        plugged_in=False,
        charging=False,
        power_kw=0.0,
        current_a=0.0,
        updated_at=session["updated_at"],
    )
    return snapshot


class Gateway:
    """Security gateway that evaluates EV charging commands before execution."""

    def __init__(
        self, db_path: str = "evguard.db", simulator: typing.Any = None
    ) -> None:
        self.db_path = db_path
        self.simulator = simulator
        self.db = init_db(db_path)
        self.rate = RateTracker()
        # handle() reads then updates session state, so run one command at a time.
        self._lock = threading.RLock()

    def create_session(self, session_def: dict) -> dict:
        """Create or reset a session to DISCONNECTED; clears its rate window. Returns session dict (§3.3).

        Raises ValueError if the definition is invalid.
        """
        if not isinstance(session_def, dict):
            raise ValueError("Session definition must be an object")
        session_id = session_def.get("session_id")
        vehicle_id = session_def.get("vehicle_id")
        max_power = session_def.get("max_power_kw", DEFAULT_MAX_POWER_KW)
        max_current = session_def.get("max_current_a", DEFAULT_MAX_CURRENT_A)
        for name, value in (("session_id", session_id), ("vehicle_id", vehicle_id)):
            if not isinstance(value, str) or not ID_PATTERN.match(value):
                raise ValueError(f"Field '{name}' must be 1-64 letters, digits, '_' or '-'")
        for name, value in (("max_power_kw", max_power), ("max_current_a", max_current)):
            if not _is_number(value) or value <= 0:
                raise ValueError(f"Field '{name}' must be a finite number greater than 0")

        with self._lock:
            now = _now_iso()
            self.db.upsert_session({
                "session_id": session_id,
                "vehicle_id": vehicle_id,
                "max_power_kw": float(max_power),
                "max_current_a": float(max_current),
                "current_state": INITIAL_STATE,
                "current_power_kw": 0.0,
                "current_current_a": 0.0,
                "created_at": now,
                "updated_at": now,
            })
            self.rate.clear(session_id)
            if self.simulator is not None:
                self.simulator.reset_session(session_id, vehicle_id)
            return self.get_session(session_id)

    def handle(self, command: dict) -> dict:
        """Evaluate one command. NEVER raises. Returns decision dict (§3.2). Applies to physical sim only on ALLOW.

        Check order (first failing check wins):
        input -> duplicate id -> auth -> authz -> session -> rate record
        -> state -> policy -> rate result.
        """
        received_at = _now_iso()
        seen: dict = {"state": None, "role": None}  # context for the fail-closed path
        try:
            with self._lock:
                return self._evaluate(command, received_at, seen)
        except Exception:
            traceback.print_exc()
            return self._fail_closed(command, received_at, seen)

    def _evaluate(self, command: typing.Any, received_at: str, seen: dict) -> dict:
        problem = _validate(command)
        if problem:
            return self._record(command, received_at, seen, "input.invalid", problem)
        command = dict(command)
        if command.get("value") is not None:
            command["value"] = float(command["value"])
        command_type = command["command_type"]

        if self.db.get_decision(command["command_id"]) is not None:
            return self._record(command, received_at, seen, "sequence.duplicate_command_id",
                                "Command ID has already been processed")

        ok, rule, reason, role = authenticate(command)
        if not ok:
            return self._record(command, received_at, seen, rule, reason)
        seen["role"] = role

        # The session state is only revealed once the caller is authenticated.
        session = self.db.get_session(command["session_id"])
        state = session["current_state"] if session else None
        seen["state"] = state

        ok, rule, reason = authorize(role, command_type)
        if not ok:
            return self._record(command, received_at, seen, rule, reason)
        if session is None:
            return self._record(command, received_at, seen, "session.unknown",
                                f"Session '{command['session_id']}' does not exist")

        # Recorded now so blocked commands count too; reported after state and policy.
        rate_ok, rate_rule, rate_reason = self.rate.record_and_check(
            command["source_id"], command["session_id"], time.monotonic())

        new_state = next_state(state, command_type)
        if new_state is None:
            return self._record(command, received_at, seen, "state.invalid_transition",
                                f"{command_type} is not valid while the session is {state}")
        ok, rule, reason = check_limits(command, session)
        if not ok:
            return self._record(command, received_at, seen, rule, reason)
        if not rate_ok:
            return self._record(command, received_at, seen, rate_rule, rate_reason)

        # ALLOW: apply to the charger first, then commit the new state.
        if self.simulator is not None:
            self.simulator.apply({**command, "auth_token": None})
        session["current_state"] = new_state
        if command_type == "SET_POWER":
            session["current_power_kw"] = command["value"]
        elif command_type == "SET_CURRENT":
            session["current_current_a"] = command["value"]
        session["updated_at"] = received_at
        self.db.upsert_session(session)
        return self._record(command, received_at, seen, "ok", RULES["ok"], new_state)

    def _record(self, command: typing.Any, received_at: str, seen: dict,
                rule: str, reason: str, state_after: str | None = None) -> dict:
        """Build the decision dict, store it and return it. The token is never included."""
        allowed = rule == "ok"
        timestamp = command.get("timestamp") if isinstance(command, dict) else None
        decision = {
            **_safe_summary(command),
            "decision": ALLOW if allowed else BLOCK,
            "rule_triggered": rule,
            "reason": reason,
            "state_before": seen["state"],
            "state_after": state_after if allowed else seen["state"],
            "received_at": received_at,
        }
        self.db.insert_decision(
            decision, role=seen["role"],
            client_timestamp=timestamp if isinstance(timestamp, str) else None)
        return decision

    def _fail_closed(self, command: typing.Any, received_at: str, seen: dict) -> dict:
        """BLOCK with engine.internal_error. Best effort to log it; never raises."""
        try:
            return self._record(command, received_at, seen, "engine.internal_error",
                                "Internal error - command blocked")
        except Exception:
            traceback.print_exc()
            return {
                **_safe_summary(command),
                "decision": BLOCK,
                "rule_triggered": "engine.internal_error",
                "reason": "Internal error - command blocked",
                "state_before": seen["state"],
                "state_after": seen["state"],
                "received_at": received_at,
            }

    def get_session(self, session_id: str) -> dict | None:
        """Get session dict (§3.3) or None.

        Note: Merges the DB session with simulator.snapshot() under 'physical'.
        Without an attached simulator, uses a zeroed snapshot matching SNAPSHOT_KEYS.
        """
        row = self.db.get_session(session_id)
        if row is None:
            return None
        snapshot = self.simulator.snapshot(session_id) if self.simulator is not None else None
        session = {
            "session_id": row["session_id"],
            "vehicle_id": row["vehicle_id"],
            "state": row["current_state"],
            "max_power_kw": row["max_power_kw"],
            "max_current_a": row["max_current_a"],
            "updated_at": row["updated_at"],
            "physical": snapshot if snapshot is not None else _zeroed_snapshot(row),
        }
        return session

    def get_decision(self, command_id: str) -> dict | None:
        """Return the decision logged for command_id, or None."""
        return self.db.get_decision(command_id)

    def recent_decisions(self, limit: int = 50) -> list[dict]:
        """Return recent decisions, newest first."""
        return self.db.recent_decisions(limit)

    def stats(self) -> dict:
        """Return stats dict: {'total': int, 'allowed': int, 'blocked': int}."""
        return self.db.stats()
