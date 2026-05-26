"""Tests for the PowerStream adapter core."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from nagabridge.adapters.powerstream.adapter import PowerstreamAdapter, PowerstreamAdapterConfig
from nagabridge.core.ble import BleConnectionConfig
from nagabridge.core.bus import EventBus


@dataclass(slots=True)
class FakePacket:
    """Decoded packet fixture returned by fake crypto."""

    src: int
    dst: int
    cmd_set: int
    cmd_id: int
    payload: bytes


class FakeCrypto:
    """Type1Crypto-compatible fake used by adapter tests."""

    def __init__(self, serial_number: str) -> None:
        self.serial_number = serial_number
        self.encoded_packets: list[Any] = []
        self.decoded_packets: list[FakePacket] = []

    def encode_packet(self, packet: Any) -> bytes:
        self.encoded_packets.append(packet)
        return bytes([packet.cmd_set, packet.cmd_id]) + packet.payload

    def decode_packets(self, data: bytes, buffer: bytearray) -> tuple[list[FakePacket], bytearray]:
        assert buffer == bytearray()
        if data == b"status":
            return self.decoded_packets, bytearray()
        return [], bytearray(data)


class FakeConnection:
    """Connection test double used by adapter tests."""

    def __init__(self, config: BleConnectionConfig) -> None:
        self.config = config
        self.connected = False
        self.disconnected = False
        self.connect_calls = 0
        self.reconnect_calls = 0
        self.write_failures_remaining = 0
        self.writes: list[bytes] = []
        self.handler: Callable[[bytes], Awaitable[None] | None] | None = None

    @property
    def is_connected(self) -> bool:
        return self.connected

    async def connect(self, notification_handler: Callable[[bytes], Awaitable[None] | None] | None = None) -> None:
        self.connect_calls += 1
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
        if self.write_failures_remaining > 0:
            self.write_failures_remaining -= 1
            raise RuntimeError("write failed")
        self.writes.append(data)

    async def emit(self, data: bytes) -> None:
        assert self.handler is not None
        result = self.handler(data)
        if asyncio.iscoroutine(result):
            await result


def _config(**overrides: object) -> PowerstreamAdapterConfig:
    values: dict[str, object] = {
        "name": "PowerStream",
        "mac": "AA:BB:CC:DD:EE:FF",
        "serial_number": "SN123",
        "poll_interval_seconds": 3600.0,
        "reconnect_backoff_seconds": 0.0,
    }
    values.update(overrides)
    return PowerstreamAdapterConfig(**values)


def test_start_connects_ble_subscribes_and_initializes_crypto() -> None:
    async def scenario() -> None:
        created_connections: list[FakeConnection] = []
        created_crypto: list[FakeCrypto] = []

        def connection_factory(config: BleConnectionConfig) -> FakeConnection:
            connection = FakeConnection(config)
            created_connections.append(connection)
            return connection

        def crypto_factory(serial_number: str) -> FakeCrypto:
            crypto = FakeCrypto(serial_number)
            created_crypto.append(crypto)
            return crypto

        bus = EventBus()
        adapter = PowerstreamAdapter(_config(), connection_factory=connection_factory, crypto_factory=crypto_factory)  # type: ignore[arg-type]

        await adapter.start(bus)

        assert adapter.health.is_ok
        assert adapter.health.detail == "running"
        assert created_crypto[0].serial_number == "SN123"
        assert created_connections[0].connected
        assert created_connections[0].config.address == "AA:BB:CC:DD:EE:FF"
        assert created_connections[0].config.notify_uuid == "00000003-0000-1000-8000-00805f9b34fb"
        assert bus.subscriber_count("ecoflow/powerstream/command") == 1

        await adapter.stop()

    asyncio.run(scenario())


def test_maintain_loop_reconnects_after_runtime_disconnect() -> None:
    async def scenario() -> None:
        connection = FakeConnection(BleConnectionConfig(address="a", notify_uuid="n", write_uuid="w"))
        crypto = FakeCrypto("SN123")
        adapter = PowerstreamAdapter(
            _config(poll_interval_seconds=0.01),
            connection_factory=lambda _cfg: connection,
            crypto_factory=lambda _serial: crypto,
        )  # type: ignore[arg-type]

        await adapter.start(EventBus())
        adapter._rx_buffer = bytearray(b"partial")  # type: ignore[attr-defined]
        connection.connected = False

        await asyncio.sleep(0.03)

        assert connection.reconnect_calls >= 1
        assert connection.connected
        assert adapter.health.is_ok
        assert adapter.health.detail == "running"
        assert adapter._rx_buffer == bytearray()  # type: ignore[attr-defined]
        assert connection.handler is not None

        await adapter.stop()

    asyncio.run(scenario())


def test_maintain_loop_reconnects_after_poll_write_failure() -> None:
    async def scenario() -> None:
        connection = FakeConnection(BleConnectionConfig(address="a", notify_uuid="n", write_uuid="w"))
        crypto = FakeCrypto("SN123")
        adapter = PowerstreamAdapter(
            _config(poll_interval_seconds=0.01),
            connection_factory=lambda _cfg: connection,
            crypto_factory=lambda _serial: crypto,
        )  # type: ignore[arg-type]

        await adapter.start(EventBus())
        connection.write_failures_remaining = 1

        await asyncio.sleep(0.03)

        assert connection.reconnect_calls >= 1
        assert connection.connected
        assert adapter.health.is_ok
        assert adapter.health.detail == "running"

        await adapter.stop()

    asyncio.run(scenario())


def test_start_without_serial_keeps_legacy_lifecycle_without_ble() -> None:
    async def scenario() -> None:
        bus = EventBus()
        adapter = PowerstreamAdapter(_config(serial_number=None), connection_factory=lambda _cfg: None)  # type: ignore[arg-type,return-value]

        await adapter.start(bus)

        assert adapter.health.is_degraded
        assert adapter.health.detail == "no serial number configured"
        assert bus.subscriber_count("ecoflow/powerstream/command") == 1

        await adapter.stop()
        assert adapter.health.is_failed

    asyncio.run(scenario())


def test_command_set_load_power_writes_type1_encoded_packet() -> None:
    async def scenario() -> None:
        connection = FakeConnection(BleConnectionConfig(address="a", notify_uuid="n", write_uuid="w"))
        crypto = FakeCrypto("SN123")
        adapter = PowerstreamAdapter(_config(), connection_factory=lambda _cfg: connection, crypto_factory=lambda _serial: crypto)  # type: ignore[arg-type]
        bus = EventBus()

        await adapter.start(bus)
        await bus.publish("ecoflow/powerstream/command", {"command": "set_load_power", "watts": 600})
        await asyncio.sleep(0)

        encoded_packet = crypto.encoded_packets[-1]
        assert encoded_packet.cmd_set == 0x14
        assert encoded_packet.cmd_id == 0x81
        # Protobuf permanent_watts_pack(permanent_watts=6000) = \x08\xf0\x2e
        from nagabridge.adapters.powerstream.wn511_sys_pb2 import permanent_watts_pack  # type: ignore[attr-defined]

        expected_payload = permanent_watts_pack(permanent_watts=6000).SerializeToString()
        assert encoded_packet.payload == expected_payload

        await adapter.stop()

    asyncio.run(scenario())


def test_authentication_writes_auth_packet_when_user_id_is_configured() -> None:
    async def scenario() -> None:
        connection = FakeConnection(BleConnectionConfig(address="a", notify_uuid="n", write_uuid="w"))
        crypto = FakeCrypto("SN123")
        adapter = PowerstreamAdapter(
            _config(user_id="user"),
            connection_factory=lambda _cfg: connection,
            crypto_factory=lambda _serial: crypto,
        )  # type: ignore[arg-type]

        await adapter.start(EventBus())

        assert crypto.encoded_packets[0].cmd_set == 0x35
        assert crypto.encoded_packets[0].cmd_id == 0x89
        assert len(crypto.encoded_packets[0].payload) == 0

        assert crypto.encoded_packets[1].cmd_set == 0x35
        assert crypto.encoded_packets[1].cmd_id == 0x86
        assert len(crypto.encoded_packets[1].payload) == 32

        await adapter.stop()

    asyncio.run(scenario())


def test_notification_is_decoded_parsed_and_published_to_state_topic() -> None:
    async def scenario() -> None:
        connection = FakeConnection(BleConnectionConfig(address="a", notify_uuid="n", write_uuid="w"))
        crypto = FakeCrypto("SN123")
        from nagabridge.adapters.powerstream.wn511_sys_pb2 import inverter_heartbeat  # type: ignore[attr-defined]

        hb = inverter_heartbeat()
        hb.bat_soc = 55
        crypto.decoded_packets.append(FakePacket(src=1, dst=2, cmd_set=0x14, cmd_id=0x01, payload=hb.SerializeToString()))
        adapter = PowerstreamAdapter(_config(), connection_factory=lambda _cfg: connection, crypto_factory=lambda _serial: crypto)  # type: ignore[arg-type]
        bus = EventBus()
        received: list[dict[str, object]] = []

        async def handler(_topic: str, payload: dict[str, object]) -> None:
            received.append(payload)

        await bus.subscribe("ecoflow/powerstream/state", handler)
        await adapter.start(bus)
        await connection.emit(b"status")
        await asyncio.sleep(0)

        assert received[-1]["message_type"] == "inverter_heartbeat"
        assert received[-1]["bat_soc"] == 55

        await adapter.stop()

    asyncio.run(scenario())


def test_stop_unsubscribes_and_disconnects() -> None:
    async def scenario() -> None:
        connection = FakeConnection(BleConnectionConfig(address="a", notify_uuid="n", write_uuid="w"))
        bus = EventBus()
        adapter = PowerstreamAdapter(_config(), connection_factory=lambda _cfg: connection, crypto_factory=lambda _serial: FakeCrypto("SN123"))  # type: ignore[arg-type]
        health_published: list[dict[str, object]] = []

        async def health_handler(_topic: str, payload: dict[str, object]) -> None:
            health_published.append(payload)

        await bus.subscribe("system/health/powerstream", health_handler)
        await adapter.start(bus)
        await adapter.stop()
        await asyncio.sleep(0)

        assert connection.disconnected
        assert bus.subscriber_count("ecoflow/powerstream/command") == 0
        assert adapter.health.is_failed
        assert adapter.health.detail == "stopped"
        stopped_payloads = [p for p in health_published if p.get("detail") == "stopped"]
        assert stopped_payloads, "'stopped' health was never published to the bus"

    asyncio.run(scenario())


def test_adapter_config_from_ble_device_uses_powerstream_specific_fields() -> None:
    from nagabridge.core.config import BleDeviceConfig

    config = PowerstreamAdapterConfig.from_ble_device(
        BleDeviceConfig(
            name="Powerstream",
            mac="AA:BB:CC:DD:EE:FF",
            type="powerstream",
            serial_number="SN123",
            user_id="USER42",
            poll_interval_seconds=15.0,
            reconnect_attempts=5,
            reconnect_backoff_seconds=0.25,
            write_with_response=True,
        ),
    )

    assert config.serial_number == "SN123"
    assert config.user_id == "USER42"
    assert config.poll_interval_seconds == 15.0
    assert config.reconnect_attempts == 5
    assert config.reconnect_backoff_seconds == 0.25
    assert config.write_with_response is True


def test_authentication_skips_when_user_id_is_missing() -> None:
    async def scenario() -> None:
        connection = FakeConnection(BleConnectionConfig(address="a", notify_uuid="n", write_uuid="w"))
        crypto = FakeCrypto("SN123")
        adapter = PowerstreamAdapter(_config(user_id=None), connection_factory=lambda _cfg: connection, crypto_factory=lambda _serial: crypto)  # type: ignore[arg-type]

        await adapter.start(EventBus())

        assert adapter._authenticated is False  # type: ignore[attr-defined]
        assert connection.writes == []

        await adapter.stop()

    asyncio.run(scenario())


def test_authentication_failure_sets_health_and_keeps_maintain_loop_running() -> None:
    class FailingCrypto(FakeCrypto):
        def encode_packet(self, packet: object) -> bytes:
            raise RuntimeError("encode failed")

    async def scenario() -> None:
        connection = FakeConnection(BleConnectionConfig(address="a", notify_uuid="n", write_uuid="w"))
        adapter = PowerstreamAdapter(
            _config(user_id="user"),
            connection_factory=lambda _cfg: connection,
            crypto_factory=lambda _serial: FailingCrypto("SN123"),
        )  # type: ignore[arg-type]

        await adapter.start(EventBus())
        assert adapter.health.is_failed
        assert "start failed" in adapter.health.detail
        assert adapter._maintain_task is not None  # type: ignore[attr-defined]

        await adapter.stop()

    asyncio.run(scenario())


def test_publish_state_copies_minimal_adr002_payload() -> None:
    async def scenario() -> None:
        bus = EventBus()
        adapter = PowerstreamAdapter(_config(serial_number=None))
        received: list[dict[str, object]] = []

        async def handler(_topic: str, payload: dict[str, object]) -> None:
            received.append(payload)

        await bus.subscribe("ecoflow/powerstream/state", handler)
        await adapter.start(bus)
        original = {"power": 120, "battery": 80}
        await adapter._publish_state(original)  # type: ignore[arg-type]
        original["power"] = 999
        await asyncio.sleep(0)

        assert received == [{"power": 120, "battery": 80}]

        await adapter.stop()

    asyncio.run(scenario())


def test_publish_state_routes_bat_topic_to_battery_cache() -> None:
    """Payloads published with bat_state_topic must go into the battery cache, not the main state cache."""

    async def scenario() -> None:
        bus = EventBus()
        adapter = PowerstreamAdapter(_config(serial_number=None))
        main_received: list[dict[str, object]] = []
        bat_received: list[dict[str, object]] = []

        async def main_handler(_t: str, p: dict[str, object]) -> None:
            main_received.append(p)

        async def bat_handler(_t: str, p: dict[str, object]) -> None:
            bat_received.append(p)

        await bus.subscribe("ecoflow/powerstream/state", main_handler)
        await bus.subscribe("ecoflow/powerstream_battery/state", bat_handler)
        await adapter.start(bus)

        await adapter._publish_state({"bat_soc": 75}, topic=adapter._config.bat_state_topic)  # type: ignore[attr-defined]
        await asyncio.sleep(0)

        assert bat_received == [{"bat_soc": 75}]
        assert main_received == []

        await adapter.stop()

    asyncio.run(scenario())
