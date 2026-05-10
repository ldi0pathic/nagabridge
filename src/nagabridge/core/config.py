"""TOML configuration loading and validation."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, cast

VALID_DEVICE_TYPES = {"powerstream", "delta2max", "delta2"}
VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}
MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
MAX_TCP_PORT = 65535


class ConfigError(ValueError):
    """Raised when configuration content is invalid."""


@dataclass(slots=True)
class BleDeviceConfig:
    """Configuration for a BLE-backed adapter device."""

    name: str
    mac: str
    type: Literal["powerstream", "delta2max", "delta2"]
    serial_number: str | None = None
    user_id: str | None = None
    poll_interval_seconds: float | None = None
    reconnect_attempts: int | None = None
    reconnect_backoff_seconds: float | None = None
    write_with_response: bool | None = None


@dataclass(slots=True)
class MqttConfig:
    """Configuration for MQTT broker integration."""

    host: str
    port: int = 1883
    user: str | None = None
    password: str | None = None


@dataclass(slots=True)
class NagaBridgeConfig:
    """Complete application configuration model."""

    log_level: str = "INFO"
    devices: list[BleDeviceConfig] = field(default_factory=list)
    mqtt: MqttConfig | None = None


def load_config(path: str | Path) -> NagaBridgeConfig:
    """Load and validate bridge configuration from TOML file."""
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))

    system = data.get("system", {})
    adapters = data.get("adapters", {})

    log_level = _parse_log_level(system)
    devices = _parse_ble_devices(adapters)
    mqtt = _parse_mqtt(data.get("mqtt"))

    return NagaBridgeConfig(log_level=log_level, devices=devices, mqtt=mqtt)


def _parse_log_level(system: dict[str, object]) -> str:
    """Parse and validate configured log level."""
    log_level = str(system.get("log_level", "INFO"))
    if log_level not in VALID_LOG_LEVELS:
        msg = f"Ungültiger log_level '{log_level}'"
        raise ConfigError(msg)
    return log_level


def _parse_ble_devices(adapters: dict[str, object]) -> list[BleDeviceConfig]:
    """Parse and validate BLE device adapters list."""
    raw_devices = adapters.get("ble_device", [])
    if not isinstance(raw_devices, list):
        msg = "adapters.ble_device muss eine Liste sein"
        raise ConfigError(msg)

    devices: list[BleDeviceConfig] = []
    for idx, device_data in enumerate(raw_devices, start=1):
        if not isinstance(device_data, dict):
            msg = f"adapters.ble_device[{idx}] muss ein Objekt sein"
            raise ConfigError(msg)
        devices.append(_parse_ble_device(device_data, idx))
    return devices


def _parse_ble_device(device_data: dict[str, object], idx: int) -> BleDeviceConfig:
    """Parse and validate a single BLE adapter config record."""
    for required in ("name", "mac", "type"):
        if required not in device_data:
            msg = f"adapters.ble_device[{idx}] fehlt Feld '{required}'"
            raise ConfigError(msg)

    name = str(device_data["name"])
    mac = str(device_data["mac"])
    device_type = str(device_data["type"])

    if device_type not in VALID_DEVICE_TYPES:
        msg = f"Ungültiger Gerätetyp '{device_type}'"
        raise ConfigError(msg)
    if not MAC_RE.match(mac):
        msg = f"Ungültige MAC-Adresse '{mac}'"
        raise ConfigError(msg)

    typed_device_type = cast(
        'Literal["powerstream", "delta2max", "delta2"]',
        device_type,
    )
    return BleDeviceConfig(
        name=name,
        mac=mac,
        type=typed_device_type,
        serial_number=_optional_str(device_data.get("serial_number")),
        user_id=_optional_str(device_data.get("user_id")),
        poll_interval_seconds=_optional_positive_float(device_data.get("poll_interval_seconds"), "poll_interval_seconds"),
        reconnect_attempts=_optional_positive_int(device_data.get("reconnect_attempts"), "reconnect_attempts"),
        reconnect_backoff_seconds=_optional_non_negative_float(device_data.get("reconnect_backoff_seconds"), "reconnect_backoff_seconds"),
        write_with_response=_optional_bool(device_data.get("write_with_response"), "write_with_response"),
    )


def _parse_mqtt(mqtt_data: object) -> MqttConfig | None:
    """Parse and validate optional MQTT configuration."""
    if mqtt_data is None:
        return None

    if not isinstance(mqtt_data, dict):
        msg = "mqtt muss ein Objekt sein"
        raise ConfigError(msg)

    host = str(mqtt_data.get("host", "")).strip()
    if not host:
        msg = "mqtt.host fehlt oder ist leer"
        raise ConfigError(msg)

    port = int(mqtt_data.get("port", 1883))
    if port <= 0 or port > MAX_TCP_PORT:
        msg = f"Ungültiger mqtt.port '{port}'"
        raise ConfigError(msg)

    return MqttConfig(
        host=host,
        port=port,
        user=_optional_str(mqtt_data.get("user")),
        password=_optional_str(mqtt_data.get("password")),
    )


def _optional_str(value: object) -> str | None:
    """Convert optional scalar value to string or None."""
    if value is None:
        return None
    return str(value)


def _optional_positive_float(value: object, field_name: str) -> float | None:
    """Parse an optional positive float config value."""
    if value is None:
        return None
    parsed = float(value)
    if parsed <= 0:
        msg = f"{field_name} muss größer als 0 sein"
        raise ConfigError(msg)
    return parsed


def _optional_non_negative_float(value: object, field_name: str) -> float | None:
    """Parse an optional non-negative float config value."""
    if value is None:
        return None
    parsed = float(value)
    if parsed < 0:
        msg = f"{field_name} darf nicht negativ sein"
        raise ConfigError(msg)
    return parsed


def _optional_positive_int(value: object, field_name: str) -> int | None:
    """Parse an optional positive integer config value."""
    if value is None:
        return None
    parsed = int(value)
    if parsed <= 0:
        msg = f"{field_name} muss größer als 0 sein"
        raise ConfigError(msg)
    return parsed


def _optional_bool(value: object, field_name: str) -> bool | None:
    """Parse an optional bool config value."""
    if value is None:
        return None
    if not isinstance(value, bool):
        msg = f"{field_name} muss ein Boolean sein"
        raise ConfigError(msg)
    return value
