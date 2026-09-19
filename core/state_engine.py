"""State engine for EVGuard: decides which command is valid in which state."""

from contract.evguard_contract import TRANSITIONS


def next_state(current: str, command_type: str) -> str | None:
    """Return next state from TRANSITIONS, or None if invalid."""
    return TRANSITIONS.get((current, command_type))
