"""MOCK_MODE is enabled only when EVGUARD_MOCK=1 (CONTRACT section 5)."""

import importlib
import sys

import pytest

MODULE = "dashboard.api_client"


def _load(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("EVGUARD_MOCK", raising=False)
    else:
        monkeypatch.setenv("EVGUARD_MOCK", value)
    sys.modules.pop(MODULE, None)
    return importlib.import_module(MODULE)


@pytest.fixture(autouse=True)
def _restore_module():
    yield
    sys.modules.pop(MODULE, None)


def test_mock_mode_off_when_unset(monkeypatch):
    assert _load(monkeypatch, None).MOCK_MODE is False


def test_mock_mode_on_when_set_to_1(monkeypatch):
    assert _load(monkeypatch, "1").MOCK_MODE is True


@pytest.mark.parametrize("value", ["0", "", "true"])
def test_mock_mode_off_for_anything_but_1(monkeypatch, value):
    assert _load(monkeypatch, value).MOCK_MODE is False


def test_module_defines_each_function_once(monkeypatch):
    import ast
    from pathlib import Path

    src = Path(_load(monkeypatch, None).__file__).read_text(encoding="utf-8")
    names = [n.name for n in ast.parse(src).body if isinstance(n, ast.FunctionDef)]
    assert len(names) == len(set(names))
    assert {"health", "get_decisions", "get_session", "get_stats", "list_scenarios",
            "run_scenario", "send_command", "baseline_command"} <= set(names)


# ---- mock mode returns contract-shaped data ----

def test_mock_mode_returns_contract_shaped_data(monkeypatch):
    from contract.evguard_contract import CONTRACT_VERSION, DECISION_KEYS, SESSION_KEYS

    client = _load(monkeypatch, "1")

    decisions = client.get_decisions()
    assert decisions is not None and decisions["items"]
    assert all(list(item) == DECISION_KEYS for item in decisions["items"])

    session = client.get_session("sess_demo")
    assert session is not None and list(session) == SESSION_KEYS

    assert list(client.get_stats() or {}) == ["total", "allowed", "blocked"]

    scenarios = client.list_scenarios()
    assert scenarios is not None and scenarios["items"]
    assert all(list(item) == ["name", "title", "description"] for item in scenarios["items"])

    assert client.health() == {"status": "ok", "contract_version": CONTRACT_VERSION}


def test_load_mock_warns_on_stderr_and_returns_none(monkeypatch, tmp_path, capsys):
    client = _load(monkeypatch, "1")
    (tmp_path / "broken.json").write_text('{"a": 1}{"a": 1}', encoding="utf-8")
    monkeypatch.setattr(client, "MOCK_DIR", tmp_path)

    assert client._load_mock("broken.json") is None
    assert client._load_mock("missing.json") is None
    err = capsys.readouterr().err.splitlines()
    assert len(err) == 2
    assert "broken.json" in err[0] and "missing.json" in err[1]
