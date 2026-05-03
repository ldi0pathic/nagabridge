from __future__ import annotations

import asyncio
from pathlib import Path

from nagabridge.adapters.delta2.adapter import Delta2Adapter
from nagabridge.adapters.delta2max.adapter import Delta2MaxAdapter
from nagabridge.adapters.mqtt.adapter import MqttAdapter, MqttAdapterConfig
from nagabridge.adapters.powerstream.adapter import PowerstreamAdapter
from nagabridge.core.adapter import Adapter
from nagabridge.core.bus import EventBus
from nagabridge.core.config import BleDeviceConfig, load_config
from nagabridge.core.logging import configure_logging


DEFAULT_CONFIG_PATH = Path("nagabridge.toml")


def _build_ble_adapter(device: BleDeviceConfig) -> Adapter:
    if device.type == "powerstream":
        return PowerstreamAdapter(device)
    if device.type == "delta2":
        return Delta2Adapter(device)
    if device.type == "delta2max":
        return Delta2MaxAdapter(device)
    raise ValueError(f"Unsupported device type '{device.type}'")


def build_adapters_from_config(
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> list[Adapter]:
    cfg = load_config(config_path)
    adapters: list[Adapter] = [_build_ble_adapter(device) for device in cfg.devices]

    if cfg.mqtt is not None:
        adapters.append(
            MqttAdapter(
                MqttAdapterConfig(
                    host=cfg.mqtt.host,
                    port=cfg.mqtt.port,
                    user=cfg.mqtt.user,
                    password=cfg.mqtt.password,
                )
            )
        )

    configure_logging(cfg.log_level)
    return adapters


async def run(config_path: Path = DEFAULT_CONFIG_PATH) -> None:
    bus = EventBus()
    adapters = build_adapters_from_config(config_path)

    for adapter in adapters:
        await adapter.start(bus)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
