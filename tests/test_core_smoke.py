"""Smoke test for EVGuard FastAPI endpoints."""

from fastapi.testclient import TestClient

from backend.main import app
from contract.evguard_contract import CONTRACT_VERSION

client = TestClient(app)


def test_health_endpoint():
    """Verify GET /health returns status 200 and contract version."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "contract_version": CONTRACT_VERSION,
    }


def test_post_command_fails_closed_with_501():
    """Verify POST /command returns HTTP 501 with 'engine not implemented'."""
    cmd_payload = {
        "command_id": "cmd_smoke_01",
        "timestamp": "2026-09-19T10:00:00Z",
        "session_id": "sess_smoke",
        "source_id": "controller_A",
        "auth_token": "demo-token-controller-A",
        "command_type": "CONNECT",
        "value": None,
        "unit": None,
    }
    response = client.post("/command", json=cmd_payload)
    assert response.status_code == 501
    assert response.json() == {"detail": "engine not implemented"}


def test_post_baseline_command_fails_closed_with_501():
    """Verify POST /baseline/command returns HTTP 501 with 'engine not implemented'."""
    cmd_payload = {
        "command_id": "cmd_smoke_02",
        "timestamp": "2026-09-19T10:00:00Z",
        "session_id": "sess_smoke",
        "source_id": "controller_A",
        "auth_token": "demo-token-controller-A",
        "command_type": "CONNECT",
        "value": None,
        "unit": None,
    }
    response = client.post("/baseline/command", json=cmd_payload)
    assert response.status_code == 501
    assert response.json() == {"detail": "engine not implemented"}


def test_post_sessions_fails_closed_with_501():
    """Verify POST /sessions returns HTTP 501 with 'engine not implemented'."""
    session_payload = {
        "session_id": "sess_smoke",
        "vehicle_id": "Vehicle-01",
        "max_power_kw": 7.0,
        "max_current_a": 32.0,
    }
    response = client.post("/sessions", json=session_payload)
    assert response.status_code == 501
    assert response.json() == {"detail": "engine not implemented"}
