"""BLE client protocol and default bleak-backed adapter."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

BleakNotificationCallback = Callable[[int | str, bytearray], None]


class BleClient(Protocol):
    """Minimal BLE client contract consumed by :class:`BleConnection`."""

    @property
    def is_connected(self) -> bool:
        """Return whether the underlying BLE client is connected."""
        ...

    async def connect(self) -> None:
        """Open the BLE connection."""
        ...

    async def disconnect(self) -> None:
        """Close the BLE connection."""
        ...

    async def start_notify(self, char_specifier: str, callback: BleakNotificationCallback) -> None:
        """Subscribe to notifications for *char_specifier*."""
        ...

    async def stop_notify(self, char_specifier: str) -> None:
        """Unsubscribe from notifications for *char_specifier*."""
        ...

    async def write_gatt_char(self, char_specifier: str, data: bytes, *, response: bool = False) -> None:
        """Write bytes to *char_specifier*."""
        ...


class BleakClientAdapter:
    """Adapter exposing bleak's client through the local :class:`BleClient` protocol."""

    def __init__(self, address: str, *, timeout: float = 20.0) -> None:
        """Create a bleak client for *address*.

        The import is intentionally local so unit tests and non-BLE environments
        can import the core BLE abstraction without having bleak installed.
        """
        from bleak import BleakClient

        self._client: Any = BleakClient(address, timeout=timeout)

    @property
    def is_connected(self) -> bool:
        """Return bleak's connection state."""
        return bool(self._client.is_connected)

    async def connect(self) -> None:
        """Connect using bleak."""
        await self._client.connect()

    async def disconnect(self) -> None:
        """Disconnect using bleak."""
        await self._client.disconnect()

    async def start_notify(self, char_specifier: str, callback: BleakNotificationCallback) -> None:
        """Subscribe to notifications using bleak."""
        await self._client.start_notify(char_specifier, callback)

    async def stop_notify(self, char_specifier: str) -> None:
        """Unsubscribe from notifications using bleak."""
        await self._client.stop_notify(char_specifier)

    async def write_gatt_char(self, char_specifier: str, data: bytes, *, response: bool = False) -> None:
        """Write bytes using bleak."""
        await self._client.write_gatt_char(char_specifier, data, response=response)
