"""Policy configuration loader for EVGuard."""

from pathlib import Path

import yaml

from contract.evguard_contract import (
    DEFAULT_MAX_CURRENT_A,
    DEFAULT_MAX_POWER_KW,
    RATE_MAX_COMMANDS,
    RATE_WINDOW_SECONDS,
    ROLE_PERMISSIONS,
)

DEFAULT_PATH = Path(__file__).with_name("policy_rules.yaml")

# What the YAML must say. It has to match the contract exactly.
_EXPECTED = {
    "defaults": {"max_power_kw": DEFAULT_MAX_POWER_KW,
                 "max_current_a": DEFAULT_MAX_CURRENT_A},
    "sequence": {"window_seconds": RATE_WINDOW_SECONDS,
                 "max_commands_per_source": RATE_MAX_COMMANDS},
    "roles": ROLE_PERMISSIONS,
}


def load_policy(path: str | None = None) -> dict:
    """Load policy rules from YAML configuration file using yaml.safe_load.

    Raises (fails closed) if the file is missing, unreadable, or does not
    match the contract.
    """
    with open(path or DEFAULT_PATH, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        raise ValueError("Policy config must be a YAML mapping")
    for section, expected in _EXPECTED.items():
        if config.get(section) != expected:
            raise ValueError(f"Policy config section '{section}' does not match the contract")
    return config
