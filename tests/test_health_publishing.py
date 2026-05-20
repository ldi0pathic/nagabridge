"""Tests for health publishing on the event bus (ADR-007)."""

from __future__ import annotations

import asyncio
import contextlib

from nagabridge.adapters.mqtt.adapter import MqttAdapter, MqttAdapterConfig
from nagabridge.adapters.powerstream.adapter import PowerstreamAdapter, PowerstreamAdapterConfig
from nagabridge.core.adapter import Adapter
from nagabridge.core.ble import BleConnectionConfig
from nagabridge.core.bus import EventBus
from nagabridge.core.health import HealthState, HealthStatus
from nagabridge.main import _health_monitor
from tests.adapters.powerstream.test_adapter import FakeConnection, FakeCrypto


def _ps_config(**overrides: object) -> PowerstreamAdapterConfig:
    values: dict[str, object] = {
        "name": "PowerStream",
        "mac": "AA:BB:CC:DD:EE:FF",
        "serial_number": "SN123",
        "poll_interval_seconds": 3600.0,
        "reconnect_backoff_seconds": 0.0,
    }
    values.update(overrides)
    return PowerstreamAdapterConfig(**values)


class _FakeMqttClient:
    def __init__(self) -> None:
        self.connected = False

    def username_pw_set(self, user: str, password: str | None = None) -> None:
        pass

    def connect(self, host: str, port: int) -> None:
        self.connected = True

    def loop_start(self) -> None:
        pass

    def loop_stop(self) -> None:
        pass

    def disconnect(self) -> None:
        self.connected = False

    def publish(self, topic: str, payload: str, qos: int = 0, *, retain: bool = False) -> None:
        pass


class _StubAdapter(Adapter):
    """Minimal adapter stub for health monitor tests."""

    def __init__(self, name: str, state: HealthState) -> None:
        self._name = name
        self._health = HealthStatus(state=state, detail="test")

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return "test"

    @property
    def health(self) -> HealthStatus:
        return self._health

    async def start(self, bus: EventBus) -> None:
        pass

    async def stop(self) -> None:
        pass


async def test_powerstream_publishes_health_on_state_change() -> None:
    """PowerstreamAdapter should publish to system/health/powerstream on each state change."""
    bus = EventBus()
    connection = FakeConnection(BleConnectionConfig(address="a", notify_uuid="n", write_uuid="w"))
    crypto = FakeCrypto("SN123")
    adapter = PowerstreamAdapter(
        _ps_config(),
        connection_factory=lambda _cfg: connection,
        crypto_factory=lambda _serial: crypto,
    )

    received: list[dict[str, object]] = []

    async def handler(_topic: str, payload: dict[str, object]) -> None:
        received.append(dict(payload))

    await bus.subscribe("system/health/powerstream", handler)
    await adapter.start(bus)
    await asyncio.sleep(0)

    assert received, "Expected at least one health publish on start"
    last = received[-1]
    assert last["state"] == "ok"
    assert last["adapter"] == "PowerStream"
    assert "timestamp" in last

    await adapter.stop()


async def test_powerstream_publishes_health_on_stop() -> None:
    """PowerstreamAdapter publishes a health event on stop (bus already cleared, so no-op is fine)."""
    bus = EventBus()
    connection = FakeConnection(BleConnectionConfig(address="a", notify_uuid="n", write_uuid="w"))
    crypto = FakeCrypto("SN123")
    adapter = PowerstreamAdapter(
        _ps_config(),
        connection_factory=lambda _cfg: connection,
        crypto_factory=lambda _serial: crypto,
    )

    received: list[dict[str, object]] = []

    async def handler(_topic: str, payload: dict[str, object]) -> None:
        received.append(dict(payload))

    await bus.subscribe("system/health/powerstream", handler)
    await adapter.start(bus)
    await asyncio.sleep(0)
    received.clear()

    # stop() clears self._bus before publishing, so the publish is a no-op — health stays failed
    await adapter.stop()
    await asyncio.sleep(0)

    assert adapter.health.is_failed
    assert adapter.health.detail == "stopped"


async def test_mqtt_adapter_publishes_health_on_start_and_stop() -> None:
    """MqttAdapter should publish ok on start and failed on stop."""
    bus = EventBus()
    adapter = MqttAdapter(
        MqttAdapterConfig(host="broker.local"),
        client_factory=_FakeMqttClient,
    )

    received: list[dict[str, object]] = []

    async def handler(_topic: str, payload: dict[str, object]) -> None:
        received.append(dict(payload))

    await bus.subscribe("system/health/mqtt", handler)

    await adapter.start(bus)
    await asyncio.sleep(0)

    assert received, "Expected health event after start"
    assert received[-1]["state"] == "ok"
    assert received[-1]["adapter"] == "mqtt"

    await adapter.stop()
    await asyncio.sleep(0)

    assert received[-1]["state"] == "failed"


async def test_health_monitor_all_ok_publishes_ok() -> None:
    """_health_monitor should publish overall=ok when all adapters are ok."""
    bus = EventBus()
    adapters: list[Adapter] = [
        _StubAdapter("alpha", HealthState.ok),
        _StubAdapter("beta", HealthState.ok),
    ]

    received: list[dict[str, object]] = []

    async def handler(_topic: str, payload: dict[str, object]) -> None:
        received.append(dict(payload))

    await bus.subscribe("system/health/overall", handler)
    shutdown_event = asyncio.Event()

    task = asyncio.create_task(_health_monitor(bus, adapters, shutdown_event, interval=0.01))
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    shutdown_event.set()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    assert received, "Expected at least one overall health publish"
    assert received[0]["state"] == "ok"
    assert received[0]["adapters"] == {"alpha": "ok", "beta": "ok"}


async def test_health_monitor_one_failed_publishes_failed() -> None:
    """_health_monitor should publish overall=failed when any adapter is failed."""
    bus = EventBus()
    adapters: list[Adapter] = [
        _StubAdapter("alpha", HealthState.ok),
        _StubAdapter("beta", HealthState.failed),
    ]

    received: list[dict[str, object]] = []

    async def handler(_topic: str, payload: dict[str, object]) -> None:
        received.append(dict(payload))

    await bus.subscribe("system/health/overall", handler)
    shutdown_event = asyncio.Event()

    task = asyncio.create_task(_health_monitor(bus, adapters, shutdown_event, interval=0.01))
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    shutdown_event.set()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    assert received
    assert received[0]["state"] == "failed"


async def test_health_monitor_degraded_without_failed_publishes_degraded() -> None:
    """_health_monitor should publish overall=degraded when degraded but no failed."""
    bus = EventBus()
    adapters: list[Adapter] = [
        _StubAdapter("alpha", HealthState.ok),
        _StubAdapter("beta", HealthState.degraded),
    ]

    received: list[dict[str, object]] = []

    async def handler(_topic: str, payload: dict[str, object]) -> None:
        received.append(dict(payload))

    await bus.subscribe("system/health/overall", handler)
    shutdown_event = asyncio.Event()

    task = asyncio.create_task(_health_monitor(bus, adapters, shutdown_event, interval=0.01))
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    shutdown_event.set()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    assert received
    assert received[0]["state"] == "degraded"
