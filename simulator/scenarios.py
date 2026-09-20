"""Scenario tooling and runner for EVGuard (Role 2).

Provides helpers to construct commands, discover and load scenario JSON files,
and execute scenarios against a gateway or mock send function.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable
import uuid

from contract.evguard_contract import COMMAND_KEYS

# Directory where scenario JSON files are stored
SCENARIO_DIR = Path(__file__).resolve().parent / "scenario_data"


def make_command(
    session_id: str,
    source_id: str,
    auth_token: str,
    command_type: str,
    value: float | None = None,
    unit: str | None = None,
) -> dict:
    """Generate a single contract-compliant command dictionary.

    Fills unique command_id and UTC timestamp automatically.
    The returned dictionary contains exactly COMMAND_KEYS from the contract.
    """
    cmd = {
        "command_id": f"cmd_{uuid.uuid4().hex[:12]}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "source_id": source_id,
        "auth_token": auth_token,
        "command_type": command_type,
        "value": value,
        "unit": unit,
    }
    return {k: cmd[k] for k in COMMAND_KEYS}


def list_scenarios() -> list[dict]:
    """Read all scenario JSON files from simulator/scenario_data/.

    Returns a list of dicts: [{'name': ..., 'title': ..., 'description': ...}],
    sorted by name in deterministic alphabetical order.
    """
    if not SCENARIO_DIR.is_dir():
        return []

    scenarios: list[dict] = []
    for file_path in sorted(SCENARIO_DIR.glob("*.json")):
        scenario_name = file_path.stem
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            scenarios.append({
                "name": data.get("name", scenario_name),
                "title": data.get("title", ""),
                "description": data.get("description", ""),
            })
        except Exception:
            scenarios.append({
                "name": scenario_name,
                "title": "",
                "description": "",
            })

    scenarios.sort(key=lambda s: s["name"])
    return scenarios


def load_scenario(name: str) -> dict:
    """Load a scenario definition JSON by name from simulator/scenario_data/.

    Raises ValueError if the scenario does not exist or is invalid.
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"Invalid scenario name: {name!r}")

    clean_name = name[:-5] if name.endswith(".json") else name

    # Prevent path traversal
    safe_name = Path(clean_name).name
    if safe_name != clean_name:
        raise ValueError(f"Invalid scenario name: {name!r}")

    file_path = SCENARIO_DIR / f"{clean_name}.json"
    if not file_path.is_file():
        raise ValueError(f"Scenario not found: {name}")

    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_scenario(name: str, send: Callable[[dict], dict], create_session: Callable[[dict], Any]) -> dict:
    """Execute a scenario against a gateway or mock send function.

    1. Loads the scenario definition.
    2. Calls create_session with the scenario session definition.
    3. Iterates over steps, creates complete commands with make_command(),
       sends them via send(command), and checks expectations.
    4. Returns a result dictionary conforming to contract §3.6.
    """
    scenario = load_scenario(name)
    session_def = scenario.get("session", {})
    session_id = session_def.get("session_id", "")

    # Initialize / reset the session
    create_session(session_def)

    step_results = []
    steps = scenario.get("steps", [])

    for idx, step in enumerate(steps, start=1):
        cmd = make_command(
            session_id=session_id,
            source_id=step.get("source_id", ""),
            auth_token=step.get("auth_token", ""),
            command_type=step.get("command_type", ""),
            value=step.get("value"),
            unit=step.get("unit"),
        )

        decision = send(cmd)

        expected_decision = step.get("expect")
        expected_rule = step.get("expect_rule")

        actual_decision = decision.get("decision") if isinstance(decision, dict) else None
        actual_rule = decision.get("rule_triggered") if isinstance(decision, dict) else None

        passed = (actual_decision == expected_decision) and (actual_rule == expected_rule)

        step_results.append({
            "step": idx,
            "expect": expected_decision,
            "expect_rule": expected_rule,
            "passed": passed,
            "decision": decision,
        })

    all_passed = all(r["passed"] for r in step_results) if step_results else True

    return {
        "scenario": scenario.get("name", name),
        "session_id": session_id,
        "passed": all_passed,
        "results": step_results,
    }

