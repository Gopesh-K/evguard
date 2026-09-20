import pytest
from pydantic import ValidationError

from backend.schemas import CommandIn


def base_command():
    return {
        "command_id": "cmd_test_001",
        "timestamp": "2026-09-20T10:00:03Z",
        "session_id": "sess_demo",
        "source_id": "controller_A",
        "auth_token": "demo-token-controller-A",
        "command_type": "CONNECT",
        "value": None,
        "unit": None,
    }


def test_connect_command_is_valid():
    command = CommandIn(**base_command())

    assert command.command_type == "CONNECT"
    assert command.value is None
    assert command.unit is None


def test_set_power_requires_kw():
    data = base_command()
    data.update({
        "command_type": "SET_POWER",
        "value": 5.0,
        "unit": "kW",
    })

    command = CommandIn(**data)

    assert command.value == 5.0
    assert command.unit == "kW"


def test_set_current_requires_ampere():
    data = base_command()
    data.update({
        "command_type": "SET_CURRENT",
        "value": 16.0,
        "unit": "A",
    })

    command = CommandIn(**data)

    assert command.value == 16.0
    assert command.unit == "A"


def test_set_power_rejects_wrong_unit():
    data = base_command()
    data.update({
        "command_type": "SET_POWER",
        "value": 5.0,
        "unit": "A",
    })

    with pytest.raises(ValueError):
        CommandIn(**data)


def test_set_current_rejects_wrong_unit():
    data = base_command()
    data.update({
        "command_type": "SET_CURRENT",
        "value": 16.0,
        "unit": "kW",
    })

    with pytest.raises(ValueError):
        CommandIn(**data)


def test_non_value_command_rejects_value():
    data = base_command()
    data.update({
        "command_type": "CONNECT",
        "value": 5.0,
        "unit": "kW",
    })

    with pytest.raises(ValueError):
        CommandIn(**data)


def test_non_value_command_rejects_unit():
    data = base_command()
    data.update({
        "command_type": "CONNECT",
        "value": None,
        "unit": "kW",
    })

    with pytest.raises(ValueError):
        CommandIn(**data)


def test_zero_value_is_rejected():
    data = base_command()
    data.update({
        "command_type": "SET_POWER",
        "value": 0,
        "unit": "kW",
    })

    with pytest.raises(ValueError):
        CommandIn(**data)


def test_negative_value_is_rejected():
    data = base_command()
    data.update({
        "command_type": "SET_POWER",
        "value": -5,
        "unit": "kW",
    })

    with pytest.raises(ValueError):
        CommandIn(**data)


def test_nan_value_is_rejected():
    data = base_command()
    data.update({
        "command_type": "SET_POWER",
        "value": float("nan"),
        "unit": "kW",
    })

    with pytest.raises(ValueError):
        CommandIn(**data)


def test_invalid_command_type_is_rejected():
    data = base_command()
    data["command_type"] = "HACK_SYSTEM"

    with pytest.raises(ValidationError):
        CommandIn(**data)


def test_invalid_command_id_is_rejected():
    data = base_command()
    data["command_id"] = "cmd with spaces"

    with pytest.raises(ValueError):
        CommandIn(**data)


def test_invalid_session_id_is_rejected():
    data = base_command()
    data["session_id"] = "session!"

    with pytest.raises(ValueError):
        CommandIn(**data)


def test_invalid_source_id_is_rejected():
    data = base_command()
    data["source_id"] = "controller@A"

    with pytest.raises(ValueError):
        CommandIn(**data)


def test_timestamp_is_optional():
    data = base_command()
    data["timestamp"] = None

    command = CommandIn(**data)

    assert command.timestamp is None


def test_timestamp_too_long_is_rejected():
    data = base_command()
    data["timestamp"] = "x" * 41

    with pytest.raises(ValidationError):
        CommandIn(**data)


def test_empty_auth_token_is_allowed():
    data = base_command()
    data["auth_token"] = ""

    command = CommandIn(**data)

    assert command.auth_token == ""


def test_auth_token_too_long_is_rejected():
    data = base_command()
    data["auth_token"] = "x" * 129

    with pytest.raises(ValidationError):
        CommandIn(**data)


def test_extra_fields_are_rejected():
    data = base_command()
    data["unexpected"] = "not_allowed"

    with pytest.raises(ValidationError):
        CommandIn(**data)


def test_to_command_has_exact_contract_keys():
    data = base_command()

    command = CommandIn(**data)
    result = command.to_command()

    expected_keys = {
        "command_id",
        "timestamp",
        "session_id",
        "source_id",
        "auth_token",
        "command_type",
        "value",
        "unit",
    }

    assert set(result.keys()) == expected_keys


def test_to_command_preserves_values():
    data = base_command()
    data.update({
        "command_type": "SET_POWER",
        "value": 5.0,
        "unit": "kW",
    })

    command = CommandIn(**data)
    result = command.to_command()

    assert result["command_type"] == "SET_POWER"
    assert result["value"] == 5.0
    assert result["unit"] == "kW"