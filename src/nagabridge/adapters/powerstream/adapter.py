"""PowerStream adapter implementation."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import struct
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from nagabridge.core.adapter import Adapter
from nagabridge.core.ble import BleakClientAdapter, BleConnection, BleConnectionConfig
from nagabridge.core.bus import EventBus, Payload, Topic
from nagabridge.core.config import BleDeviceConfig
from nagabridge.core.health import HealthStatus

if TYPE_CHECKING:
    from .protocol import Packet, Type1Crypto

log = logging.getLogger(__name__)

UUID_WRITE = "00000002-0000-1000-8000-00805f9b34fb"
UUID_NOTIFY = "00000003-0000-1000-8000-00805f9b34fb"
STATE_TOPIC = "ecoflow/powerstream/state"
COMMAND_TOPIC = "ecoflow/powerstream/command"
DEFAULT_POLL_INTERVAL_SECONDS = 10.0
MAX_LOAD_POWER_WATTS = 8000

ConnectionFactory = Callable[[BleConnectionConfig], BleConnection]
CryptoFactory = Callable[[str], "Type1Crypto"]


class _PowerstreamCrypto(Protocol):
    """Protocol subset consumed from Type1Crypto and tests."""

    def encode_packet(self, packet: Packet) -> bytes:
        """Encode one packet for BLE write."""
        ...

    def decode_packets(self, data: bytes, buffer: bytearray) -> tuple[Sequence[Packet], bytearray]:
        """Decode one or more packets from a BLE notification chunk."""
        ...


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
        """Build adapter config from the generic BLE device config."""
        return cls(
            name=config.name,
            mac=config.mac,
            serial_number=config.serial_number,
            user_id=config.user_id,
            poll_interval_seconds=config.poll_interval_seconds or DEFAULT_POLL_INTERVAL_SECONDS,
            reconnect_attempts=config.reconnect_attempts or 3,
            reconnect_backoff_seconds=config.reconnect_backoff_seconds if config.reconnect_backoff_seconds is not None else 1.0,
            write_with_response=bool(config.write_with_response),
        )


class PowerstreamAdapter(Adapter):
    """BLE adapter for EcoFlow PowerStream devices."""

    def __init__(
        self,
        config: BleDeviceConfig | PowerstreamAdapterConfig,
        *,
        connection_factory: ConnectionFactory | None = None,
        crypto_factory: CryptoFactory | None = None,
    ) -> None:
        """Initialize the adapter with config and injectable BLE dependencies."""
        self._config = config if isinstance(config, PowerstreamAdapterConfig) else PowerstreamAdapterConfig.from_ble_device(config)
        self._connection_factory = connection_factory or self._default_connection_factory
        self._crypto_factory = crypto_factory or self._default_crypto_factory
        self._health = HealthStatus()
        self._bus: EventBus | None = None
        self._connection: BleConnection | None = None
        self._crypto: _PowerstreamCrypto | None = None
        self._rx_buffer = bytearray()
        self._authenticated = False
        self._poll_task: asyncio.Task[None] | None = None
        self._last_state: dict[str, Any] = {}
        self._last_bat_state: dict[str, Any] = {}

    @property
    def name(self) -> str:
        """Return the configured adapter name."""
        return self._config.name

    @property
    def version(self) -> str:
        """Return the adapter implementation version."""
        return "0.2.1"

    @property
    def health(self) -> HealthStatus:
        """Expose current adapter health state."""
        return self._health

    async def start(self, bus: EventBus) -> None:
        """Start command handling, BLE connection and polling when configured."""
        self._bus = bus
        await bus.subscribe(self._config.command_topic, self._on_command)

        if not self._config.serial_number:
            log.info("PowerStream %s has no serial number configured; BLE connection is deferred", self.name)
            self._health = HealthStatus(online=True, detail="running")
            return

        try:
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
        if watts < 0 or watts > MAX_LOAD_POWER_WATTS:
            msg = f"PowerStream load power must be between 0 and {MAX_LOAD_POWER_WATTS} W"
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
                return
            packets, self._rx_buffer = self._crypto.decode_packets(data, self._rx_buffer)
            for packet in packets:
                from .parser import parse, parse_type2

                if packet.cmd_set == 0x14 and packet.cmd_id == 0x01:
                    await self._publish_state(parse(packet.payload))
                elif packet.cmd_set == 0x14 and packet.cmd_id == 0x04:
                    await self._publish_state(parse_type2(packet.payload), "ecoflow/powerstream/bat_state")
                else:
                    log.debug("Unhandled packet src=0x%02x cmd_set=0x%02x cmd_id=0x%02x", packet.src, packet.cmd_set, packet.cmd_id)
        except Exception as exc:
            log.exception("PowerStream notification handling failed")
            self._health = HealthStatus(online=False, detail=f"notification failed: {exc}")

    async def _publish_state(self, payload: Payload, topic: str | None = None) -> None:
        if self._bus is None:
            return
        target = topic or self._config.state_topic
        cache = self._last_bat_state if topic else self._last_state
        cache.update(payload)
        await self._bus.publish(target, dict(cache))

    async def _poll_loop(self) -> None:
        while True:
            await asyncio.sleep(self._config.poll_interval_seconds)
            try:
                await self.request_status()
            except Exception as exc:
                log.warning("PowerStream status poll failed for %s: %s", self.name, exc)
                self._health = HealthStatus(online=False, detail=f"poll failed: {exc}")

    async def _authenticate(self) -> None:
        """Send the PowerStream MD5 authentication packet when credentials exist."""
        self._authenticated = False
        if not self._config.serial_number:
            return
        if not self._config.user_id:
            log.info("PowerStream %s has no user_id configured; authentication is skipped", self.name)
            return

        try:
            from .protocol import COMMAND_ID_AUTH, COMMAND_ID_AUTH_STATUS, COMMAND_SET_AUTH, build_auth_md5

            auth_payload = build_auth_md5(self._config.user_id, self._config.serial_number)
            if len(auth_payload) != 32:
                msg = "PowerStream auth MD5 payload must be 32 ASCII bytes"
                raise ValueError(msg)
            await self._write_packet(COMMAND_SET_AUTH, COMMAND_ID_AUTH_STATUS, b"", dsrc=0x01, ddst=0x01)
            await asyncio.sleep(1)
            await self._write_packet(COMMAND_SET_AUTH, COMMAND_ID_AUTH, auth_payload, dsrc=0x01, ddst=0x01)
            self._authenticated = True
            log.info("PowerStream %s authentication packet sent", self.name)
        except Exception as exc:
            self._health = HealthStatus(online=False, detail=f"auth failed: {exc}")
            log.exception("PowerStream authentication failed for %s", self.name)
            raise

    async def _write_packet(self, cmd_set: int, cmd_id: int, payload: bytes = b"", dsrc: int = 1, ddst: int = 1) -> None:
        if self._connection is None:
            log.debug("Skipping PowerStream write because BLE is not connected")
            return
        encoded = self._encode_packet(cmd_set, cmd_id, payload, dsrc=dsrc, ddst=ddst)
        await self._connection.write(encoded)

    def _encode_packet(self, cmd_set: int, cmd_id: int, payload: bytes, dsrc: int = 1, ddst: int = 1) -> bytes:
        if self._crypto is None:
            msg = "PowerStream crypto is not initialized"
            raise RuntimeError(msg)
        from .protocol import Packet

        packet = Packet(src=0x21, dst=0x35, cmd_set=cmd_set, cmd_id=cmd_id, payload=payload, dsrc=dsrc, ddst=ddst)
        return self._crypto.encode_packet(packet)

    def _initialize_crypto(self) -> None:
        """Initialize PowerStream Type1 crypto from the serial number.

        Type1 uses the device serial number for AES key/IV derivation. The
        EcoFlow user ID is not part of the AES key; it is combined with the
        same serial number in :meth:`_authenticate` to build the MD5 handshake
        payload.
        """
        if self._crypto is not None:
            return
        if self._config.serial_number is None:
            return
        self._crypto = self._crypto_factory(self._config.serial_number)
        log.debug(
            "Initialized PowerStream Type1Crypto for %s (serial ending in %s, user_id configured=%s)",
            self.name,
            self._config.serial_number[-4:],
            self._config.user_id is not None,
        )

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

    @staticmethod
    def _default_crypto_factory(serial_number: str) -> _PowerstreamCrypto:
        from .protocol import Type1Crypto

        return Type1Crypto(serial_number)

    async def _cleanup_connection(self) -> None:
        if self._connection is not None:
            await self._connection.disconnect()
            self._connection = None
        self._rx_buffer = bytearray()
        self._last_state = {}
        self._last_bat_state = {}
