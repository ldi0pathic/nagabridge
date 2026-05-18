"""Lifecycle tests for stub adapters."""

import asyncio

from nagabridge.adapters.delta2.adapter import Delta2Adapter
from nagabridge.adapters.delta2max.adapter import Delta2MaxAdapter
from nagabridge.adapters.powerstream.adapter import PowerstreamAdapter
from nagabridge.core.bus import EventBus
from nagabridge.core.config import BleDeviceConfig


def _cfg(name: str, type_: str) -> BleDeviceConfig:
    """Build a deterministic BLE config for tests."""
    return BleDeviceConfig(name=name, mac="AA:BB:CC:DD:EE:FF", type=type_)


def _ensure(condition: object, message: str) -> None:
    """Raise AssertionError when a condition is not met."""
    if not condition:
        raise AssertionError(message)


def test_stub_adapter_lifecycle_health_states() -> None:
    """Verify start/stop lifecycle updates health correctly for all stubs."""

    async def scenario() -> None:
        bus = EventBus()
        adapters = [PowerstreamAdapter(_cfg("Powerstream", "powerstream"))]

        for adapter in adapters:
            _ensure(adapter.health.online is False, "Adapter must start offline")
            _ensure(
                adapter.health.detail == "not started",
                "Adapter must start with 'not started' detail",
            )

            ts_before = adapter.health.timestamp

            await adapter.start(bus)
            _ensure(
                adapter.health.online is True,
                "Adapter must be online after start()",
            )
            _ensure(
                adapter.health.detail == "running",
                "Adapter detail must be 'running' after start()",
            )
            _ensure(
                adapter.health.timestamp >= ts_before,
                "Adapter timestamp must be monotonic across start()",
            )

            ts_running = adapter.health.timestamp
            await adapter.stop()
            _ensure(
                adapter.health.timestamp >= ts_running,
                "Adapter timestamp must be monotonic across stop()",
            )
            _ensure(
                adapter.health.online is False,
                "Adapter must be offline after stop()",
            )
            _ensure(
                adapter.health.detail == "stopped",
                "Adapter detail must be 'stopped' after stop()",
            )

    asyncio.run(scenario())


def test_unimplemented_delta_adapters_stay_offline_after_start() -> None:
    """Delta stubs must not report production readiness before Type7 exists."""

    async def scenario() -> None:
        bus = EventBus()
        adapters = [
            Delta2Adapter(_cfg("Delta2", "delta2")),
            Delta2MaxAdapter(_cfg("Delta2Max", "delta2max")),
        ]

        for adapter in adapters:
            await adapter.start(bus)
            _ensure(
                adapter.health.online is False,
                "Unimplemented adapter must stay offline after start()",
            )
            _ensure(
                adapter.health.detail == "not implemented",
                "Unimplemented adapter detail must explain unavailable state",
            )

    asyncio.run(scenario())
