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


def test_delta2_starts_with_ble_connection_and_delta2max_remains_prototype() -> None:
    """Delta2 should use BLE while Delta2Max remains in prototype mode."""

    async def scenario() -> None:
        bus = EventBus()
        delta2_connections: list[FakeConnection] = []

        def delta2_connection_factory(config: object) -> FakeConnection:
            connection = FakeConnection(config)  # type: ignore[arg-type]
            delta2_connections.append(connection)
            return connection

        delta2 = Delta2Adapter(_cfg("Delta2", "delta2"), connection_factory=delta2_connection_factory)  # type: ignore[arg-type]
        delta2max = Delta2MaxAdapter(_cfg("Delta2Max", "delta2max"))

        await delta2.start(bus)
        _ensure(delta2.health.is_ok, "Delta2 BLE adapter must be online after start()")
        _ensure(delta2.health.detail == "running", "Delta2 BLE adapter detail must report running state")
        _ensure(delta2_connections[0].connected, "Delta2 BLE adapter must connect to BLE on start()")
        await delta2.stop()

        await delta2max.start(bus)
        _ensure(
            delta2max.health.is_degraded,
            "Delta2Max prototype adapter must stay degraded after start()",
        )
        _ensure(
            delta2max.health.detail == "prototype mode",
            "Delta2Max prototype adapter detail must explain provisional runtime state",
        )
        await delta2max.stop()

    asyncio.run(scenario())
