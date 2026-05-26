"""Delta 2 Max full adapter with model-local internal flow."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from nagabridge.core.adapter import Adapter
from nagabridge.core.bus import EventBus
from nagabridge.core.config import BleDeviceConfig
from nagabridge.core.health import HealthState, HealthStatus
from nagabridge.core.topics import health_topic

from .parser import sanitize_state
from .protocol import Delta2MaxCommand, map_command

_MODULE = __name__.rsplit(".", 1)[0]
STATE_TOPIC = "ecoflow/delta2max/state"
COMMAND_TOPIC = "ecoflow/delta2max/command"
DEFAULT_POLL_INTERVAL_SECONDS = 15.0


class Delta2MaxAdapter(Adapter):
    """State-driven adapter for EcoFlow Delta 2 Max."""

    def __init__(self, config: BleDeviceConfig) -> None:
        self._config = config
        self._log = logging.getLogger(f"{_MODULE}.{config.name.lower().replace(' ', '-')}")
        self._health = HealthStatus()
        self._bus: EventBus | None = None
        self._maintain_task: asyncio.Task[None] | None = None
        self._state: dict[str, Any] = {
            "online": False,
            "ac_output_enabled": False,
            "dc_output_enabled": False,
            "battery_percent": 0,
            "input_watts_total": 0,
            "input_xt60_1_watts": 0,
            "input_xt60_2_watts": 0,
            "output_watts": 0,
            "temperature_c": 0.0,
        }

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
        return [STATE_TOPIC]

    async def start(self, bus: EventBus) -> None:
        self._bus = bus
        await bus.subscribe(COMMAND_TOPIC, self._on_command)
        self._state["online"] = True
        await self._publish_state()
        self._health = HealthStatus(state=HealthState.ok, detail="running")
        await self._publish_health()
        self._maintain_task = asyncio.create_task(self._maintain_loop())

    async def stop(self) -> None:
        if self._maintain_task is not None:
            self._maintain_task.cancel()
            try:
                await self._maintain_task
            except asyncio.CancelledError:
                pass
            self._maintain_task = None

        if self._bus is not None:
            await self._bus.unsubscribe(COMMAND_TOPIC, self._on_command)

        self._state["online"] = False
        await self._publish_state()
        self._health = HealthStatus(state=HealthState.failed, detail="stopped")
        await self._publish_health()
        self._bus = None

    async def _maintain_loop(self) -> None:
        interval = self._config.poll_interval_seconds or DEFAULT_POLL_INTERVAL_SECONDS
        while True:
            await asyncio.sleep(interval)
            # Internal flow: fold dual XT60 model channels into one derived total value.
            self._state["input_watts_total"] = int(self._state["input_xt60_1_watts"]) + int(self._state["input_xt60_2_watts"])
            await self._publish_state()

    async def _on_command(self, _topic: str, payload: dict[str, object]) -> None:
        try:
            command = map_command(payload)
            if command is None:
                self._log.debug("Ignoring unsupported Delta2Max command payload: %s", payload)
                return
            await self._apply_command(command)
            await self._publish_state()
        except Exception as exc:
            self._log.exception("Delta2Max command failed: %s", payload)
            self._state["last_error"] = str(exc)
            self._health = HealthStatus(state=HealthState.failed, detail=f"command failed: {exc}")
            await self._publish_health()
            await self._publish_state()

    async def _apply_command(self, command: Delta2MaxCommand) -> None:
        self._state["last_command"] = command.op
        if command.op == "status.refresh":
            return
        if command.op == "ac.output":
            self._state["ac_output_enabled"] = bool(command.params["enabled"])
            return
        if command.op == "dc.output":
            self._state["dc_output_enabled"] = bool(command.params["enabled"])
            return
        if command.op == "xt60.1.limit":
            self._state["input_xt60_1_watts"] = int(command.params["watts"])
            return
        if command.op == "xt60.2.limit":
            self._state["input_xt60_2_watts"] = int(command.params["watts"])
            return
        msg = f"Unknown Delta2Max internal op: {command.op}"
        raise ValueError(msg)

    async def _publish_state(self) -> None:
        if self._bus is None:
            return
        await self._bus.publish(STATE_TOPIC, sanitize_state(dict(self._state)))

    async def _publish_health(self) -> None:
        if self._bus is None:
            return
        try:
            await self._bus.publish(health_topic(self.name), self._health.to_payload(self.name))
        except Exception:
            self._log.exception("Failed to publish health for %s", self.name)
