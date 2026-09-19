"""Tests for core/policy_engine.py."""

from core.policy_engine import check_limits

SESSION = {"max_power_kw": 7.0, "max_current_a": 32.0}


def cmd(command_type, value, unit):
    return {"command_type": command_type, "value": value, "unit": unit}


def test_power_below_limit_allowed():
    assert check_limits(cmd("SET_POWER", 5.0, "kW"), SESSION) == (True, "ok", "")


def test_power_at_limit_allowed():
    assert check_limits(cmd("SET_POWER", 7.0, "kW"), SESSION) == (True, "ok", "")


def test_power_over_limit_blocked():
    ok, rule, reason = check_limits(cmd("SET_POWER", 20.0, "kW"), SESSION)
    assert (ok, rule) == (False, "policy.power_limit")
    assert reason == "Requested power 20.0 kW exceeds session maximum of 7.0 kW"


def test_current_over_limit_blocked():
    ok, rule, reason = check_limits(cmd("SET_CURRENT", 40.0, "A"), SESSION)
    assert (ok, rule) == (False, "policy.current_limit")
    assert reason == "Requested current 40.0 A exceeds session maximum of 32.0 A"


def test_current_16a_allowed_despite_7kw_power_limit():
    # Units must never be mixed: 16 A is checked against 32 A, not 7 kW.
    assert check_limits(cmd("SET_CURRENT", 16.0, "A"), SESSION) == (True, "ok", "")


def test_non_value_command_passes():
    command = {"command_type": "CONNECT", "value": None, "unit": None}
    assert check_limits(command, SESSION) == (True, "ok", "")
