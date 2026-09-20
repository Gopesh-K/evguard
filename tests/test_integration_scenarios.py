"""End-to-end: every shipped scenario must pass through the real Gateway and simulator."""

import pytest

from core.decision import Gateway
from simulator.ev_simulator import ChargerSimulator
from simulator.scenarios import list_scenarios, run_scenario

SCENARIO_NAMES = [s["name"] for s in list_scenarios()]


def failing_steps(result: dict) -> str:
    lines = []
    for step in result["results"]:
        if not step["passed"]:
            d = step["decision"]
            lines.append(
                f"  step {step['step']}: expected {step['expect']}/{step['expect_rule']}, "
                f"got {d.get('decision')}/{d.get('rule_triggered')} ({d.get('reason')})")
    return "\n".join(lines)


def test_scenarios_are_discovered():
    assert SCENARIO_NAMES, "no scenarios found in simulator/scenario_data"


@pytest.mark.parametrize("name", SCENARIO_NAMES)
def test_scenario_passes_through_real_gateway(name, tmp_path):
    gw = Gateway(str(tmp_path / "integration.db"), simulator=ChargerSimulator())
    try:
        result = run_scenario(name, gw.handle, gw.create_session)
    finally:
        gw.db.close()
    assert result["passed"], f"scenario '{name}' failed:\n{failing_steps(result)}"
