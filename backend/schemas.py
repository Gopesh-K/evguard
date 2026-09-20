# TEMPORARY - will be replaced by Vishwajit's schemas.py (same class name and method). Do not add logic here.
# Command-specific rules are NOT here: they return 200 BLOCK input.invalid until the final schemas.py (CONTRACT.md section 6).

from pydantic import BaseModel, Field
from contract.evguard_contract import COMMAND_KEYS


class CommandIn(BaseModel):
    """Temporary input schema for incoming commands."""

    command_id: str
    timestamp: str | None = None
    session_id: str
    source_id: str
    auth_token: str
    command_type: str
    # Generic type tightening only: a string or boolean is rejected instead of coerced to a number.
    value: float | None = Field(default=None, strict=True)
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

