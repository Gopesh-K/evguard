"""Tests for core/state_engine.py."""

import pytest

from contract.evguard_contract import TRANSITIONS
from core.state_engine import next_state


@pytest.mark.parametrize("key, expected", list(TRANSITIONS.items()))
def test_every_transition_row(key, expected):
    current, command_type = key
    assert next_state(current, command_type) == expected


@pytest.mark.parametrize("current, command_type", [
    ("DISCONNECTED", "START_CHARGING"),
    ("CHARGING", "DISCONNECT"),
    ("AUTHORIZED", "SET_POWER"),
])
def test_invalid_transitions_return_none(current, command_type):
    assert next_state(current, command_type) is None
