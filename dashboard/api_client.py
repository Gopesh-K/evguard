import json
import os
import sys
from pathlib import Path
from typing import Any

import requests


BASE_DIR = Path(__file__).resolve().parent
MOCK_DIR = BASE_DIR / "mock_data"

MOCK_MODE = os.getenv("EVGUARD_MOCK", "0") == "1"
API_URL = os.getenv("EVGUARD_API_URL", "http://127.0.0.1:8000").rstrip("/")


def _load_mock(filename: str) -> Any:
    """Load a JSON file from dashboard/mock_data."""
    try:
        path = MOCK_DIR / filename

        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    except (OSError, json.JSONDecodeError) as error:
        print(f"api_client: could not load mock file {filename}: {error}", file=sys.stderr)
        return None


def _request(
    method: str,
    path: str,
    *,
    params: dict | None = None,
    json_data: dict | None = None,
) -> Any:
    """Make an API request. Return None if the backend is unavailable."""
    try:
        response = requests.request(
            method=method,
            url=f"{API_URL}{path}",
            params=params,
            json=json_data,
            timeout=5,
        )

        response.raise_for_status()
        return response.json()

    except (
        requests.RequestException,
        ValueError,
        TypeError,
    ):
        return None


def health() -> dict | None:
    """GET /health"""
    if MOCK_MODE:
        return {
            "status": "ok",
            "contract_version": "1.1",
        }

    return _request("GET", "/health")


def get_decisions(limit: int = 50) -> dict | None:
    """GET /commands?limit=50"""
    if MOCK_MODE:
        return _load_mock("decisions.json")

    limit = min(max(limit, 1), 200)

    return _request(
        "GET",
        "/commands",
        params={"limit": limit},
    )


def get_session(session_id: str) -> dict | None:
    """GET /sessions/{session_id}"""
    if MOCK_MODE:
        session = _load_mock("session.json")

        if session is None:
            return None

        if session.get("session_id") != session_id:
            return None

        return session

    return _request(
        "GET",
        f"/sessions/{session_id}",
    )


def get_stats() -> dict | None:
    """GET /stats"""
    if MOCK_MODE:
        return _load_mock("stats.json")

    return _request("GET", "/stats")


def list_scenarios() -> dict | None:
    """GET /scenarios"""
    if MOCK_MODE:
        return _load_mock("scenarios.json")

    return _request("GET", "/scenarios")


def run_scenario(name: str) -> dict | None:
    """POST /scenarios/{name}"""
    if MOCK_MODE:
        if name == "excess_power":
            return _load_mock("scenario_result_excess_power.json")

        # Generic mock result for the remaining scenarios.
        scenarios = _load_mock("scenarios.json")

        if scenarios is None:
            return None

        known_names = {
            item.get("name")
            for item in scenarios.get("items", [])
        }

        if name not in known_names:
            return None

        return {
            "scenario": name,
            "session_id": f"sess_{name}",
            "passed": True,
            "results": [],
        }

    return _request(
        "POST",
        f"/scenarios/{name}",
    )


def send_command(command: dict) -> dict | None:
    """POST /command"""
    if MOCK_MODE:
        decisions = _load_mock("decisions.json")

        if decisions is None:
            return None

        # Mock response: return the newest matching command type.
        command_type = command.get("command_type")

        for decision in decisions.get("items", []):
            if decision.get("command_type") == command_type:
                return decision

        return None

    return _request(
        "POST",
        "/command",
        json_data=command,
    )


def baseline_command(command: dict) -> dict | None:
    """POST /baseline/command"""
    if MOCK_MODE:
        value = command.get("value")
        unit = command.get("unit")

        return {
            "mode": "baseline",
            "accepted": True,
            "snapshot": {
                "session_id": command.get("session_id"),
                "vehicle_id": "Vehicle-01",
                "plugged_in": True,
                "charging": True,
                "power_kw": value if unit == "kW" else 0.0,
                "current_a": value if unit == "A" else 0.0,
                "last_command": command.get("command_type"),
                "updated_at": command.get("timestamp"),
            },
        }

    return _request(
        "POST",
        "/baseline/command",
        json_data=command,
    )
