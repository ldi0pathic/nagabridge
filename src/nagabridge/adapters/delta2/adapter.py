"""Delta 2 BLE adapter implementation."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from typing import Any

from nagabridge.core.adapter import Adapter
from nagabridge.core.ble import BleakClientAdapter, BleConnection, BleConnectionConfig
from nagabridge.core.bus import EventBus, Payload, Topic
from nagabridge.core.config import BleDeviceConfig
from nagabridge.core.health import HealthState, HealthStatus
from nagabridge.core.topics import command_topic, health_topic, state_topic

from .commands import encode_command
from .parser import parse_payload, parse_status_payload
from .protocol import KIND_STATUS, decode_packets

_MODULE = __name__.rsplit(".", 1)[0]
UUID_WRITE = "00000002-0000-1000-8000-00805f9b34fb"
UUID_NOTIFY = "00000003-0000-1000-8000-00805f9b34fb"
DEFAULT_POLL_INTERVAL_SECONDS = 10.0

ConnectionFactory = Callable[[BleConnectionConfig], BleConnection]


class Delta2Adapter(Adapter):
    """BLE adapter for EcoFlow Delta 2 devices."""

    def __init__(self, config: BleDeviceConfig, *, connection_factory: ConnectionFactory | None = None) -> None:
        self._config = config
        self._log = logging.getLogger(f"{_MODULE}.{config.name.lower().replace(' ', '-')}")
        self._connection_factory = connection_factory or self._default_connection_factory
        self._health = HealthStatus()
        self._bus: EventBus | None = None
        self._connection: BleConnection | None = None
        self._maintain_task: asyncio.Task[None] | None = None
        self._rx_buffer = bytearray()
        self._state: dict[str, Any] = {"message_type": "delta2_status", "online": False}

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def version(self) -> str:
        return "0.2.0"

    @property
    def health(self) -> HealthStatus:
        return self._health

    @property
    def published_topics(self) -> list[str]:
        return [state_topic(self._config.domain, self._config.name)]

    async def start(self, bus: EventBus) -> None:
        self._bus = bus
        await bus.subscribe(command_topic(self._config.domain, self._config.name), self._on_command)
        self._connection = self._connection_factory(self._connection_config())
        try:
            await self._connection.connect(self._on_notification)
            self._state["online"] = True
            self._health = HealthStatus(state=HealthState.ok, detail="running")
        except Exception as exc:
            self._health = HealthStatus(state=HealthState.degraded, detail=f"start deferred: {exc}")
            self._log.warning("Delta2 start failed for %s: %s", self.name, exc)
        await self._publish_state()
        await self._publish_health()
        self._maintain_task = asyncio.create_task(self._maintain_loop())

    async def stop(self) -> None:
        if self._maintain_task is not None:
            self._maintain_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._maintain_task
            self._maintain_task = None

        if self._bus is not None:
            await self._bus.unsubscribe(command_topic(self._config.domain, self._config.name), self._on_command)

        if self._connection is not None:
            await self._connection.disconnect()
            self._connection = None

        self._state["online"] = False
        self._health = HealthStatus(state=HealthState.failed, detail="stopped")
        await self._publish_state()
        await self._publish_health()
        self._bus = None

    async def _on_command(self, _topic: Topic, payload: Payload) -> None:
        encoded = encode_command(payload)
        if encoded is None:
            command = payload.get("command") or payload.get("type")
            self._state["last_error"] = f"unsupported_command:{command}"
            self._log.debug("Ignoring unsupported Delta2 command payload: %s", payload)
            await self._publish_state()
            return
        self._last_encoded_command = self._legacy_encoded_command(payload)
        if self._connection is None:
            return
        try:
            await self._connection.write(encoded)
            if (payload.get("command") or payload.get("type")) in {"get_status", "refresh"}:
                await self._publish_state()
        except Exception as exc:
            self._health = HealthStatus(state=HealthState.failed, detail=f"command failed: {exc}")
            await self._publish_health()

    async def on_ble_notification(self, data: bytes) -> None:
        """Handle compact legacy BLE notification payloads."""
        self._state.update(parse_payload(data))
        self._state["online"] = True
        self._health = HealthStatus(state=HealthState.ok, detail="running")
        await self._publish_state()
        await self._publish_health()

    async def _on_notification(self, data: bytes) -> None:
        try:
            packets, self._rx_buffer = decode_packets(data, self._rx_buffer)
            for packet in packets:
                if packet.kind != KIND_STATUS:
                    continue
                self._state.update(parse_status_payload(packet.payload))
                self._state["online"] = True
                self._health = HealthStatus(state=HealthState.ok, detail="running")
                await self._publish_state()
                await self._publish_health()
        except Exception as exc:
            self._health = HealthStatus(state=HealthState.failed, detail=f"notification failed: {exc}")
            await self._publish_health()

    async def _maintain_loop(self) -> None:
        interval = self._config.poll_interval_seconds or DEFAULT_POLL_INTERVAL_SECONDS
        while True:
            await asyncio.sleep(interval)
            self._state["heartbeat"] = int(asyncio.get_running_loop().time())
            if self._connection is None:
                self._state["online"] = False
                self._health = HealthStatus(state=HealthState.failed, detail="connection missing")
            elif not self._connection.is_connected:
                self._state["online"] = False
                self._health = HealthStatus(state=HealthState.failed, detail="disconnected")
                try:
                    await self._connection.reconnect()
                    self._state["online"] = True
                    self._health = HealthStatus(state=HealthState.ok, detail="running")
                except Exception as exc:
                    self._health = HealthStatus(state=HealthState.failed, detail=f"reconnect failed: {exc}")
            await self._publish_state()
            await self._publish_health()

    async def _publish_state(self) -> None:
        if self._bus is None:
            return
        await self._bus.publish(state_topic(self._config.domain, self._config.name), dict(self._state))

    async def _publish_health(self) -> None:
        if self._bus is None:
            return
        await self._bus.publish(health_topic(self.name), self._health.to_payload(self.name))

    @staticmethod
    def _legacy_encoded_command(payload: Payload) -> bytes:
        command = payload.get("command") or payload.get("type")
        if command == "set_ac_output":
            return bytes((0xA1, max(0, min(255, int(payload.get("watts", 0))))))
        return b""

    def _connection_config(self) -> BleConnectionConfig:
        return BleConnectionConfig(
            address=self._config.mac,
            notify_uuid=UUID_NOTIFY,
            write_uuid=UUID_WRITE,
            name=self.name,
            reconnect_attempts=self._config.reconnect_attempts or 3,
            reconnect_backoff_seconds=self._config.reconnect_backoff_seconds if self._config.reconnect_backoff_seconds is not None else 1.0,
            write_with_response=bool(self._config.write_with_response),
        )

    @staticmethod
    def _default_connection_factory(config: BleConnectionConfig) -> BleConnection:
        return BleConnection(config, lambda address: BleakClientAdapter(address, timeout=config.connect_timeout))
