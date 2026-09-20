"""Charger simulator implementation for EVGuard (Role 2).

Intentionally a dumb physical charger simulator that executes commands blindly
without performing security, authorization, rate, or limit checks.
"""

from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ChargerSimulator:
    """Dumb execution layer. Applies whatever it is given. Does NO security checks."""

    def __init__(self) -> None:
        self.sessions: dict[str, dict] = {}

    def reset_session(self, session_id: str, vehicle_id: str = "Vehicle-01") -> dict:
        """Reset or initialize a session to the default disconnected state."""
        self.sessions[session_id] = {
            "session_id": session_id,
            "vehicle_id": vehicle_id,
            "plugged_in": False,
            "charging": False,
            "power_kw": 0.0,
            "current_a": 0.0,
            "last_command": None,
            "updated_at": _now(),
        }
        return dict(self.sessions[session_id])

    def ensure_session(self, session_id: str, vehicle_id: str = "Vehicle-01") -> dict:
        """Ensure a session exists; reset only if it is missing."""
        if session_id not in self.sessions:
            return self.reset_session(session_id, vehicle_id)
        return dict(self.sessions[session_id])

    def snapshot(self, session_id: str) -> dict | None:
        """Return a copy of the session snapshot, or None if unknown."""
        if session_id in self.sessions:
            return dict(self.sessions[session_id])
        return None

    def apply(self, command: dict) -> dict:
        """Apply a command directly to the simulated physical charger.

        Does not perform security checks. Returns a copy of the updated snapshot.
        """
        session_id = command.get("session_id") or "sess_default"
        if session_id not in self.sessions:
            self.ensure_session(session_id, "Vehicle-01")

        sess = self.sessions[session_id]
        cmd_type = command.get("command_type")
        value = command.get("value")

        if cmd_type == "CONNECT":
            sess["plugged_in"] = True
        elif cmd_type == "AUTHORIZE_SESSION":
            # No physical state change
            pass
        elif cmd_type == "START_CHARGING":
            sess["charging"] = True
        elif cmd_type == "SET_POWER":
            sess["power_kw"] = float(value) if value is not None else 0.0
        elif cmd_type == "SET_CURRENT":
            sess["current_a"] = float(value) if value is not None else 0.0
        elif cmd_type == "STOP_CHARGING":
            sess["charging"] = False
            sess["power_kw"] = 0.0
            sess["current_a"] = 0.0
        elif cmd_type == "DISCONNECT":
            sess["plugged_in"] = False
            sess["charging"] = False
            sess["power_kw"] = 0.0
            sess["current_a"] = 0.0

        sess["last_command"] = cmd_type
        sess["updated_at"] = _now()

        return dict(sess)

