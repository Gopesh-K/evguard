"""Tests for core/decision.py Gateway."""

import itertools
import json
import sqlite3

import pytest

import core.decision as decision_module
from contract.evguard_contract import (
    DECISION_KEYS, DEMO_SOURCES, RATE_MAX_COMMANDS, SESSION_KEYS, SNAPSHOT_KEYS,
)
from core.decision import Gateway

SESSION = {"session_id": "sess_t", "vehicle_id": "Vehicle-01",
           "max_power_kw": 7.0, "max_current_a": 32.0}
CONTROLLER = "controller_A"
_ids = itertools.count(1)


class FakeSimulator:
    """Records what the gateway sends; does no checks."""

    def __init__(self):
        self.applied = []
        self.resets = []

    def reset_session(self, session_id, vehicle_id):
        self.resets.append((session_id, vehicle_id))
        return {}

    def apply(self, command):
        self.applied.append(command)
        return {}

    def snapshot(self, session_id):
        return None


@pytest.fixture
def sim():
    return FakeSimulator()


@pytest.fixture
def gw(tmp_path, sim):
    gateway = Gateway(str(tmp_path / "test.db"), simulator=sim)
    gateway.create_session(SESSION)
    yield gateway
    gateway.db.close()


def cmd(command_type, value=None, unit=None, source=CONTROLLER, token=None,
        session="sess_t", command_id=None):
    return {
        "command_id": command_id or f"cmd_{next(_ids)}",
        "timestamp": None,
        "session_id": session,
        "source_id": source,
        "auth_token": token if token is not None else DEMO_SOURCES[source]["token"],
        "command_type": command_type,
        "value": value,
        "unit": unit,
    }


def to_charging(gw):
    for ctype in ("CONNECT", "AUTHORIZE_SESSION", "START_CHARGING"):
        assert gw.handle(cmd(ctype))["decision"] == "ALLOW"


def test_full_lifecycle_all_allow(gw, sim):
    steps = [("CONNECT", None, None), ("AUTHORIZE_SESSION", None, None),
             ("START_CHARGING", None, None), ("SET_POWER", 7.0, "kW"),
             ("STOP_CHARGING", None, None), ("DISCONNECT", None, None)]
    expected_states = ["CONNECTED", "AUTHORIZED", "CHARGING", "CHARGING", "STOPPED", "DISCONNECTED"]
    for (ctype, value, unit), state in zip(steps, expected_states):
        d = gw.handle(cmd(ctype, value, unit))
        assert (d["decision"], d["rule_triggered"], d["state_after"]) == ("ALLOW", "ok", state)
    assert len(sim.applied) == len(steps)
    assert gw.get_session("sess_t")["state"] == "DISCONNECTED"

    # Contract full_lifecycle step 7: a second DISCONNECT is an invalid transition.
    d = gw.handle(cmd("DISCONNECT"))
    assert (d["decision"], d["rule_triggered"]) == ("BLOCK", "state.invalid_transition")


def test_readme_demo_sequence_back_to_back_never_rate_limited(gw):
    demo = [
        ("CONNECT", None, None, "ALLOW", "ok"),
        ("AUTHORIZE_SESSION", None, None, "ALLOW", "ok"),
        ("START_CHARGING", None, None, "ALLOW", "ok"),
        ("SET_POWER", 5.0, "kW", "ALLOW", "ok"),
        ("SET_POWER", 20.0, "kW", "BLOCK", "policy.power_limit"),
        ("STOP_CHARGING", None, None, "ALLOW", "ok"),
        ("DISCONNECT", None, None, "ALLOW", "ok"),
        ("START_CHARGING", None, None, "BLOCK", "state.invalid_transition"),
    ]
    for ctype, value, unit, expected, rule in demo:
        d = gw.handle(cmd(ctype, value, unit))
        assert (d["decision"], d["rule_triggered"]) == (expected, rule), ctype
    assert all(d["rule_triggered"] != "sequence.rate_exceeded" for d in gw.recent_decisions(50))


def test_excess_power_blocked_and_setpoint_unchanged(gw, sim):
    to_charging(gw)
    assert gw.handle(cmd("SET_POWER", 5.0, "kW"))["decision"] == "ALLOW"
    applied_before = len(sim.applied)

    d = gw.handle(cmd("SET_POWER", 20.0, "kW"))
    assert (d["decision"], d["rule_triggered"]) == ("BLOCK", "policy.power_limit")
    assert d["reason"] == "Requested power 20.0 kW exceeds session maximum of 7.0 kW"
    assert d["state_before"] == d["state_after"] == "CHARGING"
    assert len(sim.applied) == applied_before          # simulator not touched
    assert gw.db.get_session("sess_t")["current_power_kw"] == 5.0


def test_start_charging_while_disconnected_blocked(gw, sim):
    d = gw.handle(cmd("START_CHARGING"))
    assert (d["decision"], d["rule_triggered"]) == ("BLOCK", "state.invalid_transition")
    assert d["state_before"] == d["state_after"] == "DISCONNECTED"
    assert sim.applied == []


def test_rate_burst_steps_1_to_10_allow_11_to_15_block(gw):
    steps = [cmd("CONNECT"), cmd("AUTHORIZE_SESSION"), cmd("START_CHARGING")]
    steps += [cmd("SET_POWER", 5.0, "kW") for _ in range(12)]
    results = [gw.handle(c) for c in steps]
    for d in results[:10]:
        assert (d["decision"], d["rule_triggered"]) == ("ALLOW", "ok")
    for d in results[10:]:
        assert (d["decision"], d["rule_triggered"]) == ("BLOCK", "sequence.rate_exceeded")
        assert d["state_before"] == d["state_after"] == "CHARGING"


def test_blocked_commands_count_toward_rate_and_state_wins_over_rate(gw):
    for _ in range(RATE_MAX_COMMANDS):
        assert gw.handle(cmd("START_CHARGING"))["rule_triggered"] == "state.invalid_transition"
    # The next command is valid, but the window is full of (blocked) commands.
    assert gw.handle(cmd("CONNECT"))["rule_triggered"] == "sequence.rate_exceeded"
    # An invalid transition is still reported as a state problem, not a rate one.
    assert gw.handle(cmd("START_CHARGING"))["rule_triggered"] == "state.invalid_transition"


def test_create_session_clears_rate_window_and_resets_state(gw, sim):
    to_charging(gw)
    for _ in range(RATE_MAX_COMMANDS - 3):
        gw.handle(cmd("SET_POWER", 5.0, "kW"))
    assert gw.handle(cmd("SET_POWER", 5.0, "kW"))["rule_triggered"] == "sequence.rate_exceeded"

    session = gw.create_session(SESSION)
    assert session["state"] == "DISCONNECTED"
    assert sim.resets[-1] == ("sess_t", "Vehicle-01")
    assert gw.handle(cmd("CONNECT"))["decision"] == "ALLOW"


def test_reused_command_id_blocked(gw):
    first = gw.handle(cmd("CONNECT", command_id="cmd_dup"))
    assert first["decision"] == "ALLOW"
    second = gw.handle(cmd("CONNECT", command_id="cmd_dup"))
    assert (second["decision"], second["rule_triggered"]) == ("BLOCK", "sequence.duplicate_command_id")
    # The original decision is still the one returned for that ID.
    assert gw.get_decision("cmd_dup")["decision"] == "ALLOW"
    assert gw.stats()["total"] == 2


def test_unknown_session_blocked(gw):
    d = gw.handle(cmd("CONNECT", session="sess_nope"))
    assert (d["decision"], d["rule_triggered"]) == ("BLOCK", "session.unknown")


def test_auth_failures_reveal_no_state(gw):
    d = gw.handle(cmd("CONNECT", token="bad-token"))
    assert (d["rule_triggered"], d["state_before"], d["state_after"]) == \
        ("auth.invalid_token", None, None)


def test_monitor_connect_blocked_by_authz(gw):
    d = gw.handle(cmd("CONNECT", source="monitor_01"))
    assert (d["decision"], d["rule_triggered"]) == ("BLOCK", "authz.command_not_permitted")
    assert d["state_before"] == d["state_after"] == "DISCONNECTED"


def test_source_mismatch_blocked(gw):
    d = gw.handle(cmd("CONNECT", token=DEMO_SOURCES["monitor_01"]["token"]))
    assert d["rule_triggered"] == "auth.source_mismatch"


@pytest.mark.parametrize("bad", [
    "not a dict",
    None,
    {},
    {"command_id": "cmd_x"},
    {**cmd("NUKE")},
    {**cmd("SET_POWER"), "value": None},
    {**cmd("SET_POWER", 5.0, "A")},
    {**cmd("SET_POWER", -5.0, "kW")},
    {**cmd("SET_POWER", 0.0, "kW")},
    {**cmd("SET_POWER", float("nan"), "kW")},
    {**cmd("SET_POWER", float("inf"), "kW")},
    {**cmd("SET_POWER", "5", "kW")},
    {**cmd("SET_POWER", True, "kW")},
    {**cmd("SET_CURRENT", 16.0, "kW")},
    {**cmd("CONNECT", 5.0, "kW")},
    {**cmd("CONNECT"), "session_id": "bad id!"},
    {**cmd("CONNECT"), "auth_token": ["x"]},
])
def test_malformed_input_blocked_never_raises(gw, bad):
    d = gw.handle(bad)
    assert (d["decision"], d["rule_triggered"]) == ("BLOCK", "input.invalid")
    assert list(d) == DECISION_KEYS


def test_missing_token_reaches_auth(gw):
    c = cmd("CONNECT")
    c["auth_token"] = ""
    assert gw.handle(c)["rule_triggered"] == "auth.missing_token"


def test_internal_error_fails_closed_state_unchanged(gw, sim, monkeypatch):
    to_charging(gw)
    applied_before = len(sim.applied)

    def boom(command, session):
        raise RuntimeError("boom")

    monkeypatch.setattr(decision_module, "check_limits", boom)
    d = gw.handle(cmd("SET_POWER", 5.0, "kW"))
    assert (d["decision"], d["rule_triggered"]) == ("BLOCK", "engine.internal_error")
    assert d["state_before"] == d["state_after"] == "CHARGING"
    assert list(d) == DECISION_KEYS
    assert len(sim.applied) == applied_before
    assert gw.get_session("sess_t")["state"] == "CHARGING"
    assert gw.recent_decisions(1)[0]["rule_triggered"] == "engine.internal_error"


def test_internal_error_before_session_lookup_still_returns_block(gw, monkeypatch):
    def boom(command):
        raise RuntimeError("boom")

    monkeypatch.setattr(decision_module, "authenticate", boom)
    d = gw.handle(cmd("CONNECT"))
    assert (d["decision"], d["rule_triggered"]) == ("BLOCK", "engine.internal_error")


def test_simulator_failure_fails_closed_state_unchanged(gw, sim, monkeypatch):
    def boom(command):
        raise RuntimeError("charger offline")

    monkeypatch.setattr(sim, "apply", boom)
    d = gw.handle(cmd("CONNECT"))
    assert d["rule_triggered"] == "engine.internal_error"
    assert gw.get_session("sess_t")["state"] == "DISCONNECTED"


def test_token_never_stored_or_returned(gw, tmp_path):
    tokens = [s["token"] for s in DEMO_SOURCES.values()] + ["bad-token"]
    decisions = [
        gw.handle(cmd("CONNECT")),                                        # ALLOW
        gw.handle(cmd("CONNECT", token="bad-token")),                     # auth.invalid_token
        gw.handle(cmd("CONNECT", token=DEMO_SOURCES["monitor_01"]["token"])),  # mismatch
        gw.handle(cmd("CONNECT", source="monitor_01")),                   # authz
        gw.handle({**cmd("CONNECT", token="bad-token"), "command_type": "NUKE"}),  # input
    ]
    blob = json.dumps(decisions) + json.dumps(gw.recent_decisions(100))
    blob += json.dumps(gw.get_session("sess_t"))

    conn = sqlite3.connect(str(tmp_path / "test.db"))
    for (table,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall():
        for row in conn.execute(f"SELECT * FROM {table}").fetchall():  # noqa: S608 (test only)
            blob += json.dumps([str(c) for c in row])
    conn.close()

    for token in tokens:
        assert token not in blob


def test_every_decision_has_exactly_decision_keys(gw):
    to_charging(gw)
    decisions = [
        gw.handle(cmd("SET_POWER", 5.0, "kW")),
        gw.handle(cmd("SET_POWER", 20.0, "kW")),
        gw.handle(cmd("CONNECT", token="bad-token")),
        gw.handle(cmd("CONNECT", session="sess_nope")),
        gw.handle("junk"),
    ]
    for d in decisions + gw.recent_decisions(100):
        assert list(d) == DECISION_KEYS


def test_get_session_shape_with_and_without_simulator(gw, tmp_path):
    session = gw.get_session("sess_t")
    assert list(session) == SESSION_KEYS
    assert list(session["physical"]) == SNAPSHOT_KEYS
    assert gw.get_session("sess_nope") is None

    bare = Gateway(str(tmp_path / "bare.db"))
    bare.create_session(SESSION)
    physical = bare.get_session("sess_t")["physical"]
    assert list(physical) == SNAPSHOT_KEYS
    assert (physical["plugged_in"], physical["charging"], physical["power_kw"],
            physical["current_a"]) == (False, False, 0.0, 0.0)
    bare.db.close()


def test_recent_decisions_newest_first_and_stats(gw):
    gw.handle(cmd("CONNECT"))
    gw.handle(cmd("START_CHARGING"))
    recent = gw.recent_decisions(10)
    assert [d["command_type"] for d in recent] == ["START_CHARGING", "CONNECT"]
    assert gw.stats() == {"total": 2, "allowed": 1, "blocked": 1}


@pytest.mark.parametrize("bad", [
    None, {}, {"session_id": "s", "vehicle_id": "v", "max_power_kw": -1},
    {"session_id": "bad id", "vehicle_id": "v"},
    {"session_id": "s", "vehicle_id": "v", "max_current_a": "x"},
])
def test_create_session_rejects_bad_definition(gw, bad):
    with pytest.raises(ValueError):
        gw.create_session(bad)
