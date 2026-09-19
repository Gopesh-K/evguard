"""Rate tracking for EVGuard: limits commands per (source_id, session_id)."""

from collections import deque

from contract.evguard_contract import RATE_MAX_COMMANDS, RATE_WINDOW_SECONDS


class RateTracker:
    """Sliding-window command counter keyed by (source_id, session_id).

    Duplicate command_ids are checked by the Gateway against the command log.
    """

    def __init__(self) -> None:
        self._windows: dict[tuple[str, str], deque] = {}

    def record_and_check(
        self, source_id: str, session_id: str, now: float
    ) -> tuple[bool, str, str]:
        """Record command arrival and check if rate limit exceeded.

        Every call is recorded, whether the command ends up allowed or blocked.
        Returns (ok, rule_id, reason).
        """
        window = self._windows.setdefault((source_id, session_id), deque())

        # Drop arrivals that have slid out of the window, then count this one.
        while window and now - window[0] >= RATE_WINDOW_SECONDS:
            window.popleft()
        window.append(now)

        if len(window) > RATE_MAX_COMMANDS:
            return (False, "sequence.rate_exceeded",
                    f"{len(window)} commands from {source_id} for session {session_id} "
                    f"within {RATE_WINDOW_SECONDS} seconds exceeds the limit of "
                    f"{RATE_MAX_COMMANDS}")
        return True, "ok", ""

    def clear(self, session_id: str) -> None:
        """Clear rate tracking windows for a session."""
        for key in [k for k in self._windows if k[1] == session_id]:
            del self._windows[key]
