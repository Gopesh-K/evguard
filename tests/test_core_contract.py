"""Tests verifying contract internal consistency and configuration alignment."""

from pathlib import Path
import yaml

from contract.evguard_contract import (
    CHECK_ORDER,
    COMMANDS,
    DEFAULT_MAX_CURRENT_A,
    DEFAULT_MAX_POWER_KW,
    DEMO_SOURCES,
    RATE_MAX_COMMANDS,
    RATE_WINDOW_SECONDS,
    ROLE_PERMISSIONS,
    RULES,
    STATES,
    TRANSITIONS,
    VALUE_COMMANDS,
)


def test_transitions_states_and_commands():
    """Verify every state and command in TRANSITIONS exists in STATES and COMMANDS."""
    for (state, cmd), next_state in TRANSITIONS.items():
        assert state in STATES, f"Source state '{state}' not in STATES"
        assert cmd in COMMANDS, f"Transition command '{cmd}' not in COMMANDS"
        assert next_state in STATES, f"Target state '{next_state}' not in STATES"


def test_value_commands_in_commands():
    """Verify every command in VALUE_COMMANDS is registered in COMMANDS."""
    for cmd, unit in VALUE_COMMANDS.items():
        assert cmd in COMMANDS, f"Value command '{cmd}' not in COMMANDS"
        assert unit in {"kW", "A"}, f"Unexpected unit '{unit}' for value command"


def test_check_order_rules_and_roles():
    """Verify CHECK_ORDER, RULES, and DEMO_SOURCES are consistent with ROLE_PERMISSIONS."""
    # Check that each check prefix corresponds to known rule namespaces
    known_namespaces = {
        rule.split(".")[0] for rule in RULES.keys() if "." in rule
    }
    for check in CHECK_ORDER:
        assert (
            check in known_namespaces
        ), f"Check '{check}' from CHECK_ORDER has no corresponding rules in RULES"

    # Check that roles in DEMO_SOURCES are defined in ROLE_PERMISSIONS
    for source_id, identity in DEMO_SOURCES.items():
        role = identity["role"]
        assert (
            role in ROLE_PERMISSIONS
        ), f"Source '{source_id}' has role '{role}' not in ROLE_PERMISSIONS"

    # Check that commands permitted for any role are in COMMANDS
    for role, allowed_commands in ROLE_PERMISSIONS.items():
        for cmd in allowed_commands:
            assert (
                cmd in COMMANDS
            ), f"Role '{role}' allows unknown command '{cmd}'"


def test_policy_rules_yaml_matches_contract():
    """Verify that config/policy_rules.yaml matches contract constants."""
    yaml_path = Path(__file__).resolve().parent.parent / "config" / "policy_rules.yaml"
    assert yaml_path.exists(), f"Configuration file not found at {yaml_path}"

    with open(yaml_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    assert config is not None, "Configuration YAML is empty"
    assert "defaults" in config, "Missing 'defaults' in policy_rules.yaml"
    assert "sequence" in config, "Missing 'sequence' in policy_rules.yaml"
    assert "roles" in config, "Missing 'roles' in policy_rules.yaml"

    assert config["defaults"]["max_power_kw"] == DEFAULT_MAX_POWER_KW
    assert config["defaults"]["max_current_a"] == DEFAULT_MAX_CURRENT_A
    assert config["sequence"]["window_seconds"] == RATE_WINDOW_SECONDS
    assert config["sequence"]["max_commands_per_source"] == RATE_MAX_COMMANDS
    assert config["roles"] == ROLE_PERMISSIONS

