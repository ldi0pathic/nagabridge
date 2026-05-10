"""Reusable BLE connection lifecycle helper."""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from .client import BleClient
from .exceptions import BleConnectionError, BleOperationError

log = logging.getLogger(__name__)

NotificationHandler = Callable[[bytes], Awaitable[None] | None]
ClientFactory = Callable[[str], BleClient | Awaitable[BleClient]]
SleepFunc = Callable[[float], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class BleConnectionConfig:
    """Configuration for a reusable BLE connection."""

    address: str
    notify_uuid: str
    write_uuid: str
    name: str = "ble-device"
    connect_timeout: float = 20.0
    reconnect_attempts: int = 3
    reconnect_backoff_seconds: float = 1.0
    max_backoff_seconds: float = 30.0
    write_with_response: bool = False

    def __post_init__(self) -> None:
        """Validate values that would otherwise make reconnect behavior unsafe."""
        if not self.address:
            msg = "BLE address must not be empty"
            raise ValueError(msg)
        if not self.notify_uuid:
            msg = "BLE notify UUID must not be empty"
            raise ValueError(msg)
        if not self.write_uuid:
            msg = "BLE write UUID must not be empty"
            raise ValueError(msg)
        if self.reconnect_attempts < 1:
            msg = "reconnect_attempts must be at least 1"
            raise ValueError(msg)
        if self.reconnect_backoff_seconds < 0:
            msg = "reconnect_backoff_seconds must not be negative"
            raise ValueError(msg)
        if self.max_backoff_seconds < self.reconnect_backoff_seconds:
            msg = "max_backoff_seconds must be greater than or equal to reconnect_backoff_seconds"
            raise ValueError(msg)


class BleConnection:
    """Own a BLE client, reconnect with backoff and normalize notifications."""

    def __init__(self, config: BleConnectionConfig, client_factory: ClientFactory, *, sleep: SleepFunc = asyncio.sleep) -> None:
        """Create a connection helper around an injectable BLE client factory."""
        self._config = config
        self._client_factory = client_factory
        self._sleep = sleep
        self._client: BleClient | None = None
        self._notification_handler: NotificationHandler | None = None
        self._notifications_started = False

    @property
    def config(self) -> BleConnectionConfig:
        """Return immutable connection configuration."""
        return self._config

    @property
    def is_connected(self) -> bool:
        """Return whether the current client is connected."""
        return self._client is not None and self._client.is_connected

    async def connect(self, notification_handler: NotificationHandler | None = None) -> None:
        """Connect and optionally subscribe to notifications.

        Failed attempts are retried with exponential backoff until
        ``reconnect_attempts`` is exhausted.
        """
        if notification_handler is not None:
            self._notification_handler = notification_handler
        if self.is_connected:
            await self._ensure_notifications_started()
            return

        last_error: BaseException | None = None
        backoff = self._config.reconnect_backoff_seconds
        for attempt in range(1, self._config.reconnect_attempts + 1):
            try:
                self._client = await self._create_client()
                await self._client.connect()
                await self._ensure_notifications_started()
                log.info("BLE connection established for %s", self._config.name)
                return
            except Exception as exc:
                last_error = exc
                log.warning(
                    "BLE connection attempt %d/%d failed for %s: %s",
                    attempt,
                    self._config.reconnect_attempts,
                    self._config.name,
                    exc,
                )
                await self._safe_disconnect()
                if attempt < self._config.reconnect_attempts and backoff > 0:
                    await self._sleep(backoff)
                    backoff = min(backoff * 2, self._config.max_backoff_seconds)

        msg = f"Could not connect BLE device {self._config.name} at {self._config.address}"
        raise BleConnectionError(msg) from last_error

    async def reconnect(self) -> None:
        """Disconnect and reconnect using the last notification handler."""
        await self.disconnect()
        await self.connect(self._notification_handler)

    async def disconnect(self) -> None:
        """Stop notifications and close the BLE client."""
        if self._client is None:
            self._notifications_started = False
            return
        if self._notifications_started:
            try:
                await self._client.stop_notify(self._config.notify_uuid)
            except Exception as exc:
                log.debug("Ignoring BLE stop_notify error for %s: %s", self._config.name, exc)
        await self._safe_disconnect()

    async def write(self, data: bytes, *, response: bool | None = None) -> None:
        """Write bytes to the configured write characteristic."""
        if self._client is None or not self._client.is_connected:
            msg = f"BLE device {self._config.name} is not connected"
            raise BleOperationError(msg)
        await self._client.write_gatt_char(
            self._config.write_uuid,
            data,
            response=self._config.write_with_response if response is None else response,
        )

    async def _create_client(self) -> BleClient:
        client = self._client_factory(self._config.address)
        if inspect.isawaitable(client):
            client = await client
        return client

    async def _ensure_notifications_started(self) -> None:
        if self._client is None or self._notification_handler is None or self._notifications_started:
            return
        await self._client.start_notify(self._config.notify_uuid, self._handle_notification)
        self._notifications_started = True

    def _handle_notification(self, _sender: int | str, data: bytearray) -> None:
        if self._notification_handler is None:
            return
        payload = bytes(data)
        result = self._notification_handler(payload)
        if inspect.isawaitable(result):
            asyncio.create_task(result)

    async def _safe_disconnect(self) -> None:
        if self._client is None:
            self._notifications_started = False
            return
        try:
            await self._client.disconnect()
        finally:
            self._client = None
            self._notifications_started = False
