"""State-aware security gateway for EV charging commands."""

import typing


class Gateway:
    """Security gateway that evaluates EV charging commands before execution."""

    def __init__(
        self, db_path: str = "evguard.db", simulator: typing.Any = None
    ) -> None:
        self.db_path = db_path
        self.simulator = simulator

    def create_session(self, session_def: dict) -> dict:
        """Create or reset a session to DISCONNECTED; clears its rate window. Returns session dict (§3.3)."""
        raise NotImplementedError("TODO: implement create_session")

    def handle(self, command: dict) -> dict:
        """Evaluate one command. NEVER raises. Returns decision dict (§3.2). Applies to physical sim only on ALLOW.

        Check order (from ROLE_1 Step 6):
        1. Validate the dict: keys, command_type in COMMANDS, value and unit rules, value finite and > 0.
           On failure -> BLOCK input.invalid.
        2. Duplicate ID check (sequence.duplicate_command_id).
        3. Auth (auth.*) -> authz (authz.command_not_permitted).
        4. Session lookup -> session.unknown.
        5. Rate record.
        6. State (state.invalid_transition) -> policy (policy.power_limit / policy.current_limit) -> rate result (sequence.rate_exceeded).
        7. On ALLOW: update the state in the DB. If a simulator is attached, call simulator.apply(command).
        8. Build the decision dict with exactly DECISION_KEYS and store it. Never store the token.

        Must NEVER raise: if any unexpected exception occurs, fail closed with rule engine.internal_error.
        """
        raise NotImplementedError("TODO: implement handle")

    def get_session(self, session_id: str) -> dict | None:
        """Get session dict (§3.3) or None.

        Note: Merges the DB session with simulator.snapshot() under 'physical'.
        Without an attached simulator, uses a zeroed snapshot matching SNAPSHOT_KEYS.
        """
        raise NotImplementedError("TODO: implement get_session")

    def recent_decisions(self, limit: int = 50) -> list[dict]:
        """Return recent decisions, newest first."""
        raise NotImplementedError("TODO: implement recent_decisions")

    def stats(self) -> dict:
        """Return stats dict: {'total': int, 'allowed': int, 'blocked': int}."""
        raise NotImplementedError("TODO: implement stats")

