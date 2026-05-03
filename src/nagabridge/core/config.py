from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Literal
import tomllib

VALID_DEVICE_TYPES = {"powerstream", "delta2max", "delta2"}
VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}
MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


class ConfigError(ValueError):
    pass


@dataclass(slots=True)
class BleDeviceConfig:
    name: str
    mac: str
    type: Literal["powerstream", "delta2max", "delta2"]


@dataclass(slots=True)
class MqttConfig:
    host: str
    port: int = 1883
    user: str | None = None
    password: str | None = None


@dataclass(slots=True)
class NagaBridgeConfig:
    log_level: str = "INFO"
    devices: list[BleDeviceConfig] = field(default_factory=list)
    mqtt: MqttConfig | None = None


def load_config(path: str | Path) -> NagaBridgeConfig:
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))

    system = data.get("system", {})
    mqtt_data = data.get("mqtt")
    adapters = data.get("adapters", {})

    log_level = system.get("log_level", "INFO")
    if log_level not in VALID_LOG_LEVELS:
        raise ConfigError(f"Ungültiger log_level '{log_level}'")

    devices = []
    for idx, d in enumerate(adapters.get("ble_device", []), start=1):
        for required in ("name", "mac", "type"):
            if required not in d:
                raise ConfigError(f"adapters.ble_device[{idx}] fehlt Feld '{required}'")
        if d["type"] not in VALID_DEVICE_TYPES:
            raise ConfigError(f"Ungültiger Gerätetyp '{d['type']}'")
        if not MAC_RE.match(d["mac"]):
            raise ConfigError(f"Ungültige MAC-Adresse '{d['mac']}'")
        devices.append(BleDeviceConfig(name=d["name"], mac=d["mac"], type=d["type"]))

    mqtt = None
    if mqtt_data is not None:
        if "host" not in mqtt_data or not str(mqtt_data["host"]).strip():
            raise ConfigError("mqtt.host fehlt oder ist leer")
        port = int(mqtt_data.get("port", 1883))
        if port <= 0 or port > 65535:
            raise ConfigError(f"Ungültiger mqtt.port '{port}'")
        mqtt = MqttConfig(
            host=mqtt_data["host"],
            port=port,
            user=mqtt_data.get("user"),
            password=mqtt_data.get("password"),
        )

    return NagaBridgeConfig(log_level=log_level, devices=devices, mqtt=mqtt)
