from pathlib import Path

import pytest

from nagabridge.core.config import ConfigError, load_config


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "nagabridge.toml"
    path.write_text(body, encoding="utf-8")
    return path


def test_load_config_valid_minimal(tmp_path: Path):
    path = _write(
        tmp_path,
        """
[system]
log_level = "INFO"

[mqtt]
host = "127.0.0.1"
port = 1883

[[adapters.ble_device]]
name = "Powerstream"
mac = "AA:BB:CC:DD:EE:FF"
type = "powerstream"
""",
    )

    cfg = load_config(path)
    assert cfg.mqtt is not None
    assert cfg.mqtt.host == "127.0.0.1"
    assert cfg.devices[0].type == "powerstream"


def test_load_config_invalid_device_type(tmp_path: Path):
    path = _write(
        tmp_path,
        """
[[adapters.ble_device]]
name = "Unknown"
mac = "AA:BB:CC:DD:EE:11"
type = "foo"
""",
    )

    with pytest.raises(ConfigError):
        load_config(path)


def test_load_config_missing_mqtt_host(tmp_path: Path):
    path = _write(
        tmp_path,
        """
[mqtt]
port = 1883
""",
    )

    with pytest.raises(ConfigError):
        load_config(path)
