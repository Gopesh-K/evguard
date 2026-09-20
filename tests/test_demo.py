"""demo.py runs every scenario through the real Gateway and must match expectations."""

import demo


def test_all_scenarios_match_expectations(tmp_path):
    results, comparison = demo.run_demo(tmp_path / "demo.db")

    assert len(results) == 8
    assert [r["scenario"] for r in results[:2]] == ["normal_session", "full_lifecycle"]
    assert all(r["passed"] for r in results), [r["scenario"] for r in results if not r["passed"]]


def test_baseline_comparison(tmp_path):
    _, comparison = demo.run_demo(tmp_path / "demo.db")

    assert comparison["ok"] is True
    assert comparison["baseline_power_kw"] == 20.0
    assert (comparison["evguard_decision"], comparison["evguard_rule"]) == ("BLOCK", "policy.power_limit")
    assert comparison["evguard_power_kw"] == 5.0


def test_main_prints_summary_and_returns_zero(capsys):
    assert demo.main() == 0
    out = capsys.readouterr().out
    assert "8 scenarios, all matched expectations" in out
    assert "Without EVGuard: charger set to 20 kW" in out
    assert "With EVGuard:    BLOCK (policy.power_limit), charger stays at 5 kW" in out
    assert "Excess power attack" in out and "policy.power_limit" in out


def test_main_returns_one_on_mismatch(monkeypatch, capsys):
    real = demo.run_demo

    def broken(db_path):
        results, comparison = real(db_path)
        results[0]["passed"] = False
        results[0]["results"][0]["passed"] = False
        return results, comparison

    monkeypatch.setattr(demo, "run_demo", broken)
    assert demo.main() == 1
    assert "MISMATCH" in capsys.readouterr().out
