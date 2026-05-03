"""TOML configuration loading and validation."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

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
    mqtt_data = data.get("mqtt")
    adapters = data.get("adapters", {})

    log_level = system.get("log_level", "INFO")
    if log_level not in VALID_LOG_LEVELS:
        msg = f"Ungültiger log_level '{log_level}'"
        raise ConfigError(msg)

    devices = []
    for idx, d in enumerate(adapters.get("ble_device", []), start=1):
        for required in ("name", "mac", "type"):
            if required not in d:
                msg = f"adapters.ble_device[{idx}] fehlt Feld '{required}'"
                raise ConfigError(msg)
        if d["type"] not in VALID_DEVICE_TYPES:
            msg = f"Ungültiger Gerätetyp '{d['type']}'"
            raise ConfigError(msg)
        if not MAC_RE.match(d["mac"]):
            msg = f"Ungültige MAC-Adresse '{d['mac']}'"
            raise ConfigError(msg)
        devices.append(BleDeviceConfig(name=d["name"], mac=d["mac"], type=d["type"]))

    mqtt = None
    if mqtt_data is not None:
        if "host" not in mqtt_data or not str(mqtt_data["host"]).strip():
            msg = "mqtt.host fehlt oder ist leer"
            raise ConfigError(msg)
        port = int(mqtt_data.get("port", 1883))
        if port <= 0 or port > MAX_TCP_PORT:
            msg = f"Ungültiger mqtt.port '{port}'"
            raise ConfigError(msg)
        mqtt = MqttConfig(
            host=mqtt_data["host"],
            port=port,
            user=mqtt_data.get("user"),
            password=mqtt_data.get("password"),
        )

    return NagaBridgeConfig(log_level=log_level, devices=devices, mqtt=mqtt)
