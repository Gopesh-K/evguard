"""Capture real API responses (contract v1.1) into docs/real_responses/.

Run from the project root:  python scripts/capture_responses.py  (inside the .venv)

Uses FastAPI's TestClient against backend.main.app with a throwaway Gateway on
a temporary database, in standalone mode (no simulator). evguard.db is never touched.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "docs" / "real_responses"
sys.path.insert(0, str(ROOT))

CONTROLLER_TOKEN = "demo-token-controller-A"
BAD_TOKEN = "bad-token"


def command(command_id, command_type, value=None, unit=None,
            session_id="sess_demo", token=CONTROLLER_TOKEN):
    return {
        "command_id": command_id,
        "timestamp": "2026-09-20T10:00:00Z",
        "session_id": session_id,
        "source_id": "controller_A",
        "auth_token": token,
        "command_type": command_type,
        "value": value,
        "unit": unit,
    }


def capture() -> list[Path]:
    # Importing backend.main creates the default "evguard.db" in the current
    # directory, so import it from inside a temporary directory.
    with tempfile.TemporaryDirectory() as tmp:
        original_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            import backend.main as main
            from fastapi.testclient import TestClient
            from core.decision import Gateway

            main.gateway.db.close()  # the import-time gateway is not used
            gateway = Gateway(str(Path(tmp) / "capture.db"))
            main.seed_demo_session(gateway)
            main.gateway = gateway
            main.sim = None  # standalone mode
            client = TestClient(main.app)

            def send(cmd, expect, rule):
                response = client.post("/command", json=cmd)
                assert response.status_code == 200, response.text
                body = response.json()
                assert (body["decision"], body["rule_triggered"]) == (expect, rule), (
                    f"{cmd['command_type']}: expected {expect}/{rule}, "
                    f"got {body['decision']}/{body['rule_triggered']}")
                return body

            send(command("cmd_capture_01", "CONNECT"), "ALLOW", "ok")
            send(command("cmd_capture_02", "AUTHORIZE_SESSION"), "ALLOW", "ok")
            send(command("cmd_capture_03", "START_CHARGING"), "ALLOW", "ok")
            send(command("cmd_capture_04", "SET_POWER", 5.0, "kW"), "ALLOW", "ok")
            block = send(command("cmd_capture_05", "SET_POWER", 20.0, "kW"),
                         "BLOCK", "policy.power_limit")

            created = client.post("/sessions", json={
                "session_id": "sess_invalid_state", "vehicle_id": "Vehicle-02",
                "max_power_kw": 7.0, "max_current_a": 32.0})
            assert created.status_code == 200, created.text
            send(command("cmd_capture_06", "START_CHARGING", session_id="sess_invalid_state"),
                 "BLOCK", "state.invalid_transition")

            bad = send(command("cmd_capture_07", "CONNECT", token=BAD_TOKEN),
                       "BLOCK", "auth.invalid_token")
            assert bad["state_before"] is None and bad["state_after"] is None

            session = client.get("/sessions/sess_demo").json()
            assert session["state"] == "CHARGING", session["state"]

            outputs = {
                "decisions.json": client.get("/commands").json(),
                "session.json": session,
                "stats.json": client.get("/stats").json(),
                "scenarios.json": client.get("/scenarios").json(),
                "block_decision.json": block,
            }
            assert len(outputs["decisions.json"]["items"]) == 7
            assert outputs["stats.json"] == {"total": 7, "allowed": 4, "blocked": 3}
            assert outputs["scenarios.json"] == {"items": []}

            gateway.db.close()
        finally:
            os.chdir(original_cwd)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for name, body in outputs.items():
        text = json.dumps(body, indent=2) + "\n"
        for secret in (CONTROLLER_TOKEN, BAD_TOKEN, "demo-token"):
            assert secret not in text, f"token string '{secret}' leaked into {name}"
        path = OUT_DIR / name
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written


if __name__ == "__main__":
    for path in capture():
        print(path.relative_to(ROOT))
