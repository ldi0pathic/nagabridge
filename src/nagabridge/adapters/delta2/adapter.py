"""Delta 2 adapter implementation (prototype telemetry + command handling)."""

import asyncio
import logging

from nagabridge.core.adapter import Adapter
from nagabridge.core.bus import EventBus
from nagabridge.core.config import BleDeviceConfig
from nagabridge.core.health import HealthState, HealthStatus
from nagabridge.core.topics import command_topic, health_topic, state_topic

from .parser import parse_payload
from .protocol import encode_command

_MODULE = __name__.rsplit(".", 1)[0]


class Delta2Adapter(Adapter):
    """Prototype adapter for Delta 2 devices."""

    def __init__(self, config: BleDeviceConfig) -> None:
        """Initialize the adapter with BLE device configuration."""
        self._config = config
        self._log = logging.getLogger(f"{_MODULE}.{config.name.lower().replace(' ', '-')}")
        self._health = HealthStatus()
        self._bus: EventBus | None = None
        self._maintain_task: asyncio.Task[None] | None = None
        self._last_encoded_command: bytes | None = None
        self._state: dict[str, object] = {
            "message_type": "delta2_status",
            "online": False,
            "mode": "prototype",
        }

    @property
    def name(self) -> str:
        """Return the configured adapter name."""
        return self._config.name

    @property
    def version(self) -> str:
        """Return the adapter implementation version."""
        return "0.1.0"

    @property
    def health(self) -> HealthStatus:
        """Expose current adapter health state."""
        return self._health

    async def start(self, bus: EventBus) -> None:
        """Start the adapter lifecycle in prototype mode."""
        self._bus = bus
        await bus.subscribe(command_topic(self._config.domain, self._config.name), self._on_command)
        self._state["online"] = True
        await self._publish_state()
        self._health = HealthStatus(state=HealthState.degraded, detail="prototype mode")
        await self._publish_health()
        self._maintain_task = asyncio.create_task(self._maintain_loop())

    @property
    def published_topics(self) -> list[str]:
        """Return state topics published by this adapter."""
        from nagabridge.core.topics import state_topic

        return [state_topic(self._config.domain, self._config.name)]

    async def _publish_state(self) -> None:
        if self._bus is None:
            return
        await self._bus.publish(state_topic(self._config.domain, self._config.name), dict(self._state))

    async def _publish_health(self) -> None:
        if self._bus is None:
            return
        try:
            await self._bus.publish(health_topic(self.name), self._health.to_payload(self.name))
        except Exception:
            self._log.exception("Failed to publish health for %s", self.name)

    async def stop(self) -> None:
        """Stop the adapter lifecycle."""
        if self._maintain_task is not None:
            self._maintain_task.cancel()
            try:
                await self._maintain_task
            except asyncio.CancelledError:
                pass
            self._maintain_task = None
        if self._bus is not None:
            await self._bus.unsubscribe(command_topic(self._config.domain, self._config.name), self._on_command)
        self._state["online"] = False
        await self._publish_state()
        self._health = HealthStatus(state=HealthState.failed, detail="stopped")
        await self._publish_health()
        self._bus = None

    async def _maintain_loop(self) -> None:
        while True:
            await asyncio.sleep(self._config.poll_interval_seconds or 30.0)
            self._state["heartbeat"] = int(self.health.timestamp)
            await self._publish_state()

    async def on_ble_notification(self, payload: bytes) -> None:
        self._state.update(parse_payload(payload))
        await self._publish_state()

    async def _on_command(self, _topic: str, payload: dict[str, object]) -> None:
        command = str(payload.get("command") or payload.get("type") or "")
        if command in {"get_status", "refresh"}:
            await self._publish_state()
            self._last_encoded_command = encode_command(command, payload)
            return
        try:
            self._last_encoded_command = encode_command(command, payload)
        except ValueError:
            self._state["last_error"] = f"unsupported_command:{command}"
            await self._publish_state()
