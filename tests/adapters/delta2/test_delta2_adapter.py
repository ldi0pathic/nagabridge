"""Tests for the Delta 2 BLE adapter."""

from __future__ import annotations

import asyncio

from nagabridge.adapters.delta2.adapter import Delta2Adapter
from nagabridge.adapters.delta2.commands import encode_command
from nagabridge.adapters.delta2.parser import parse_status_payload
from nagabridge.adapters.delta2.protocol import KIND_COMMAND_ACK, KIND_STATUS, decode_packets, encode_packet
from nagabridge.core.ble import BleConnectionConfig
from nagabridge.core.bus import EventBus
from nagabridge.core.config import BleDeviceConfig


class FakeConnection:
    """Connection test double used by Delta2 adapter tests."""

    def __init__(self, config: BleConnectionConfig) -> None:
        self.config = config
        self.connected = False
        self.disconnected = False
        self.reconnect_calls = 0
        self.writes: list[bytes] = []
        self.handler = None

    @property
    def is_connected(self) -> bool:
        return self.connected

    async def connect(self, notification_handler=None) -> None:  # type: ignore[no-untyped-def]
        self.connected = True
        self.handler = notification_handler

    async def reconnect(self) -> None:
        self.reconnect_calls += 1
        await self.disconnect()
        await self.connect(self.handler)

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


def _config(**overrides: object) -> BleDeviceConfig:
    values: dict[str, object] = {
        "name": "Delta2",
        "mac": "AA:BB:CC:DD:EE:FE",
        "type": "delta2",
        "poll_interval_seconds": 3600.0,
        "reconnect_backoff_seconds": 0.0,
    }
    values.update(overrides)
    return BleDeviceConfig(**values)  # type: ignore[arg-type]


def test_start_connects_ble_and_subscribes_to_stable_command_topic() -> None:
    async def scenario() -> None:
        connections: list[FakeConnection] = []

        def connection_factory(config: BleConnectionConfig) -> FakeConnection:
            connection = FakeConnection(config)
            connections.append(connection)
            return connection

        bus = EventBus()
        adapter = Delta2Adapter(_config(), connection_factory=connection_factory)  # type: ignore[arg-type]

        await adapter.start(bus)

        assert adapter.health.is_ok
        assert adapter.health.detail == "running"
        assert connections[0].connected
        assert connections[0].config.address == "AA:BB:CC:DD:EE:FE"
        assert connections[0].config.notify_uuid == "00000003-0000-1000-8000-00805f9b34fb"
        assert connections[0].config.write_uuid == "00000002-0000-1000-8000-00805f9b34fb"
        assert bus.subscriber_count("ecoflow/delta2/command") == 1
        assert adapter.published_topics == ["ecoflow/delta2/state"]

        await adapter.stop()
        assert connections[0].disconnected
        assert bus.subscriber_count("ecoflow/delta2/command") == 0

    asyncio.run(scenario())


def test_command_subscription_writes_delta2_packets() -> None:
    async def scenario() -> None:
        connection = FakeConnection(BleConnectionConfig(address="a", notify_uuid="n", write_uuid="w"))
        bus = EventBus()
        adapter = Delta2Adapter(_config(), connection_factory=lambda _cfg: connection)  # type: ignore[arg-type]

        await adapter.start(bus)
        await bus.publish("ecoflow/delta2/command", {"command": "set_xt60_input", "watts": 120})
        await asyncio.sleep(0)

        assert connection.writes == [encode_command({"command": "set_xt60_input", "watts": 120})]

        await bus.publish("ecoflow/delta2/command", {"command": "unsupported"})
        await asyncio.sleep(0)
        assert len(connection.writes) == 1

        await adapter.stop()

    asyncio.run(scenario())


def test_notification_decodes_status_and_publishes_state() -> None:
    async def scenario() -> None:
        connection = FakeConnection(BleConnectionConfig(address="a", notify_uuid="n", write_uuid="w"))
        bus = EventBus()
        states: list[dict[str, object]] = []

        async def collect_state(_topic: str, payload: dict[str, object]) -> None:
            states.append(payload)

        await bus.subscribe("ecoflow/delta2/state", collect_state)
        adapter = Delta2Adapter(_config(), connection_factory=lambda _cfg: connection)  # type: ignore[arg-type]
        await adapter.start(bus)

        payload = b"\x02\x2b\x00\x7b\x01\xc8\x00\x5a\x01"
        await connection.emit(encode_packet(KIND_STATUS, payload))
        await asyncio.sleep(0)

        assert adapter.health.is_ok
        assert states[-1]["online"] is True
        assert states[-1]["battery_percent"] == 55.5
        assert states[-1]["output_watts"] == 123
        assert states[-1]["input_watts"] == 456
        assert states[-1]["xt60_input_watts"] == 90
        assert states[-1]["ac_output_enabled"] is True

        await adapter.stop()

    asyncio.run(scenario())


def test_maintain_loop_reconnects_after_disconnect() -> None:
    async def scenario() -> None:
        connection = FakeConnection(BleConnectionConfig(address="a", notify_uuid="n", write_uuid="w"))
        adapter = Delta2Adapter(
            _config(poll_interval_seconds=0.01),
            connection_factory=lambda _cfg: connection,
        )  # type: ignore[arg-type]

        await adapter.start(EventBus())
        connection.connected = False

        await asyncio.sleep(0.03)

        assert connection.reconnect_calls >= 1
        assert connection.connected
        assert adapter.health.is_ok
        assert adapter.health.detail == "running"

        await adapter.stop()

    asyncio.run(scenario())


def test_notification_decode_failure_updates_health() -> None:
    async def scenario() -> None:
        adapter = Delta2Adapter(_config(), connection_factory=lambda cfg: FakeConnection(cfg))  # type: ignore[arg-type]
        await adapter.start(EventBus())

        await adapter._on_notification(encode_packet(KIND_STATUS, b"short"))  # noqa: SLF001

        assert adapter.health.is_ok

        await adapter._on_notification(bytes((0xAA, KIND_STATUS, 255)))  # noqa: SLF001
        assert adapter.health.is_ok

        await adapter.stop()

    asyncio.run(scenario())


def test_parser_protocol_and_command_helpers_cover_edge_cases() -> None:
    assert parse_status_payload(b"short") == {"raw_len": 5}

    packet_bytes = encode_packet(KIND_STATUS, b"abc")
    packets, remaining = decode_packets(b"noise" + packet_bytes[:2], bytearray())
    assert packets == []
    packets, remaining = decode_packets(packet_bytes[2:], remaining)
    assert [(packet.kind, packet.payload) for packet in packets] == [(KIND_STATUS, b"abc")]
    assert remaining == bytearray()

    assert encode_command({"type": "refresh"}) == encode_packet(KIND_COMMAND_ACK, b"\x01")
    assert encode_command({"command": "set_ac_output", "enabled": False}) == encode_packet(KIND_COMMAND_ACK, b"\x10\x00")
    assert encode_command({"command": "set_xt60_input", "watts": 999}) == encode_packet(KIND_COMMAND_ACK, b"\x11\x01\xf4")
    assert encode_command({"command": "unknown"}) is None
