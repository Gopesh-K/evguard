"""Smoke tests for EVGuard FastAPI endpoints."""

import itertools
import json

import pytest
from fastapi.testclient import TestClient

import backend.main as main
from contract.evguard_contract import CONTRACT_VERSION, DECISION_KEYS, SESSION_KEYS
from core.decision import Gateway

_ids = itertools.count(1)


@pytest.fixture
def client(tmp_path, monkeypatch):
    """TestClient wired to a throwaway Gateway seeded like the real app."""
    gw = Gateway(str(tmp_path / "api.db"))
    main.seed_demo_session(gw)
    monkeypatch.setattr(main, "gateway", gw)
    monkeypatch.setattr(main, "sim", None)  # these tests cover standalone mode
    yield TestClient(main.app)
    gw.db.close()


def payload(command_type, value=None, unit=None, session="sess_demo"):
    return {
        "command_id": f"cmd_api_{next(_ids)}",
        "timestamp": "2026-09-19T10:00:00Z",
        "session_id": session,
        "source_id": "controller_A",
        "auth_token": "demo-token-controller-A",
        "command_type": command_type,
        "value": value,
        "unit": unit,
    }


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "contract_version": CONTRACT_VERSION}


def test_demo_session_seeded(client):
    body = client.get("/sessions/sess_demo").json()
    assert list(body) == SESSION_KEYS
    assert (body["vehicle_id"], body["state"], body["max_power_kw"], body["max_current_a"]) == \
        ("Vehicle-01", "DISCONNECTED", 7.0, 32.0)


def test_post_command_returns_decision(client):
    response = client.post("/command", json=payload("CONNECT"))
    assert response.status_code == 200
    body = response.json()
    assert list(body) == DECISION_KEYS
    assert (body["decision"], body["rule_triggered"], body["state_after"]) == \
        ("ALLOW", "ok", "CONNECTED")
    assert "demo-token" not in response.text


def test_excess_power_blocked_via_api(client):
    for ctype in ("CONNECT", "AUTHORIZE_SESSION", "START_CHARGING"):
        assert client.post("/command", json=payload(ctype)).json()["decision"] == "ALLOW"
    body = client.post("/command", json=payload("SET_POWER", 20.0, "kW")).json()
    assert (body["decision"], body["rule_triggered"]) == ("BLOCK", "policy.power_limit")
    assert client.get("/sessions/sess_demo").json()["state"] == "CHARGING"


def test_invalid_state_blocked_via_api(client):
    body = client.post("/command", json=payload("START_CHARGING")).json()
    assert (body["decision"], body["rule_triggered"]) == ("BLOCK", "state.invalid_transition")


def test_malformed_body_returns_422(client):
    bad = payload("CONNECT")
    del bad["session_id"]
    assert client.post("/command", json=bad).status_code == 422
    assert client.post("/command", json={"command_id": "x"}).status_code == 422


def test_commands_listing_and_lookup(client):
    first = client.post("/command", json=payload("CONNECT")).json()
    client.post("/command", json=payload("START_CHARGING"))

    items = client.get("/commands").json()["items"]
    assert [d["command_type"] for d in items] == ["START_CHARGING", "CONNECT"]
    assert client.get("/commands?limit=1").json()["items"] == items[:1]
    assert client.get(f"/commands/{first['command_id']}").json() == first
    assert client.get("/commands/cmd_missing").status_code == 404
    assert client.get("/commands?limit=0").status_code == 422


def test_stats(client):
    client.post("/command", json=payload("CONNECT"))
    client.post("/command", json=payload("START_CHARGING"))
    assert client.get("/stats").json() == {"total": 2, "allowed": 1, "blocked": 1}


def test_sessions_create_reset_and_errors(client):
    client.post("/command", json=payload("CONNECT"))
    reset = client.post("/sessions", json={"session_id": "sess_demo", "vehicle_id": "Vehicle-01",
                                           "max_power_kw": 7.0, "max_current_a": 32.0})
    assert reset.status_code == 200
    assert reset.json()["state"] == "DISCONNECTED"
    assert client.get("/sessions/sess_nope").status_code == 404
    assert client.post("/sessions", json={"session_id": "bad id"}).status_code == 422


def test_scenarios_stubs(client):
    assert client.get("/scenarios").json() == {"items": []}
    assert client.post("/scenarios/excess_power").status_code == 404


def test_baseline_stays_501(client):
    response = client.post("/baseline/command", json=payload("CONNECT"))
    assert response.status_code == 501


# ---- input validation: every malformed command is rejected with 422 at the API layer ----

@pytest.mark.parametrize("command_type, value, unit", [
    ("SET_POWER", "5", "kW"),        # numeric string is not coerced
    ("SET_POWER", True, "kW"),       # boolean is not a number
    ("SET_CURRENT", "16", "A"),
    ("CONNECT", "5", None),          # type errors are command-agnostic
])
def test_generic_type_errors_return_422(client, command_type, value, unit):
    response = client.post("/command", json=payload(command_type, value, unit))
    assert response.status_code == 422
    assert client.get("/stats").json()["total"] == 0  # never reached the engine


@pytest.mark.parametrize("field, value", [("command_id", 5), ("auth_token", None), ("unit", 5)])
def test_wrong_string_types_return_422(client, field, value):
    body = payload("CONNECT")
    body[field] = value
    assert client.post("/command", json=body).status_code == 422


@pytest.mark.parametrize("changes", [
    {"command_type": "SET_POWER", "value": None, "unit": None},       # value required
    {"command_type": "SET_POWER", "value": 5.0, "unit": None},        # unit required
    {"command_type": "SET_POWER", "value": 5.0, "unit": "A"},         # wrong unit
    {"command_type": "SET_CURRENT", "value": 16.0, "unit": "kW"},     # wrong unit
    {"command_type": "CONNECT", "value": 5.0, "unit": "kW"},          # value forbidden
    {"command_type": "CONNECT", "value": None, "unit": "kW"},         # unit forbidden
    {"command_type": "SET_POWER", "value": -5.0, "unit": "kW"},       # not greater than 0
    {"command_type": "SET_POWER", "value": 0, "unit": "kW"},          # not greater than 0
    {"command_type": "NUKE", "value": None, "unit": None},            # not in COMMANDS
    {"command_type": "CONNECT", "session_id": "bad id!"},             # ID pattern
])
def test_command_specific_cases_return_422(client, changes):
    response = client.post("/command", json={**payload("CONNECT"), **changes})
    assert response.status_code == 422
    assert client.get("/stats").json()["total"] == 0  # never reached the engine
    assert "demo-token" not in response.text  # token not echoed


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_value_returns_422(client, token):
    body = json.dumps(payload("SET_POWER", 1.0, "kW")).replace("1.0", token)
    response = client.post("/command", content=body, headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert client.get("/stats").json()["total"] == 0  # never reached the engine
    assert "demo-token" not in response.text  # token not echoed


# ---- 422 responses never echo submitted values ----

def test_nan_with_missing_field_returns_422_not_500(client):
    body = '{"command_id": "cmd_nan_1", "value": NaN}'
    response = client.post("/command", content=body, headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json()["detail"]  # errors are still listed


def test_422_does_not_echo_auth_token_or_input(client):
    bad = payload("CONNECT")
    del bad["session_id"]
    response = client.post("/command", json=bad)
    assert response.status_code == 422
    assert "demo-token-controller-A" not in response.text
    assert "demo-token" not in response.text
    for error in response.json()["detail"]:
        assert set(error) == {"type", "loc", "msg"}
    assert {"type": "missing", "loc": ["body", "session_id"], "msg": "Field required"} in \
        response.json()["detail"]


def test_422_for_wrong_type_does_not_echo_the_submitted_value(client):
    response = client.post("/command", json=payload("SET_POWER", "secret-value-123", "kW"))
    assert response.status_code == 422
    assert "secret-value-123" not in response.text
