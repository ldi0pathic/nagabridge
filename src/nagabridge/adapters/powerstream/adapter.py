"""PowerStream adapter implementation."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import struct
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from nagabridge.core.adapter import Adapter
from nagabridge.core.ble import BleakClientAdapter, BleConnection, BleConnectionConfig
from nagabridge.core.bus import EventBus, Payload, Topic
from nagabridge.core.config import BleDeviceConfig
from nagabridge.core.health import HealthStatus

from .parser import parse

log = logging.getLogger(__name__)

UUID_WRITE = "00000002-0000-1000-8000-00805f9b34fb"
UUID_NOTIFY = "00000003-0000-1000-8000-00805f9b34fb"
STATE_TOPIC = "ecoflow/powerstream/state"
COMMAND_TOPIC = "ecoflow/powerstream/command"
DEFAULT_POLL_INTERVAL_SECONDS = 30.0

ConnectionFactory = Callable[[BleConnectionConfig], BleConnection]
PacketEncoder = Callable[[int, int, bytes], bytes]


@dataclass(frozen=True, slots=True)
class PowerstreamAdapterConfig:
    """Runtime configuration for the PowerStream adapter core."""

    name: str
    mac: str
    serial_number: str | None = None
    user_id: str | None = None
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS
    reconnect_attempts: int = 3
    reconnect_backoff_seconds: float = 1.0
    state_topic: str = STATE_TOPIC
    command_topic: str = COMMAND_TOPIC
    write_with_response: bool = False

    @classmethod
    def from_ble_device(cls, config: BleDeviceConfig) -> PowerstreamAdapterConfig:
        """Build adapter config from the current generic BLE device config."""
        return cls(name=config.name, mac=config.mac)


class PowerstreamAdapter(Adapter):
    """BLE adapter for EcoFlow PowerStream devices."""

    def __init__(
        self,
        config: BleDeviceConfig | PowerstreamAdapterConfig,
        *,
        connection_factory: ConnectionFactory | None = None,
        packet_encoder: PacketEncoder | None = None,
    ) -> None:
        """Initialize the adapter with config and injectable BLE dependencies."""
        self._config = config if isinstance(config, PowerstreamAdapterConfig) else PowerstreamAdapterConfig.from_ble_device(config)
        self._connection_factory = connection_factory or self._default_connection_factory
        self._packet_encoder = packet_encoder
        self._health = HealthStatus()
        self._bus: EventBus | None = None
        self._connection: BleConnection | None = None
        self._crypto: Any | None = None
        self._rx_buffer = bytearray()
        self._poll_task: asyncio.Task[None] | None = None

    @property
    def name(self) -> str:
        """Return the configured adapter name."""
        return self._config.name

    @property
    def version(self) -> str:
        """Return the adapter implementation version."""
        return "0.2.0"

    @property
    def health(self) -> HealthStatus:
        """Expose current adapter health state."""
        return self._health

    async def start(self, bus: EventBus) -> None:
        """Start command handling, BLE connection and polling when fully configured."""
        self._bus = bus
        await bus.subscribe(self._config.command_topic, self._on_command)

        if not self._config.serial_number:
            log.info("PowerStream %s has no serial number configured; BLE connection is deferred", self.name)
            self._health = HealthStatus(online=True, detail="running")
            return

        try:
            if self._packet_encoder is None:
                self._initialize_crypto()
            self._connection = self._connection_factory(self._connection_config())
            await self._connection.connect(self._on_notification)
            await self._authenticate()
            self._poll_task = asyncio.create_task(self._poll_loop())
            self._health = HealthStatus(online=True, detail="running")
        except Exception as exc:
            self._health = HealthStatus(online=False, detail=f"start failed: {exc}")
            await self._cleanup_connection()
            raise

    async def stop(self) -> None:
        """Stop polling, unsubscribe from commands and close BLE connection."""
        if self._poll_task is not None:
            self._poll_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._poll_task
            self._poll_task = None

        if self._bus is not None:
            await self._bus.unsubscribe(self._config.command_topic, self._on_command)
            self._bus = None

        await self._cleanup_connection()
        self._health = HealthStatus(online=False, detail="stopped")

    async def request_status(self) -> None:
        """Request one fresh status update from the PowerStream."""
        await self._write_packet(0x02, 0x22)

    async def set_load_power(self, watts: int) -> None:
        """Set the PowerStream permanent output limit in watts."""
        if watts < 0 or watts > 8000:
            msg = "PowerStream load power must be between 0 and 8000 W"
            raise ValueError(msg)
        await self._write_packet(0x02, 0x23, struct.pack("<H", watts))

    async def _on_command(self, _topic: Topic, payload: Payload) -> None:
        command = payload.get("command") or payload.get("type")
        try:
            if command in {"get_status", "refresh"}:
                await self.request_status()
            elif command in {"set_load_power", "set_permanent_watts"}:
                await self.set_load_power(int(payload["watts"]))
            else:
                log.debug("Ignoring unsupported PowerStream command payload: %s", payload)
        except Exception as exc:
            log.exception("PowerStream command failed: %s", payload)
            self._health = HealthStatus(online=False, detail=f"command failed: {exc}")

    async def _on_notification(self, data: bytes) -> None:
        if self._bus is None:
            return
        try:
            if self._crypto is None:
                parsed = parse(data)
                await self._publish_state(parsed)
                return

            packets, self._rx_buffer = self._crypto.decode_packets(data, self._rx_buffer)
            for packet in packets:
                parsed = parse(packet.payload)
                parsed.update(
                    {
                        "src": packet.src,
                        "dst": packet.dst,
                        "cmd_set": packet.cmd_set,
                        "cmd_id": packet.cmd_id,
                    },
                )
                await self._publish_state(parsed)
        except Exception as exc:
            log.exception("PowerStream notification handling failed")
            self._health = HealthStatus(online=False, detail=f"notification failed: {exc}")

    async def _publish_state(self, payload: dict[str, Any]) -> None:
        if self._bus is None:
            return
        await self._bus.publish(self._config.state_topic, payload)

    async def _poll_loop(self) -> None:
        while True:
            await asyncio.sleep(self._config.poll_interval_seconds)
            try:
                await self.request_status()
            except Exception as exc:
                log.warning("PowerStream status poll failed for %s: %s", self.name, exc)
                self._health = HealthStatus(online=False, detail=f"poll failed: {exc}")

    async def _authenticate(self) -> None:
        if not self._config.user_id or not self._config.serial_number:
            return
        from .protocol import build_auth_md5

        await self._write_packet(0x01, 0x20, build_auth_md5(self._config.user_id, self._config.serial_number))

    async def _write_packet(self, cmd_set: int, cmd_id: int, payload: bytes = b"") -> None:
        if self._connection is None:
            log.debug("Skipping PowerStream write because BLE is not connected")
            return
        encoded = self._encode_packet(cmd_set, cmd_id, payload)
        await self._connection.write(encoded)

    def _encode_packet(self, cmd_set: int, cmd_id: int, payload: bytes) -> bytes:
        if self._packet_encoder is not None:
            return self._packet_encoder(cmd_set, cmd_id, payload)
        if self._crypto is None:
            msg = "PowerStream crypto is not initialized"
            raise RuntimeError(msg)
        from .protocol import Packet

        packet = Packet(src=0x21, dst=0x35, cmd_set=cmd_set, cmd_id=cmd_id, payload=payload)
        return self._crypto.encode_packet(packet)

    def _initialize_crypto(self) -> None:
        if self._crypto is not None:
            return
        if self._config.serial_number is None:
            return
        from .protocol import Type1Crypto

        self._crypto = Type1Crypto(self._config.serial_number)

    def _connection_config(self) -> BleConnectionConfig:
        return BleConnectionConfig(
            address=self._config.mac,
            notify_uuid=UUID_NOTIFY,
            write_uuid=UUID_WRITE,
            name=self._config.name,
            reconnect_attempts=self._config.reconnect_attempts,
            reconnect_backoff_seconds=self._config.reconnect_backoff_seconds,
            write_with_response=self._config.write_with_response,
        )

    @staticmethod
    def _default_connection_factory(config: BleConnectionConfig) -> BleConnection:
        return BleConnection(config, lambda address: BleakClientAdapter(address, timeout=config.connect_timeout))

    async def _cleanup_connection(self) -> None:
        if self._connection is not None:
            await self._connection.disconnect()
            self._connection = None
        self._rx_buffer = bytearray()
