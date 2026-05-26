"""Lifecycle tests for stub adapters."""

import asyncio

from nagabridge.adapters.delta2.adapter import Delta2Adapter
from nagabridge.adapters.delta2max.adapter import Delta2MaxAdapter
from nagabridge.adapters.powerstream.adapter import PowerstreamAdapter
from nagabridge.core.bus import EventBus
from nagabridge.core.config import BleDeviceConfig
from tests.adapters.powerstream.test_adapter import FakeConnection, FakeCrypto


def _cfg(name: str, type_: str, serial_number: str | None = None) -> BleDeviceConfig:
    return BleDeviceConfig(name=name, mac="AA:BB:CC:DD:EE:FF", type=type_, serial_number=serial_number)


def _ensure(condition: object, message: str) -> None:
    """Raise AssertionError when a condition is not met."""
    if not condition:
        raise AssertionError(message)


def test_stub_adapter_lifecycle_health_states() -> None:
    """Verify start/stop lifecycle updates health correctly for all stubs."""

    async def scenario() -> None:
        bus = EventBus()
        adapters = [
            PowerstreamAdapter(
                _cfg("Powerstream", "powerstream", serial_number="SN123"),
                connection_factory=lambda cfg: FakeConnection(cfg),
                crypto_factory=lambda _sn: FakeCrypto("SN123"),
            )
        ]

        for adapter in adapters:
            _ensure(adapter.health.is_failed, "Adapter must start offline")
            _ensure(
                adapter.health.detail == "not started",
                "Adapter must start with 'not started' detail",
            )

            ts_before = adapter.health.timestamp
            health_published: list[dict[str, object]] = []
            topic = f"system/health/{adapter.name.lower()}"

            async def health_handler(
                _t: str,
                payload: dict[str, object],
                _published: list[dict[str, object]] = health_published,
            ) -> None:
                _published.append(payload)

            await bus.subscribe(topic, health_handler)
            await adapter.start(bus)
            _ensure(
                adapter.health.is_ok,
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
            await asyncio.sleep(0)
            _ensure(
                adapter.health.timestamp >= ts_running,
                "Adapter timestamp must be monotonic across stop()",
            )
            _ensure(
                adapter.health.is_failed,
                "Adapter must be offline after stop()",
            )
            _ensure(
                adapter.health.detail == "stopped",
                "Adapter detail must be 'stopped' after stop()",
            )
            _ensure(
                any(p.get("detail") == "stopped" for p in health_published),
                f"'stopped' health was never published to the bus for {adapter.name}",
            )

    asyncio.run(scenario())


def test_delta_adapters_start_in_prototype_mode() -> None:
    """Delta adapters should expose prototype mode until BLE protocol is integrated."""

    async def scenario() -> None:
        bus = EventBus()
        adapters = [
            Delta2Adapter(_cfg("Delta2", "delta2")),
            Delta2MaxAdapter(_cfg("Delta2Max", "delta2max")),
        ]

        for adapter in adapters:
            await adapter.start(bus)
            _ensure(
                adapter.health.is_degraded,
                "Prototype adapter must stay degraded after start()",
            )
            _ensure(
                adapter.health.detail == "prototype mode",
                "Prototype adapter detail must explain provisional runtime state",
            )

    asyncio.run(scenario())
