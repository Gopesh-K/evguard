"""Tests for the unprotected baseline charger execution (Role 2)."""

import pytest
from contract.evguard_contract import SNAPSHOT_KEYS
from simulator.baseline import baseline_apply


def test_baseline_apply_structure_and_keys():
    """Verify baseline_apply returns exact top-level keys and contract snapshot fields."""
    cmd = {
        "session_id": "baseline-struct-test",
        "command_type": "CONNECT",
    }
    result = baseline_apply(cmd)

    # 1. Exact top-level keys
    assert set(result.keys()) == {"mode", "accepted", "snapshot"}

    # 2. Field values
    assert result["mode"] == "baseline"
    assert result["accepted"] is True

    # 4. Snapshot fields match contract SNAPSHOT_KEYS
    snap = result["snapshot"]
    assert sorted(snap.keys()) == sorted(SNAPSHOT_KEYS)
    assert snap["session_id"] == "baseline-struct-test"
    assert snap["plugged_in"] is True
    assert snap["last_command"] == "CONNECT"


def test_baseline_apply_unsafe_set_power():
    """Verify baseline directly executes 20.0 kW without rejection."""
    cmd = {
        "session_id": "baseline-test",
        "command_type": "SET_POWER",
        "value": 20.0,
        "unit": "kW",
    }
    result = baseline_apply(cmd)

    # Top-level verification
    assert result["mode"] == "baseline"
    assert result["accepted"] is True

    # 3. & 5. Verify direct execution of 20 kW without security rejection
    assert result["snapshot"]["power_kw"] == 20.0
    assert result["snapshot"]["last_command"] == "SET_POWER"
    assert sorted(result["snapshot"].keys()) == sorted(SNAPSHOT_KEYS)

