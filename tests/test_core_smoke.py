"""Smoke tests for EVGuard FastAPI endpoints."""

import itertools

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
