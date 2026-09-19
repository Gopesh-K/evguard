"""Tests for config/loader.py."""

import pytest
import yaml

from config.loader import load_policy


def test_default_config_loads():
    config = load_policy()
    assert config["defaults"] == {"max_power_kw": 7.0, "max_current_a": 32.0}


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_policy(str(tmp_path / "nope.yaml"))


def test_malformed_yaml_raises(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("defaults: [unclosed", encoding="utf-8")
    with pytest.raises(yaml.YAMLError):
        load_policy(str(path))


def test_config_differing_from_contract_raises(tmp_path):
    config = load_policy()
    config["defaults"]["max_power_kw"] = 99.0
    path = tmp_path / "wrong.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    with pytest.raises(ValueError):
        load_policy(str(path))


def test_empty_config_raises(tmp_path):
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        load_policy(str(path))
