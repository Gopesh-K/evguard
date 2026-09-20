"""Unprotected baseline charger execution for EVGuard (Role 2).

Directly applies commands to an isolated ChargerSimulator without any
intervening EVGuard security gate checks, demonstrating the unsafe execution
path where dangerous or unauthorized commands are applied unchecked.
"""

from simulator.ev_simulator import ChargerSimulator

# Dedicated module-level simulator instance isolated from protected sessions
_BASELINE = ChargerSimulator()


def baseline_apply(command: dict) -> dict:
    """Apply a command directly to the unprotected baseline charger.

    Performs NO security checks, rate limiting, or policy enforcement.
    Returns:
        {"mode": "baseline", "accepted": True, "snapshot": <snapshot dict>}
    """
    snapshot = _BASELINE.apply(command)
    return {
        "mode": "baseline",
        "accepted": True,
        "snapshot": snapshot,
    }

