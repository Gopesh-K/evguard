"""Tests for backend/main.py simulator detection: standalone and integrated modes."""

import sys
from types import ModuleType, SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import backend.main as main
from core.decision import Gateway

SIM_MODULES = ("simulator", "simulator.ev_simulator", "simulator.scenarios", "simulator.baseline")

COMMAND = {
    "command_id": "cmd_mode_1", "session_id": "sess_demo", "source_id": "controller_A",
    "auth_token": "demo-token-controller-A", "command_type": "CONNECT",
    "value": None, "unit": None,
}


def block_simulator_imports(monkeypatch):
    """Make `import simulator...` fail even if a simulator/ folder exists."""
    for name in SIM_MODULES:
        monkeypatch.setitem(sys.modules, name, None)


def test_load_simulator_without_package_returns_none(monkeypatch):
    block_simulator_imports(monkeypatch)
    namespace, mode = main.load_simulator()
    assert namespace is None
    assert mode.startswith("standalone, no simulator")


def test_partial_simulator_package_also_falls_back(monkeypatch):
    # simulator/ exists but is missing a required name -> ImportError -> standalone.
    block_simulator_imports(monkeypatch)
    for name in ("simulator", "simulator.scenarios", "simulator.baseline"):
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
    namespace, _ = main.load_simulator()
    assert namespace is None


@pytest.fixture
def standalone_client(tmp_path, monkeypatch):
    gw = Gateway(str(tmp_path / "standalone.db"))
    main.seed_demo_session(gw)
    monkeypatch.setattr(main, "gateway", gw)
    monkeypatch.setattr(main, "sim", None)
    yield TestClient(main.app)
    gw.db.close()


def test_standalone_scenarios_empty_and_404(standalone_client):
    assert standalone_client.get("/scenarios").json() == {"items": []}
    assert standalone_client.post("/scenarios/excess_power").status_code == 404


def test_standalone_baseline_501(standalone_client):
    assert standalone_client.post("/baseline/command", json=COMMAND).status_code == 501


def test_standalone_gateway_still_protects(standalone_client):
    body = standalone_client.post("/command", json=COMMAND).json()
    assert (body["decision"], body["state_after"]) == ("ALLOW", "CONNECTED")


# ---- integrated mode, using a fake simulator package -------------------------

class FakeChargerSimulator:
    def reset_session(self, session_id, vehicle_id):
        return {}

    def apply(self, command):
        return {}

    def snapshot(self, session_id):
        return None


def fake_run_scenario(name, send, create_session):
    if name == "broken":
        # A bad session definition in a scenario file: create_session raises ValueError.
        create_session({"session_id": "bad id", "vehicle_id": "Vehicle-01"})
    create_session({"session_id": "sess_fake", "vehicle_id": "Vehicle-01"})
    return {"scenario": name, "session_id": "sess_fake", "passed": True, "results": []}


@pytest.fixture
def integrated_client(tmp_path, monkeypatch):
    fake = SimpleNamespace(
        ChargerSimulator=FakeChargerSimulator,
        list_scenarios=lambda: [{"name": "demo", "title": "Demo", "description": "d"},
                                {"name": "broken", "title": "Broken", "description": "b"}],
        run_scenario=fake_run_scenario,
        baseline_apply=lambda cmd: {"mode": "baseline", "accepted": True, "snapshot": {}},
    )
    gw = Gateway(str(tmp_path / "integrated.db"), simulator=fake.ChargerSimulator())
    main.seed_demo_session(gw)
    monkeypatch.setattr(main, "gateway", gw)
    monkeypatch.setattr(main, "sim", fake)
    yield TestClient(main.app)
    gw.db.close()


def test_load_simulator_success_path(monkeypatch):
    modules = {
        "simulator": ModuleType("simulator"),
        "simulator.ev_simulator": SimpleNamespace(ChargerSimulator=FakeChargerSimulator),
        "simulator.scenarios": SimpleNamespace(list_scenarios=list, run_scenario=fake_run_scenario),
        "simulator.baseline": SimpleNamespace(baseline_apply=dict),
    }
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)
    namespace, mode = main.load_simulator()
    assert namespace.ChargerSimulator is FakeChargerSimulator
    assert mode == "integrated, simulator attached"


def test_integrated_scenarios_list_run_and_unknown(integrated_client):
    assert integrated_client.get("/scenarios").json() == {"items": [
        {"name": "demo", "title": "Demo", "description": "d"},
        {"name": "broken", "title": "Broken", "description": "b"}]}
    assert integrated_client.post("/scenarios/demo").json()["passed"] is True
    assert integrated_client.post("/scenarios/nope").status_code == 404


def test_unknown_name_is_404_without_running_the_scenario(integrated_client, monkeypatch):
    calls = []
    monkeypatch.setattr(main.sim, "run_scenario", lambda *a: calls.append(a))
    assert integrated_client.post("/scenarios/nope").status_code == 404
    assert calls == []


def test_value_error_while_running_is_422_with_message(integrated_client):
    response = integrated_client.post("/scenarios/broken")
    assert response.status_code == 422
    assert "session_id" in response.json()["detail"]


def test_integrated_baseline(integrated_client):
    response = integrated_client.post("/baseline/command", json=COMMAND)
    assert response.json() == {"mode": "baseline", "accepted": True, "snapshot": {}}
