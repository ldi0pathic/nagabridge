from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
import tomllib


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
    mqtt_data = data.get("mqtt", {})
    adapters = data.get("adapters", {})

    devices = [
        BleDeviceConfig(name=d["name"], mac=d["mac"], type=d["type"])
        for d in adapters.get("ble_device", [])
    ]

    mqtt = None
    if mqtt_data:
        mqtt = MqttConfig(
            host=mqtt_data["host"],
            port=int(mqtt_data.get("port", 1883)),
            user=mqtt_data.get("user"),
            password=mqtt_data.get("password"),
        )

    return NagaBridgeConfig(
        log_level=system.get("log_level", "INFO"),
        devices=devices,
        mqtt=mqtt,
    )
