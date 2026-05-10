"""Tests for the reusable BLE connection abstraction."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import pytest

from nagabridge.core.ble import BleConnection, BleConnectionConfig, BleConnectionError, BleOperationError


class FakeBleClient:
    """Small in-memory BLE client test double."""

    def __init__(self, *, fail_connects: int = 0) -> None:
        self.fail_connects = fail_connects
        self.connect_calls = 0
        self.disconnect_calls = 0
        self.start_notify_calls: list[str] = []
        self.stop_notify_calls: list[str] = []
        self.writes: list[tuple[str, bytes, bool]] = []
        self.callback: Callable[[int | str, bytearray], None] | None = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        self.connect_calls += 1
        if self.fail_connects > 0:
            self.fail_connects -= 1
            raise RuntimeError("connect failed")
        self._connected = True

    async def disconnect(self) -> None:
        self.disconnect_calls += 1
        self._connected = False

    async def start_notify(self, char_specifier: str, callback: Callable[[int | str, bytearray], None]) -> None:
        self.start_notify_calls.append(char_specifier)
        self.callback = callback

    async def stop_notify(self, char_specifier: str) -> None:
        self.stop_notify_calls.append(char_specifier)

    async def write_gatt_char(self, char_specifier: str, data: bytes, *, response: bool = False) -> None:
        self.writes.append((char_specifier, data, response))

    def emit(self, data: bytes) -> None:
        assert self.callback is not None
        self.callback("notify", bytearray(data))


def _config(**overrides: object) -> BleConnectionConfig:
    values = {
        "address": "AA:BB:CC:DD:EE:FF",
        "notify_uuid": "notify-uuid",
        "write_uuid": "write-uuid",
        "name": "PowerStream",
        "reconnect_backoff_seconds": 0.0,
    }
    values.update(overrides)
    return BleConnectionConfig(**values)  # type: ignore[arg-type]


def test_connect_starts_notifications_and_delivers_sync_callback() -> None:
    async def scenario() -> None:
        client = FakeBleClient()
        received: list[bytes] = []
        connection = BleConnection(_config(), lambda _address: client)

        await connection.connect(received.append)
        client.emit(b"payload")

        assert connection.is_connected
        assert client.start_notify_calls == ["notify-uuid"]
        assert received == [b"payload"]

    asyncio.run(scenario())


def test_connect_delivers_async_notification_callback() -> None:
    async def scenario() -> None:
        client = FakeBleClient()
        received: list[bytes] = []

        async def handler(data: bytes) -> None:
            received.append(data)

        connection = BleConnection(_config(), lambda _address: client)

        await connection.connect(handler)
        client.emit(b"async")
        await asyncio.sleep(0)

        assert received == [b"async"]

    asyncio.run(scenario())


def test_connect_retries_with_backoff() -> None:
    async def scenario() -> None:
        clients = [FakeBleClient(fail_connects=1), FakeBleClient()]
        sleeps: list[float] = []

        async def sleep(delay: float) -> None:
            sleeps.append(delay)

        connection = BleConnection(_config(reconnect_attempts=2, reconnect_backoff_seconds=0.5), lambda _address: clients.pop(0), sleep=sleep)

        await connection.connect()

        assert connection.is_connected
        assert sleeps == [0.5]

    asyncio.run(scenario())


def test_connect_raises_after_exhausting_retries() -> None:
    async def scenario() -> None:
        connection = BleConnection(_config(reconnect_attempts=2), lambda _address: FakeBleClient(fail_connects=1))

        with pytest.raises(BleConnectionError, match="Could not connect"):
            await connection.connect()

    asyncio.run(scenario())


def test_write_requires_connected_client() -> None:
    async def scenario() -> None:
        connection = BleConnection(_config(), lambda _address: FakeBleClient())

        with pytest.raises(BleOperationError, match="not connected"):
            await connection.write(b"data")

    asyncio.run(scenario())


def test_write_uses_configured_characteristic_and_response_flag() -> None:
    async def scenario() -> None:
        client = FakeBleClient()
        connection = BleConnection(_config(write_with_response=True), lambda _address: client)

        await connection.connect()
        await connection.write(b"data")
        await connection.write(b"other", response=False)

        assert client.writes == [("write-uuid", b"data", True), ("write-uuid", b"other", False)]

    asyncio.run(scenario())


def test_disconnect_stops_notifications_and_disconnects() -> None:
    async def scenario() -> None:
        client = FakeBleClient()
        connection = BleConnection(_config(), lambda _address: client)

        await connection.connect(lambda _data: None)
        await connection.disconnect()

        assert not connection.is_connected
        assert client.stop_notify_calls == ["notify-uuid"]
        assert client.disconnect_calls == 1

    asyncio.run(scenario())


def test_config_validation_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="address"):
        _config(address="")
    with pytest.raises(ValueError, match="reconnect_attempts"):
        _config(reconnect_attempts=0)
    with pytest.raises(ValueError, match="max_backoff"):
        _config(reconnect_backoff_seconds=2.0, max_backoff_seconds=1.0)
