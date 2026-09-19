"""Tests for core/auth.py and core/authz.py."""

import pytest

from contract.evguard_contract import COMMANDS, DEMO_SOURCES
from core.auth import authenticate
from core.authz import authorize


def cmd(source_id, token):
    return {"source_id": source_id, "auth_token": token}


def test_valid_controller():
    token = DEMO_SOURCES["controller_A"]["token"]
    assert authenticate(cmd("controller_A", token)) == (True, "ok", "", "controller")


def test_valid_monitor():
    token = DEMO_SOURCES["monitor_01"]["token"]
    assert authenticate(cmd("monitor_01", token)) == (True, "ok", "", "monitor")


@pytest.mark.parametrize("token", [None, ""])
def test_missing_token(token):
    ok, rule, _, role = authenticate(cmd("controller_A", token))
    assert (ok, rule, role) == (False, "auth.missing_token", None)


def test_missing_token_key():
    ok, rule, _, _ = authenticate({"source_id": "controller_A"})
    assert (ok, rule) == (False, "auth.missing_token")


def test_invalid_token():
    ok, rule, _, role = authenticate(cmd("controller_A", "bad-token"))
    assert (ok, rule, role) == (False, "auth.invalid_token", None)


def test_unknown_source():
    ok, rule, _, role = authenticate(cmd("ghost", "bad-token"))
    assert (ok, rule, role) == (False, "auth.invalid_token", None)


def test_source_mismatch():
    # controller_A presents monitor_01's (valid) token.
    token = DEMO_SOURCES["monitor_01"]["token"]
    ok, rule, _, role = authenticate(cmd("controller_A", token))
    assert (ok, rule, role) == (False, "auth.source_mismatch", None)


def test_token_never_in_reason():
    for token in ["bad-token", DEMO_SOURCES["monitor_01"]["token"]]:
        _, _, reason, _ = authenticate(cmd("controller_A", token))
        assert token not in reason


@pytest.mark.parametrize("command_type", COMMANDS)
def test_controller_permitted_for_every_command(command_type):
    assert authorize("controller", command_type) == (True, "ok", "")


def test_monitor_connect_not_permitted():
    # monitor_01 authenticates fine, but authz blocks CONNECT.
    token = DEMO_SOURCES["monitor_01"]["token"]
    ok, _, _, role = authenticate(cmd("monitor_01", token))
    assert ok and role == "monitor"
    ok, rule, _ = authorize(role, "CONNECT")
    assert (ok, rule) == (False, "authz.command_not_permitted")


@pytest.mark.parametrize("command_type", COMMANDS)
def test_monitor_blocked_for_every_command(command_type):
    ok, rule, _ = authorize("monitor", command_type)
    assert (ok, rule) == (False, "authz.command_not_permitted")


def test_unknown_role_blocked():
    ok, rule, _ = authorize("hacker", "CONNECT")
    assert (ok, rule) == (False, "authz.command_not_permitted")
