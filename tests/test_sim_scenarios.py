"""Tests for scenario tooling, loader, and runner (Role 2)."""

import pytest
from contract.evguard_contract import (
    COMMAND_KEYS,
    COMMANDS,
    RULES,
    VALUE_COMMANDS,
    ALLOW,
    BLOCK,
)
from simulator.scenarios import (
    make_command,
    list_scenarios,
    load_scenario,
    run_scenario,
)


def test_make_command_structure_and_values():
    """Verify make_command generates exact keys, unique IDs, timestamps, and preserves values."""
    cmd1 = make_command(
        session_id="sess_01",
        source_id="controller_A",
        auth_token="demo-token",
        command_type="SET_POWER",
        value=5.0,
        unit="kW",
    )
    cmd2 = make_command(
        session_id="sess_01",
        source_id="controller_A",
        auth_token="demo-token",
        command_type="SET_POWER",
        value=5.0,
        unit="kW",
    )

    # Exact keys match contract
    assert list(cmd1.keys()) == COMMAND_KEYS

    # Fields populated properly
    assert cmd1["session_id"] == "sess_01"
    assert cmd1["source_id"] == "controller_A"
    assert cmd1["auth_token"] == "demo-token"
    assert cmd1["command_type"] == "SET_POWER"
    assert cmd1["value"] == 5.0
    assert cmd1["unit"] == "kW"
    assert isinstance(cmd1["command_id"], str) and cmd1["command_id"].startswith("cmd_")
    assert isinstance(cmd1["timestamp"], str) and len(cmd1["timestamp"]) > 0

    # IDs must be unique
    assert cmd1["command_id"] != cmd2["command_id"]


def test_list_scenarios():
    """Verify list_scenarios returns MUST scenarios sorted deterministically."""
    scenarios = list_scenarios()
    names = [s["name"] for s in scenarios]

    # Must contain the three MUST scenarios
    assert "excess_power" in names
    assert "invalid_state" in names
    assert "normal_session" in names

    # Deterministic alphabetical ordering
    assert names == sorted(names)

    # Each entry contains name, title, description
    for s in scenarios:
        assert "name" in s
        assert "title" in s
        assert "description" in s


def test_load_scenario_must_scenarios():
    """Verify load_scenario loads the three MUST scenarios correctly."""
    for name in ["normal_session", "excess_power", "invalid_state"]:
        scen = load_scenario(name)
        assert scen["name"] == name
        assert isinstance(scen["title"], str)
        assert isinstance(scen["description"], str)
        assert isinstance(scen["session"], dict)
        assert isinstance(scen["steps"], list)
        assert len(scen["steps"]) > 0


def test_load_scenario_nonexistent_raises_exception():
    """Verify loading a nonexistent scenario raises ValueError."""
    with pytest.raises(ValueError):
        load_scenario("non_existent_scenario_12345")


def test_must_scenarios_expectations():
    """Verify step counts and expectations for the MUST scenarios."""
    # 1. normal_session: 4 steps, all ALLOW / ok
    normal = load_scenario("normal_session")
    assert len(normal["steps"]) == 4
    for step in normal["steps"]:
        assert step["expect"] == ALLOW
        assert step["expect_rule"] == "ok"

    # 2. excess_power: 4 steps, final step expects BLOCK / policy.power_limit
    excess = load_scenario("excess_power")
    assert len(excess["steps"]) == 4
    assert excess["steps"][-1]["expect"] == BLOCK
    assert excess["steps"][-1]["expect_rule"] == "policy.power_limit"

    # 3. invalid_state: 1 step, expects BLOCK / state.invalid_transition
    invalid = load_scenario("invalid_state")
    assert len(invalid["steps"]) == 1
    assert invalid["steps"][0]["expect"] == BLOCK
    assert invalid["steps"][0]["expect_rule"] == "state.invalid_transition"


@pytest.mark.parametrize("name", ["normal_session", "excess_power", "invalid_state"])
def test_run_scenario_with_fake_gateway(name):
    """Verify run_scenario executes against a fake gateway recording calls and validating flow."""
    scen = load_scenario(name)
    recorded_sessions = []
    recorded_commands = []
    answers = iter(scen["steps"])

    def fake_create_session(session_def):
        recorded_sessions.append(session_def)

    def fake_send(command):
        recorded_commands.append(command)
        step = next(answers)
        return {
            "command_id": command["command_id"],
            "session_id": command["session_id"],
            "source_id": command["source_id"],
            "command_type": command["command_type"],
            "value": command["value"],
            "unit": command["unit"],
            "decision": step["expect"],
            "rule_triggered": step["expect_rule"],
            "reason": "Mock decision for testing",
            "state_before": "DISCONNECTED",
            "state_after": "DISCONNECTED",
            "received_at": "2026-09-20T10:00:00Z",
        }

    result = run_scenario(name, fake_send, fake_create_session)

    # 1. Verification of scenario result structure
    assert result["scenario"] == name
    assert result["session_id"] == scen["session"]["session_id"]
    assert result["passed"] is True
    assert len(result["results"]) == len(scen["steps"])

    # 2. Verification that create_session was called once
    assert len(recorded_sessions) == 1
    assert recorded_sessions[0] == scen["session"]

    # 3. Verification of commands dispatched
    assert len(recorded_commands) == len(scen["steps"])
    for idx, (cmd, step) in enumerate(zip(recorded_commands, scen["steps"])):
        # Exact keys
        assert list(cmd.keys()) == COMMAND_KEYS
        # Session ID automatically injected from scenario session
        assert cmd["session_id"] == scen["session"]["session_id"]
        # Unique command_id and timestamp generated
        assert cmd["command_id"].startswith("cmd_")
        assert len(cmd["timestamp"]) > 0
        # Command type and parameters match scenario step
        assert cmd["command_type"] == step["command_type"]
        assert cmd["source_id"] == step["source_id"]
        assert cmd["auth_token"] == step["auth_token"]
        assert cmd["value"] == step.get("value")
        assert cmd["unit"] == step.get("unit")


def test_all_scenario_files_contract_compliance():
    """Verify all scenario files in scenario_data conform strictly to the contract."""
    for s_meta in list_scenarios():
        scen = load_scenario(s_meta["name"])
        assert "name" in scen and "title" in scen and "description" in scen
        assert "session" in scen and "steps" in scen
        assert "session_id" in scen["session"]

        for step in scen["steps"]:
            # Prohibited keys in steps (must be injected by runner)
            assert "command_id" not in step
            assert "timestamp" not in step
            assert "session_id" not in step

            # Valid command types and decisions
            assert step["command_type"] in COMMANDS
            assert step["expect"] in [ALLOW, BLOCK]
            assert step["expect_rule"] in RULES

            # Value commands consistency
            if step["command_type"] in VALUE_COMMANDS:
                assert "value" in step
                assert step.get("unit") == VALUE_COMMANDS[step["command_type"]]
            else:
                assert "value" not in step
                assert "unit" not in step

