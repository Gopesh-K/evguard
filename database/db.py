"""SQLite storage for EVGuard: command log and sessions.

One connection shared by all threads, guarded by a lock. Every query uses
? placeholders; values are never formatted into SQL strings.
"""

import sqlite3
import threading
from pathlib import Path

from contract.evguard_contract import DECISION_KEYS

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

# Columns of command_log that make up a decision dict (contract DECISION_KEYS).
_DECISION_COLUMNS = ", ".join(DECISION_KEYS)


class Database:
    """Thin wrapper around one sqlite3 connection."""

    def __init__(self, path: str = "evguard.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _write(self, sql: str, params: tuple) -> None:
        with self._lock:
            self._conn.execute(sql, params)
            self._conn.commit()

    def _read(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    # ---- command_log -----------------------------------------------------

    def insert_decision(
        self, d: dict, role: str | None = None, client_timestamp: str | None = None
    ) -> None:
        """Insert an evaluated command decision record into command_log."""
        self._write(
            "INSERT INTO command_log (command_id, received_at, client_timestamp, "
            "session_id, source_id, role, command_type, value, unit, decision, "
            "reason, rule_triggered, state_before, state_after) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (d["command_id"], d["received_at"], client_timestamp,
             d["session_id"], d["source_id"], role, d["command_type"],
             d["value"], d["unit"], d["decision"], d["reason"],
             d["rule_triggered"], d["state_before"], d["state_after"]),
        )

    def recent_decisions(self, limit: int = 50) -> list[dict]:
        """Return recent decision records, newest first."""
        rows = self._read(
            f"SELECT {_DECISION_COLUMNS} FROM command_log ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in rows]

    def get_decision(self, command_id: str) -> dict | None:
        """Retrieve the first decision logged for command_id, or None."""
        rows = self._read(
            f"SELECT {_DECISION_COLUMNS} FROM command_log "
            "WHERE command_id = ? ORDER BY id ASC LIMIT 1",
            (command_id,),
        )
        return dict(rows[0]) if rows else None

    def stats(self) -> dict:
        """Return stats dict: {'total': int, 'allowed': int, 'blocked': int}."""
        row = self._read(
            "SELECT COUNT(*) AS total, "
            "COALESCE(SUM(decision = 'ALLOW'), 0) AS allowed, "
            "COALESCE(SUM(decision = 'BLOCK'), 0) AS blocked "
            "FROM command_log"
        )[0]
        return {"total": row["total"], "allowed": row["allowed"], "blocked": row["blocked"]}

    # ---- sessions --------------------------------------------------------

    def upsert_session(self, s: dict) -> None:
        """Insert or update a session record (created_at is kept on update)."""
        self._write(
            "INSERT INTO sessions (session_id, vehicle_id, max_power_kw, "
            "max_current_a, current_state, current_power_kw, current_current_a, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(session_id) DO UPDATE SET "
            "vehicle_id = excluded.vehicle_id, "
            "max_power_kw = excluded.max_power_kw, "
            "max_current_a = excluded.max_current_a, "
            "current_state = excluded.current_state, "
            "current_power_kw = excluded.current_power_kw, "
            "current_current_a = excluded.current_current_a, "
            "updated_at = excluded.updated_at",
            (s["session_id"], s["vehicle_id"], s["max_power_kw"],
             s["max_current_a"], s["current_state"], s["current_power_kw"],
             s["current_current_a"], s["created_at"], s["updated_at"]),
        )

    def get_session(self, session_id: str) -> dict | None:
        """Retrieve session record by session_id, or None if not found."""
        rows = self._read("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
        return dict(rows[0]) if rows else None


def init_db(path: str = "evguard.db") -> Database:
    """Open the SQLite database at path, creating the tables if needed."""
    return Database(path)
