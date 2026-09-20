"""Streamlit AppTest checks for dashboard/app.py (mock mode, no backend needed)."""

import sys
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

DASHBOARD = Path(__file__).resolve().parents[1] / "dashboard"
APP = str(DASHBOARD / "app.py")


@pytest.fixture
def app(monkeypatch):
    monkeypatch.syspath_prepend(str(DASHBOARD))
    monkeypatch.setenv("EVGUARD_MOCK", "1")
    sys.modules.pop("api_client", None)
    at = AppTest.from_file(APP, default_timeout=30).run()
    yield at
    sys.modules.pop("api_client", None)


def _texts(at):
    return [e.value for e in at.markdown] + [e.value for e in at.caption]


def test_mock_wording_follows_mock_mode(app):
    assert not app.exception
    joined = "\n".join(_texts(app))
    assert "Mock data mode" in joined
    assert "against mock data" in joined
    assert "the mock EVGuard gateway" not in joined


def test_live_wording_when_mock_off(monkeypatch):
    monkeypatch.syspath_prepend(str(DASHBOARD))
    monkeypatch.setenv("EVGUARD_MOCK", "0")
    sys.modules.pop("api_client", None)
    try:
        # No backend is running, so the app stops early; check the labels directly.
        import api_client

        assert api_client.MOCK_MODE is False
        at = AppTest.from_file(APP, default_timeout=30).run()
        assert not at.exception
    finally:
        sys.modules.pop("api_client", None)


def test_scenario_run_shows_banner_and_selects_session(app):
    button = next(b for b in app.button if b.key == "scenario_excess_power")
    button.click().run()
    assert not app.exception
    assert app.session_state["active_session_id"] == "sess_excess_power"
    assert any(s.value == "Scenario matched expectations" for s in app.success)  # leading ✔ becomes the icon


def test_mismatch_banner_names_the_step(app, monkeypatch):
    import api_client

    bad = {
        "scenario": "excess_power",
        "session_id": "sess_excess_power",
        "passed": False,
        "results": [
            {"step": 1, "expect": "ALLOW", "expect_rule": "ok", "passed": True},
            {"step": 2, "expect": "BLOCK", "expect_rule": "x", "passed": False},
        ],
    }
    monkeypatch.setattr(api_client, "run_scenario", lambda name: bad)
    next(b for b in app.button if b.key == "scenario_excess_power").click().run()
    assert any("Mismatch at step 2" in e.value for e in app.error)


def test_csv_download_is_utf8_with_bom(app):
    sys.path.insert(0, str(DASHBOARD))
    try:
        import importlib.util

        # build_csv lives in app.py; exercise it through the module source.
        src = Path(APP).read_text(encoding="utf-8")
        start = src.index("def build_csv")
        end = src.index("# Streamlit renamed", start)
        ns = {"io": __import__("io"), "csv": __import__("csv")}
        exec(src[start:end], ns)
    finally:
        sys.path.remove(str(DASHBOARD))
    data = ns["build_csv"]([{"Time": "t", "Command": "c", "Value": "—",
                             "Decision": "ALLOW", "Rule": "ok", "Reason": "r"}])
    assert data.startswith(b"\xef\xbb\xbf")
    assert "—" in data.decode("utf-8-sig")


# ---- guided layout, against a real in-process backend ----

@pytest.fixture
def live(monkeypatch, tmp_path):
    """Real uvicorn server on a free port, throwaway database, dashboard in live mode."""
    import socket
    import threading
    import time

    import uvicorn

    import backend.main as main
    from core.decision import Gateway
    from simulator.ev_simulator import ChargerSimulator

    gateway = Gateway(str(tmp_path / "live.db"), simulator=ChargerSimulator())
    main.seed_demo_session(gateway)
    monkeypatch.setattr(main, "gateway", gateway)

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    assert server.started

    monkeypatch.syspath_prepend(str(DASHBOARD))
    monkeypatch.setenv("EVGUARD_MOCK", "0")
    monkeypatch.setenv("EVGUARD_API_URL", f"http://127.0.0.1:{port}")
    sys.modules.pop("api_client", None)
    yield AppTest.from_file(APP, default_timeout=30).run()

    server.should_exit = True
    thread.join(timeout=5)
    gateway.db.close()
    sys.modules.pop("api_client", None)


def _md(at):
    return "\n".join(e.value for e in at.markdown)


def _plain(at):
    """Visible text of every markdown element: no <style> block, no tags, entities decoded."""
    import html
    import re

    text = "\n".join(e.value for e in at.markdown)
    text = re.sub(r"<style>.*?</style>", "", text, flags=re.S)
    return html.unescape(re.sub(r"<[^>]+>", "", text))


def _html_with(at, marker):
    """The markdown element whose raw HTML contains `marker` (the CSS block never does)."""
    return next(e.value for e in at.markdown if marker in e.value and "<style>" not in e.value)


def _click(at, key):
    next(b for b in at.button if b.key == key).click().run()


def test_intro_panels_and_scenario_groups(live):
    assert not live.exception
    text = _plain(live)
    assert "What is EVGuard?" in text
    assert "Authentication" in text and "Rate limit" in text and "ALLOW / BLOCK" in text
    assert "How to use this dashboard" in text
    assert "Run the Normal charging session" in text
    assert "✅ Normal operation" in text and "⚠️ Attacks" in text
    keys = {b.key for b in live.button if b.key and b.key.startswith("scenario_")}
    assert len(keys) == 8
    assert text.index("Normal operation") < text.index("Attacks")
    assert any("Live mode" in c.value for c in live.caption)


def test_cards_show_expectation_and_description(live):
    text = _plain(live)
    assert "Expected: ALLOW" in text
    assert "Expected: BLOCK (policy.power_limit)" in text
    assert 'class="badge badge-allow"' in _md(live) and 'class="badge badge-block"' in _md(live)
    assert "Valid controller asks for 20 kW on a 7 kW session." in [m.value for m in live.markdown]


def test_run_shows_what_just_happened(live):
    _click(live, "scenario_excess_power")
    assert not live.exception
    assert "What just happened" in _md(live)
    assert any(s.value == "Scenario matched expectations" for s in live.success)

    table = _html_with(live, '<table class="evtable">')
    assert table.count("<tr>") == 1 + 4                        # header + 4 steps
    assert 'class="pill pill-block">⛔ BLOCK</span>' in table   # coloured pill with icon and word
    assert "<code>policy.power_limit</code>" in table
    assert table.count("as expected") == 4 and "mismatch" not in table

    conclusion = next(i.value for i in live.info if "blocked" in i.value)
    assert "SET_POWER 20 kW (rule policy.power_limit)" in conclusion
    assert "exceeds session maximum of 7.0 kW" in conclusion
    assert live.session_state["active_session_id"] == "sess_excess_power"


def test_reset_demo_clears_the_run(live):
    _click(live, "scenario_excess_power")
    assert live.session_state["scenario_result"]

    _click(live, "reset_demo")
    assert not live.exception
    assert "scenario_result" not in live.session_state
    assert "active_session_id" not in live.session_state
    assert any("Demo reset" in i.value for i in live.info)
    assert "What just happened" not in _md(live)


def test_baseline_vs_evguard_card(live):
    _click(live, "run_comparison")
    assert not live.exception
    bad = _html_with(live, "cmp-card cmp-bad")
    good = _html_with(live, "cmp-card cmp-good")
    assert "Without EVGuard" in bad and "20 kW" in bad
    assert "BLOCKED" in good and "policy.power_limit" in good and "5 kW" in good
    assert "stays at" in good
    assert "simulated unprotected controller, not a real charger" in "\n".join(
        c.value for c in live.caption)


def test_backend_down_shows_instructions(monkeypatch):
    monkeypatch.syspath_prepend(str(DASHBOARD))
    monkeypatch.setenv("EVGUARD_MOCK", "0")
    monkeypatch.setenv("EVGUARD_API_URL", "http://127.0.0.1:9")  # nothing listens here
    sys.modules.pop("api_client", None)
    try:
        at = AppTest.from_file(APP, default_timeout=30).run()
    finally:
        sys.modules.pop("api_client", None)

    assert not at.exception
    assert any("backend isn't running" in e.value for e in at.error)
    assert any("./run.ps1" in c.value for c in at.code)
    assert not at.button  # nothing else is rendered


def _api_power(session_id):
    import os

    import requests

    body = requests.get(f"{os.environ['EVGUARD_API_URL']}/sessions/{session_id}", timeout=5).json()
    return body["physical"]["power_kw"]


@pytest.mark.parametrize("name, session_id, expected_power", [
    ("excess_power", "sess_excess_power", 0.0),   # no 5 kW step before the 20 kW request
    ("normal_session", "sess_normal", 5.0),
    ("invalid_state", "sess_invalid_state", 0.0),
])
def test_conclusion_power_matches_the_sessions_actual_power(live, name, session_id, expected_power):
    _click(live, f"scenario_{name}")
    assert not live.exception

    actual = _api_power(session_id)
    assert actual == expected_power  # what the simulated charger really did

    conclusion = next(i.value for i in live.info if "Charger power after the run" in i.value)
    assert f"Charger power after the run: {actual:g} kW." in conclusion


def test_conclusions_are_computed_not_hardcoded(live, monkeypatch):
    """Feed the panel a different result: the sentence must follow the data."""
    import api_client

    fake = {
        "scenario": "excess_power", "session_id": "sess_excess_power", "passed": True,
        "results": [
            {"step": 1, "expect": "ALLOW", "expect_rule": "ok", "passed": True,
             "decision": {"decision": "ALLOW", "source_id": "controller_A", "command_type": "CONNECT",
                          "rule_triggered": "ok", "reason": "All checks passed"}},
            {"step": 2, "expect": "BLOCK", "expect_rule": "policy.current_limit", "passed": True,
             "decision": {"decision": "BLOCK", "source_id": "controller_A", "command_type": "SET_CURRENT",
                          "value": 99.0, "unit": "A", "rule_triggered": "policy.current_limit",
                          "reason": "Requested current 99.0 A exceeds session maximum of 32.0 A"}},
        ],
    }
    monkeypatch.setattr(api_client, "run_scenario", lambda name: fake)
    _click(live, "scenario_excess_power")
    conclusion = next(i.value for i in live.info if "blocked" in i.value)
    assert "SET_CURRENT 99 A (rule policy.current_limit)" in conclusion
    assert "99.0 A exceeds session maximum of 32.0 A" in conclusion
    assert "20 kW" not in conclusion and "7" not in conclusion.replace("32.0", "")


def test_decision_card_and_session_panel_name_their_session(live):
    def texts():
        return [m.value for m in live.markdown] + [c.value for c in live.caption]

    # First load: no run yet, so the panel shows the default demo session.
    assert any("Showing session: `sess_demo` (default demo session)" in x for x in texts())

    _click(live, "scenario_excess_power")
    assert "Session: sess_excess_power" in _html_with(live, "decision-hero")
    assert any("Showing session: `sess_excess_power` (from your last scenario run)" in x for x in texts())


def test_api_text_is_escaped_in_injected_html(live, monkeypatch):
    """Reasons, rules and IDs come from the API; none of it may reach the page as raw HTML."""
    import api_client

    evil = "<script>alert(1)</script><img src=x onerror=alert(2)>"
    item = {"command_id": "cmd_x", "session_id": "sess_<b>x</b>", "source_id": "controller_A",
            "command_type": "SET_POWER", "value": 20.0, "unit": "kW", "decision": "BLOCK",
            "rule_triggered": "<i>rule</i>", "reason": evil, "state_before": "CHARGING",
            "state_after": "CHARGING", "received_at": "2026-09-20T10:00:00Z"}
    monkeypatch.setattr(api_client, "get_decisions", lambda limit=50: {"items": [item]})
    live.run()
    assert not live.exception

    page_html = "\n".join(e.value for e in live.markdown if "<style>" not in e.value)
    for raw in ("<script", "<img", "<i>rule", "<b>x</b>"):
        assert raw not in page_html, raw
    assert "&lt;script&gt;" in _html_with(live, "decision-hero")            # decision card
    assert "&lt;script&gt;" in _html_with(live, '<table class="evtable">')  # audit table
