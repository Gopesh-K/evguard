"""EVGuard no-browser demo.

Runs every scenario through the REAL EVGuard Gateway in this process (with the
simulated charger, on a throwaway database) and prints what happened, in plain
English. No server, no browser, no extra dependencies.

    python demo.py

Exit code 0 only if every scenario matched its expectations and the
baseline comparison behaved as described.
"""

import sys
import tempfile
from pathlib import Path

from core.decision import Gateway
from simulator.baseline import baseline_apply
from simulator.ev_simulator import ChargerSimulator
from simulator.scenarios import list_scenarios, load_scenario, make_command, run_scenario

# Normal operation first, then the attacks (order follows CONTRACT section 4).
NORMAL = ("normal_session", "full_lifecycle")
ATTACKS = (
    "excess_power",
    "invalid_state",
    "excess_current",
    "invalid_token",
    "unauthorized_role",
    "rate_burst",
)

# One plain-English line per scenario: what the "attacker" (or normal user) does.
BLURBS = {
    "normal_session": "Normal operation: a legitimate controller connects, authorizes, "
                      "starts charging and sets a safe 5 kW.",
    "full_lifecycle": "Normal operation: a complete charge from plug-in to unplug, "
                      "every command within limits.",
    "excess_power": "ATTACK: a fully authenticated controller asks the charger for 20 kW "
                    "on a session limited to 7 kW.",
    "invalid_state": "ATTACK: a command sent out of order: START_CHARGING on a session "
                     "that was never connected.",
    "excess_current": "ATTACK: an authenticated controller requests 40 A on a session "
                      "capped at 32 A.",
    "invalid_token": "ATTACK: a controller with a forged authentication token tries to "
                     "connect.",
    "unauthorized_role": "ATTACK: a read-only monitor account tries to send an active "
                         "CONNECT command.",
    "rate_burst": "ATTACK: a controller floods the charger with rapid SET_POWER "
                  "commands; only 10 commands per 10 seconds are allowed.",
}

CONTROLLER = ("controller_A", "demo-token-controller-A")


def _symbols():
    """Unicode ticks and arrows when the console can show them, ASCII otherwise."""
    encoding = getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        "✔✘→—".encode(encoding)
        return {"ok": "✔", "bad": "✘", "arrow": "→", "dash": "—"}
    except (UnicodeEncodeError, LookupError):
        return {"ok": "OK", "bad": "X", "arrow": "->", "dash": "-"}


def _command_text(command_type, value, unit):
    if value is None:
        return command_type
    return f"{command_type} {value:g} {unit or ''}".rstrip()


def _steps_of(name):
    """The scenario's own step definitions, to show the command sent at each step."""
    return load_scenario(name).get("steps", [])


def run_baseline_comparison(gateway):
    """Send the same SET_POWER 20 kW to the protected gateway and to the baseline.

    Both first reach a safe 5 kW. The baseline then obeys 20 kW; EVGuard blocks it.
    """
    session_id = "sess_compare"
    gateway.create_session({
        "session_id": session_id,
        "vehicle_id": "Vehicle-01",
        "max_power_kw": 7.0,
        "max_current_a": 32.0,
    })
    source_id, token = CONTROLLER
    setup = [("CONNECT", None, None), ("AUTHORIZE_SESSION", None, None),
             ("START_CHARGING", None, None), ("SET_POWER", 5.0, "kW")]
    attack = ("SET_POWER", 20.0, "kW")

    for command_type, value, unit in setup:
        gateway.handle(make_command(session_id, source_id, token, command_type, value, unit))
    power_before = gateway.get_session(session_id)["physical"]["power_kw"]
    guarded = gateway.handle(make_command(session_id, source_id, token, *attack))
    guarded_power = gateway.get_session(session_id)["physical"]["power_kw"]

    baseline_session = "sess_compare_baseline"
    for command_type, value, unit in setup + [attack]:
        outcome = baseline_apply(
            make_command(baseline_session, source_id, token, command_type, value, unit)
        )
    baseline_power = outcome["snapshot"]["power_kw"]

    return {
        "evguard_decision": guarded["decision"],
        "evguard_rule": guarded["rule_triggered"],
        "evguard_power_before_kw": power_before,
        "evguard_power_kw": guarded_power,
        "baseline_power_kw": baseline_power,
        "ok": (guarded["decision"] == "BLOCK" and guarded_power == 5.0
               and baseline_power == 20.0),
    }


def run_demo(db_path):
    """Run all scenarios and the comparison. Returns (ordered results, comparison)."""
    gateway = Gateway(str(db_path), simulator=ChargerSimulator())
    try:
        available = {s["name"] for s in list_scenarios()}
        ordered = [n for n in NORMAL + ATTACKS if n in available]
        ordered += sorted(available - set(ordered))
        results = [
            run_scenario(name, gateway.handle, gateway.create_session) for name in ordered
        ]
        comparison = run_baseline_comparison(gateway)
    finally:
        gateway.db.close()
    return results, comparison


def print_scenario(result, sym):
    name = result["scenario"]
    meta = next((s for s in list_scenarios() if s["name"] == name), {})
    steps = _steps_of(name)
    print(f"\n=== {meta.get('title') or name} ({name}) ===")
    print(BLURBS.get(name) or meta.get("description", ""))
    for step in result["results"]:
        definition = steps[step["step"] - 1] if step["step"] - 1 < len(steps) else {}
        command = _command_text(
            definition.get("command_type", "?"), definition.get("value"),
            definition.get("unit"),
        )
        decision = step["decision"] or {}
        mark = sym["ok"] if step["passed"] else sym["bad"]
        print(
            f"  {step['step']:>2}. {command:<22} {decision.get('decision', '?'):<5} "
            f"{decision.get('rule_triggered', '?'):<28} {decision.get('reason', '')}  {mark}"
        )
    if result["passed"]:
        print(f"  {sym['ok']} Matched expectations")
    else:
        failed = [str(s["step"]) for s in result["results"] if not s["passed"]]
        print(f"  {sym['bad']} MISMATCH at step {', '.join(failed)}")


def main():
    sym = _symbols()
    print("EVGuard demo: every scenario runs through the real gateway, in this process.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        results, comparison = run_demo(Path(folder) / "demo.db")

    for result in results:
        print_scenario(result, sym)

    mismatches = [r["scenario"] for r in results if not r["passed"]]
    print("\n=== Baseline vs EVGuard: the same 20 kW command ===")
    print("(The baseline is a simulated unprotected controller, not a real charger.)")
    print(f"  Without EVGuard: charger set to {comparison['baseline_power_kw']:g} kW")
    unchanged = comparison["evguard_power_kw"] == comparison["evguard_power_before_kw"]
    print(f"  With EVGuard:    {comparison['evguard_decision']} ({comparison['evguard_rule']}), "
          f"charger {'stays at' if unchanged else 'is now at'} "
          f"{comparison['evguard_power_kw']:g} kW")

    print("\n=== Summary ===")
    if mismatches:
        print(f"{len(results)} scenarios, MISMATCHES: {', '.join(mismatches)}")
    else:
        print(f"{len(results)} scenarios, all matched expectations {sym['ok']}")
    if not comparison["ok"]:
        print(f"{sym['bad']} Baseline comparison did not behave as expected")
    return 0 if not mismatches and comparison["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
