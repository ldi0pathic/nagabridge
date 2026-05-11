"""Tests for TOML configuration loading and validation."""

from pathlib import Path

import pytest

from nagabridge.core.config import ConfigError, load_config

TWO_DEVICES = 2


def _write(tmp_path: Path, body: str) -> Path:
    """Write a TOML config body to a temporary config file."""
    path = tmp_path / "nagabridge.toml"
    path.write_text(body, encoding="utf-8")
    return path


def _ensure(condition: object, message: str) -> None:
    """Raise assertion error if condition is not true."""
    if not condition:
        raise AssertionError(message)


def test_load_config_valid_minimal(tmp_path: Path) -> None:
    """Minimal valid config should load MQTT and one adapter."""
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
    _ensure(cfg.mqtt is not None, "MQTT config should be present")
    _ensure(cfg.mqtt.host == "127.0.0.1", "MQTT host should match config")
    _ensure(cfg.devices[0].type == "powerstream", "Adapter type should match config")


def test_load_config_without_mqtt_section_is_valid(tmp_path: Path) -> None:
    """Config without MQTT block should remain valid."""
    path = _write(
        tmp_path,
        """
[[adapters.ble_device]]
name = "Powerstream"
mac = "AA:BB:CC:DD:EE:FF"
type = "powerstream"
""",
    )
    cfg = load_config(path)
    _ensure(cfg.mqtt is None, "MQTT should be optional")


def test_load_config_invalid_device_type(tmp_path: Path) -> None:
    """Unknown device types should raise ConfigError."""
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


def test_load_config_invalid_mac(tmp_path: Path) -> None:
    """Invalid MAC format should raise ConfigError."""
    path = _write(
        tmp_path,
        """
[[adapters.ble_device]]
name = "Powerstream"
mac = "foo"
type = "powerstream"
""",
    )

    with pytest.raises(ConfigError):
        load_config(path)


def test_load_config_missing_device_name(tmp_path: Path) -> None:
    """Missing required device fields should raise ConfigError."""
    path = _write(
        tmp_path,
        """
[[adapters.ble_device]]
mac = "AA:BB:CC:DD:EE:11"
type = "powerstream"
""",
    )

    with pytest.raises(ConfigError):
        load_config(path)


def test_load_config_invalid_log_level(tmp_path: Path) -> None:
    """Unsupported log levels should raise ConfigError."""
    path = _write(
        tmp_path,
        """
[system]
log_level = "TRACE"
""",
    )

    with pytest.raises(ConfigError):
        load_config(path)


def test_load_config_invalid_mqtt_port(tmp_path: Path) -> None:
    """Out-of-range MQTT port should raise ConfigError."""
    path = _write(
        tmp_path,
        """
[mqtt]
host = "127.0.0.1"
port = 99999
""",
    )

    with pytest.raises(ConfigError):
        load_config(path)


def test_load_config_multiple_devices(tmp_path: Path) -> None:
    """Multiple adapters should all be loaded from config."""
    path = _write(
        tmp_path,
        """
[[adapters.ble_device]]
name = "Powerstream"
mac = "AA:BB:CC:DD:EE:FF"
type = "powerstream"

[[adapters.ble_device]]
name = "Delta2"
mac = "AA:BB:CC:DD:EE:FE"
type = "delta2"
""",
    )

    cfg = load_config(path)
    _ensure(len(cfg.devices) == TWO_DEVICES, "Expected two device entries")


def test_load_config_missing_mqtt_host(tmp_path: Path) -> None:
    """MQTT section without host should raise ConfigError."""
    path = _write(
        tmp_path,
        """
[mqtt]
port = 1883
""",
    )

    with pytest.raises(ConfigError):
        load_config(path)


def test_load_config_powerstream_specific_fields(tmp_path: Path) -> None:
    """PowerStream-specific BLE settings should be parsed and validated."""
    path = _write(
        tmp_path,
        """
[[adapters.ble_device]]
name = "Powerstream"
mac = "AA:BB:CC:DD:EE:FF"
type = "powerstream"
serial_number = "SN123"
user_id = "USER42"
poll_interval_seconds = 12.5
reconnect_attempts = 4
reconnect_backoff_seconds = 0.5
write_with_response = true
""",
    )

    cfg = load_config(path)
    device = cfg.devices[0]

    _ensure(device.serial_number == "SN123", "serial_number should be parsed")
    _ensure(device.user_id == "USER42", "user_id should be parsed")
    _ensure(device.poll_interval_seconds == 12.5, "poll interval should be parsed")
    _ensure(device.reconnect_attempts == 4, "reconnect attempts should be parsed")
    _ensure(device.reconnect_backoff_seconds == 0.5, "backoff should be parsed")
    _ensure(device.write_with_response is True, "write response flag should be parsed")


def test_load_config_rejects_invalid_powerstream_poll_interval(tmp_path: Path) -> None:
    """Invalid PowerStream timing values should fail config validation."""
    path = _write(
        tmp_path,
        """
[[adapters.ble_device]]
name = "Powerstream"
mac = "AA:BB:CC:DD:EE:FF"
type = "powerstream"
poll_interval_seconds = 0
""",
    )

    with pytest.raises(ConfigError):
        load_config(path)
