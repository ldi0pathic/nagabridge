"""Tests for the PowerStream adapter core."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from nagabridge.adapters.powerstream.adapter import PowerstreamAdapter, PowerstreamAdapterConfig
from nagabridge.core.ble import BleConnectionConfig
from nagabridge.core.bus import EventBus


class FakeConnection:
    """Connection test double used by adapter tests."""

    def __init__(self, config: BleConnectionConfig) -> None:
        self.config = config
        self.connected = False
        self.disconnected = False
        self.writes: list[bytes] = []
        self.handler: Callable[[bytes], Awaitable[None] | None] | None = None

    async def connect(self, notification_handler: Callable[[bytes], Awaitable[None] | None] | None = None) -> None:
        self.connected = True
        self.handler = notification_handler

    async def disconnect(self) -> None:
        self.disconnected = True
        self.connected = False

    async def write(self, data: bytes, *, response: bool | None = None) -> None:
        _ = response
        self.writes.append(data)

    async def emit(self, data: bytes) -> None:
        assert self.handler is not None
        result = self.handler(data)
        if asyncio.iscoroutine(result):
            await result


def _config(**overrides: object) -> PowerstreamAdapterConfig:
    values = {
        "name": "PowerStream",
        "mac": "AA:BB:CC:DD:EE:FF",
        "serial_number": "SN123",
        "poll_interval_seconds": 3600.0,
        "reconnect_backoff_seconds": 0.0,
    }
    values.update(overrides)
    return PowerstreamAdapterConfig(**values)  # type: ignore[arg-type]


def _packet_encoder(cmd_set: int, cmd_id: int, payload: bytes) -> bytes:
    return bytes([cmd_set, cmd_id]) + payload


def test_start_connects_ble_and_subscribes_to_command_topic() -> None:
    async def scenario() -> None:
        created: list[FakeConnection] = []

        def factory(config: BleConnectionConfig) -> FakeConnection:
            connection = FakeConnection(config)
            created.append(connection)
            return connection

        bus = EventBus()
        adapter = PowerstreamAdapter(_config(), connection_factory=factory, packet_encoder=_packet_encoder)  # type: ignore[arg-type]

        await adapter.start(bus)

        assert adapter.health.online
        assert adapter.health.detail == "running"
        assert created[0].connected
        assert created[0].config.address == "AA:BB:CC:DD:EE:FF"
        assert created[0].config.notify_uuid == "00000003-0000-1000-8000-00805f9b34fb"
        assert bus.subscriber_count("ecoflow/powerstream/command") == 1

        await adapter.stop()

    asyncio.run(scenario())


def test_start_without_serial_keeps_legacy_lifecycle_without_ble() -> None:
    async def scenario() -> None:
        bus = EventBus()
        adapter = PowerstreamAdapter(_config(serial_number=None), connection_factory=lambda _cfg: None)  # type: ignore[arg-type,return-value]

        await adapter.start(bus)

        assert adapter.health.online
        assert adapter.health.detail == "running"
        assert bus.subscriber_count("ecoflow/powerstream/command") == 1

        await adapter.stop()
        assert not adapter.health.online

    asyncio.run(scenario())


def test_command_set_load_power_writes_encoded_packet() -> None:
    async def scenario() -> None:
        connection = FakeConnection(BleConnectionConfig(address="a", notify_uuid="n", write_uuid="w"))
        adapter = PowerstreamAdapter(_config(), connection_factory=lambda _cfg: connection, packet_encoder=_packet_encoder)  # type: ignore[arg-type]
        bus = EventBus()

        await adapter.start(bus)
        await bus.publish("ecoflow/powerstream/command", {"command": "set_load_power", "watts": 600})
        await asyncio.sleep(0)

        assert connection.writes[-1] == b"\x02\x23" + bytes([0x58, 0x02])

        await adapter.stop()

    asyncio.run(scenario())


def test_notification_is_parsed_and_published_to_state_topic() -> None:
    async def scenario() -> None:
        connection = FakeConnection(BleConnectionConfig(address="a", notify_uuid="n", write_uuid="w"))
        adapter = PowerstreamAdapter(_config(serial_number=None), connection_factory=lambda _cfg: connection, packet_encoder=_packet_encoder)  # type: ignore[arg-type]
        bus = EventBus()
        received: list[dict[str, object]] = []

        async def handler(_topic: str, payload: dict[str, object]) -> None:
            received.append(payload)

        await bus.subscribe("ecoflow/powerstream/state", handler)
        await adapter.start(bus)
        await adapter._on_notification(b"\xf8\x01\x37")  # field 31 / bat_soc = 55
        await asyncio.sleep(0)

        assert received[-1]["message_type"] == "inverter_heartbeat"
        assert received[-1]["bat_soc"] == 55

        await adapter.stop()

    asyncio.run(scenario())


def test_stop_unsubscribes_and_disconnects() -> None:
    async def scenario() -> None:
        connection = FakeConnection(BleConnectionConfig(address="a", notify_uuid="n", write_uuid="w"))
        bus = EventBus()
        adapter = PowerstreamAdapter(_config(), connection_factory=lambda _cfg: connection, packet_encoder=_packet_encoder)  # type: ignore[arg-type]

        await adapter.start(bus)
        await adapter.stop()

        assert connection.disconnected
        assert bus.subscriber_count("ecoflow/powerstream/command") == 0
        assert not adapter.health.online
        assert adapter.health.detail == "stopped"

    asyncio.run(scenario())
