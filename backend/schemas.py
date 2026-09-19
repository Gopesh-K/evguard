# TEMPORARY - will be replaced by Vishwajit's schemas.py (same class name and method). Do not add logic here.

from pydantic import BaseModel
from contract.evguard_contract import COMMAND_KEYS


class CommandIn(BaseModel):
    """Temporary input schema for incoming commands."""

    command_id: str
    timestamp: str | None = None
    session_id: str
    source_id: str
    auth_token: str
    command_type: str
    value: float | None = None
    unit: str | None = None

    def to_command(self) -> dict:
        """Convert to dict with exactly COMMAND_KEYS."""
        return {
            "command_id": self.command_id,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "source_id": self.source_id,
            "auth_token": self.auth_token,
            "command_type": self.command_type,
            "value": self.value,
            "unit": self.unit,
        }

