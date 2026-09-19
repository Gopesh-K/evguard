"""Database operations stub for EVGuard."""


def init_db(path: str = "evguard.db") -> None:
    """Initialize the SQLite database with schema tables."""
    raise NotImplementedError("TODO: implement init_db")


def insert_decision(d: dict) -> None:
    """Insert an evaluated command decision record into command_log."""
    raise NotImplementedError("TODO: implement insert_decision")


def recent_decisions(limit: int = 50) -> list[dict]:
    """Return recent decision records, newest first."""
    raise NotImplementedError("TODO: implement recent_decisions")


def get_decision(command_id: str) -> dict | None:
    """Retrieve a single decision by command_id, or None if not found."""
    raise NotImplementedError("TODO: implement get_decision")


def upsert_session(s: dict) -> None:
    """Insert or update a session record."""
    raise NotImplementedError("TODO: implement upsert_session")


def get_session(session_id: str) -> dict | None:
    """Retrieve session record by session_id, or None if not found."""
    raise NotImplementedError("TODO: implement get_session")


def stats() -> dict:
    """Return stats dict: {'total': int, 'allowed': int, 'blocked': int}."""
    raise NotImplementedError("TODO: implement stats")

