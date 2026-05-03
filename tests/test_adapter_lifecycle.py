import asyncio

from nagabridge.adapters.delta2.adapter import Delta2Adapter
from nagabridge.adapters.delta2max.adapter import Delta2MaxAdapter
from nagabridge.adapters.powerstream.adapter import PowerstreamAdapter
from nagabridge.core.bus import EventBus
from nagabridge.core.config import BleDeviceConfig


def _cfg(name: str, type_: str) -> BleDeviceConfig:
    return BleDeviceConfig(name=name, mac="AA:BB:CC:DD:EE:FF", type=type_)


def test_stub_adapter_lifecycle_health_states():
    async def scenario():
        bus = EventBus()
        adapters = [
            PowerstreamAdapter(_cfg("Powerstream", "powerstream")),
            Delta2Adapter(_cfg("Delta2", "delta2")),
            Delta2MaxAdapter(_cfg("Delta2Max", "delta2max")),
        ]

        for adapter in adapters:
            assert adapter.health.online is False
            assert adapter.health.detail == "not started"

            await adapter.start(bus)
            assert adapter.health.online is True
            assert adapter.health.detail == "running"

            await adapter.stop()
            assert adapter.health.online is False
            assert adapter.health.detail == "stopped"

    asyncio.run(scenario())
