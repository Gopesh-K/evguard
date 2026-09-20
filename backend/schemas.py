import math
import re
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    field_validator,
    model_validator,
)

from contract.evguard_contract import COMMAND_KEYS, VALUE_COMMANDS


ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class CommandIn(BaseModel):
    """
    Validates an EVGuard command according to Contract v1.1.
    """

    model_config = ConfigDict(extra="forbid")

    command_id: str = Field(min_length=1, max_length=64)
    timestamp: str | None = Field(default=None, max_length=40)
    session_id: str = Field(min_length=1, max_length=64)
    source_id: str = Field(min_length=1, max_length=64)
    auth_token: str = Field(max_length=128)

    command_type: Literal[
        "CONNECT",
        "AUTHORIZE_SESSION",
        "START_CHARGING",
        "SET_POWER",
        "SET_CURRENT",
        "STOP_CHARGING",
        "DISCONNECT",
    ]

    value: StrictFloat | None = None
    unit: str | None = None

    @field_validator("command_id", "session_id", "source_id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not ID_PATTERN.fullmatch(value):
            raise ValueError(
                "must contain only letters, numbers, '_' or '-' "
                "and be 1-64 characters long"
            )
        return value

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: float | None) -> float | None:
        if value is None:
            return value

        if not math.isfinite(value):
            raise ValueError("value must be finite")

        if value <= 0:
            raise ValueError("value must be greater than 0")

        return value

    @model_validator(mode="after")
    def validate_command(self):
        expected_unit = VALUE_COMMANDS.get(self.command_type)

        if expected_unit is not None:
            if self.value is None:
                raise ValueError(
                    f"{self.command_type} requires a value"
                )

            if self.unit != expected_unit:
                raise ValueError(
                    f"{self.command_type} requires unit {expected_unit}"
                )

        else:
            if self.value is not None:
                raise ValueError(
                    f"{self.command_type} must not contain a value"
                )

            if self.unit is not None:
                raise ValueError(
                    f"{self.command_type} must not contain a unit"
                )

        return self

    def to_command(self) -> dict:
        command = {
            "command_id": self.command_id,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "source_id": self.source_id,
            "auth_token": self.auth_token,
            "command_type": self.command_type,
            "value": self.value,
            "unit": self.unit,
        }

        return {
            key: command[key]
            for key in COMMAND_KEYS
        }
