"""Tests for core/sequence_check.py."""

from contract.evguard_contract import RATE_MAX_COMMANDS, RATE_WINDOW_SECONDS
from core.sequence_check import RateTracker


def burst(tracker, n, source="controller_A", session="sess_a", start=0.0):
    return [tracker.record_and_check(source, session, start + i * 0.1) for i in range(n)]


def test_first_max_commands_pass_then_block():
    results = burst(RateTracker(), RATE_MAX_COMMANDS + 2)
    assert all(ok for ok, _, _ in results[:RATE_MAX_COMMANDS])
    for ok, rule, reason in results[RATE_MAX_COMMANDS:]:
        assert (ok, rule) == (False, "sequence.rate_exceeded")
        assert str(RATE_MAX_COMMANDS) in reason


def test_window_slides():
    tracker = RateTracker()
    burst(tracker, RATE_MAX_COMMANDS + 1)
    ok, _, _ = tracker.record_and_check("controller_A", "sess_a", RATE_WINDOW_SECONDS + 5)
    assert ok


def test_keyed_by_source_and_session():
    tracker = RateTracker()
    burst(tracker, RATE_MAX_COMMANDS + 1)
    assert tracker.record_and_check("controller_A", "sess_b", 0.5)[0]
    assert tracker.record_and_check("monitor_01", "sess_a", 0.5)[0]


def test_clear_removes_only_that_session():
    tracker = RateTracker()
    burst(tracker, RATE_MAX_COMMANDS + 1, session="sess_a")
    burst(tracker, RATE_MAX_COMMANDS + 1, session="sess_b")
    tracker.clear("sess_a")
    assert tracker.record_and_check("controller_A", "sess_a", 1.0)[0]
    assert not tracker.record_and_check("controller_A", "sess_b", 1.0)[0]
