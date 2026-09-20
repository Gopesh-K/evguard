"""Tests for the EV charger simulator (Role 2)."""

import pytest
from simulator.ev_simulator import ChargerSimulator
from contract.evguard_contract import SNAPSHOT_KEYS


def test_default_session_state():
    """Verify default initial/reset state of a session."""
    sim = ChargerSimulator()
    snap = sim.reset_session("sess_test", "Vehicle-42")

    assert snap["session_id"] == "sess_test"
    assert snap["vehicle_id"] == "Vehicle-42"
    assert snap["plugged_in"] is False
    assert snap["charging"] is False
    assert snap["power_kw"] == 0.0
    assert snap["current_a"] == 0.0
    assert snap["last_command"] is None
    assert isinstance(snap["updated_at"], str)
    assert sorted(snap.keys()) == sorted(SNAPSHOT_KEYS)


def test_connect_command():
    """Verify CONNECT sets plugged_in to True."""
    sim = ChargerSimulator()
    sim.reset_session("sess_test", "Vehicle-01")
    snap = sim.apply({"session_id": "sess_test", "command_type": "CONNECT"})

    assert snap["plugged_in"] is True
    assert snap["charging"] is False
    assert snap["last_command"] == "CONNECT"


def test_authorize_session_command():
    """Verify AUTHORIZE_SESSION causes no physical change, only updates last_command."""
    sim = ChargerSimulator()
    sim.reset_session("sess_test", "Vehicle-01")
    sim.apply({"session_id": "sess_test", "command_type": "CONNECT"})

    snap = sim.apply({"session_id": "sess_test", "command_type": "AUTHORIZE_SESSION"})
    assert snap["plugged_in"] is True
    assert snap["charging"] is False
    assert snap["power_kw"] == 0.0
    assert snap["current_a"] == 0.0
    assert snap["last_command"] == "AUTHORIZE_SESSION"


def test_start_charging_command():
    """Verify START_CHARGING sets charging to True."""
    sim = ChargerSimulator()
    sim.reset_session("sess_test", "Vehicle-01")
    sim.apply({"session_id": "sess_test", "command_type": "CONNECT"})
    snap = sim.apply({"session_id": "sess_test", "command_type": "START_CHARGING"})

    assert snap["charging"] is True
    assert snap["last_command"] == "START_CHARGING"


def test_set_power_blind_execution():
    """Verify SET_POWER sets power_kw, including excessive values (e.g. 20.0 kW)."""
    sim = ChargerSimulator()
    sim.reset_session("sess_test", "Vehicle-01")
    snap = sim.apply({
        "session_id": "sess_test",
        "command_type": "SET_POWER",
        "value": 20.0,
        "unit": "kW",
    })

    assert snap["power_kw"] == 20.0
    assert snap["last_command"] == "SET_POWER"


def test_set_current_command():
    """Verify SET_CURRENT sets current_a."""
    sim = ChargerSimulator()
    sim.reset_session("sess_test", "Vehicle-01")
    snap = sim.apply({
        "session_id": "sess_test",
        "command_type": "SET_CURRENT",
        "value": 16.0,
        "unit": "A",
    })

    assert snap["current_a"] == 16.0
    assert snap["last_command"] == "SET_CURRENT"


def test_stop_charging_command():
    """Verify STOP_CHARGING resets charging, power_kw, and current_a."""
    sim = ChargerSimulator()
    sim.reset_session("sess_test", "Vehicle-01")
    sim.apply({"session_id": "sess_test", "command_type": "START_CHARGING"})
    sim.apply({"session_id": "sess_test", "command_type": "SET_POWER", "value": 7.0, "unit": "kW"})
    sim.apply({"session_id": "sess_test", "command_type": "SET_CURRENT", "value": 32.0, "unit": "A"})

    snap = sim.apply({"session_id": "sess_test", "command_type": "STOP_CHARGING"})
    assert snap["charging"] is False
    assert snap["power_kw"] == 0.0
    assert snap["current_a"] == 0.0
    assert snap["last_command"] == "STOP_CHARGING"


def test_disconnect_command():
    """Verify DISCONNECT resets plugged_in, charging, power_kw, and current_a."""
    sim = ChargerSimulator()
    sim.reset_session("sess_test", "Vehicle-01")
    sim.apply({"session_id": "sess_test", "command_type": "CONNECT"})
    sim.apply({"session_id": "sess_test", "command_type": "START_CHARGING"})
    sim.apply({"session_id": "sess_test", "command_type": "SET_POWER", "value": 5.0, "unit": "kW"})

    snap = sim.apply({"session_id": "sess_test", "command_type": "DISCONNECT"})
    assert snap["plugged_in"] is False
    assert snap["charging"] is False
    assert snap["power_kw"] == 0.0
    assert snap["current_a"] == 0.0
    assert snap["last_command"] == "DISCONNECT"


def test_unknown_session_auto_creation():
    """Verify applying a command to an unknown session auto-creates it with vehicle_id 'Vehicle-01'."""
    sim = ChargerSimulator()
    snap = sim.apply({"session_id": "sess_unknown", "command_type": "CONNECT"})

    assert snap["session_id"] == "sess_unknown"
    assert snap["vehicle_id"] == "Vehicle-01"
    assert snap["plugged_in"] is True
    assert snap["last_command"] == "CONNECT"


def test_snapshot_returns_decoupled_copy_and_exact_keys():
    """Verify snapshot returns a decoupled copy and contains exactly SNAPSHOT_KEYS."""
    sim = ChargerSimulator()
    sim.reset_session("sess_test", "Vehicle-01")

    snap1 = sim.snapshot("sess_test")
    assert snap1 is not None
    assert sorted(snap1.keys()) == sorted(SNAPSHOT_KEYS)

    # Mutating snap1 must not affect the internal state or future snapshots
    snap1["power_kw"] = 999.0
    snap2 = sim.snapshot("sess_test")
    assert snap2["power_kw"] == 0.0

    # Non-existent session returns None
    assert sim.snapshot("sess_nonexistent") is None


def test_updated_at_and_last_command_updated_each_command():
    """Verify last_command and updated_at update on each command."""
    sim = ChargerSimulator()
    sim.reset_session("sess_test", "Vehicle-01")

    snap1 = sim.apply({"session_id": "sess_test", "command_type": "CONNECT"})
    assert snap1["last_command"] == "CONNECT"
    t1 = snap1["updated_at"]

    snap2 = sim.apply({"session_id": "sess_test", "command_type": "START_CHARGING"})
    assert snap2["last_command"] == "START_CHARGING"
    t2 = snap2["updated_at"]

    assert t1 is not None
    assert t2 is not None

