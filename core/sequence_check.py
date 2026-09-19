"""Sequence and rate tracking stub for EVGuard."""


class RateTracker:
    """Tracks command rates per (source_id, session_id) and duplicate command IDs."""

    def __init__(self) -> None:
        pass

    def record_and_check(
        self, source_id: str, session_id: str, now: float
    ) -> tuple[bool, str, str]:
        """Record command arrival and check if rate limit exceeded.

        Returns (ok, rule_id, reason).
        """
        raise NotImplementedError("TODO: implement record_and_check")

    def clear(self, session_id: str) -> None:
        """Clear rate tracking window for a session."""
        raise NotImplementedError("TODO: implement clear")

