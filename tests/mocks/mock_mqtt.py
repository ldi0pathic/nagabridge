"""Mock MQTT adapter used in integration-style tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nagabridge.core.adapter import Adapter
from nagabridge.core.health import HealthStatus

if TYPE_CHECKING:
    from nagabridge.core.bus import EventBus, Payload, Topic


class MockMqttAdapter(Adapter):
    """Mock-MQTT Adapter: sammelt Bus-Events statt Netzwerk-I/O."""

    def __init__(self, subscribe_topic: str = "ecoflow/powerstream/state") -> None:
        """Create a mock MQTT adapter with a single subscribed source topic."""
        self._subscribe_topic = subscribe_topic
        self._health = HealthStatus(online=False, detail="not started")
        self._bus: EventBus | None = None
        self.published: list[tuple[Topic, Payload]] = []

    @property
    def name(self) -> str:
        """Return adapter name."""
        return "mock-mqtt"

    @property
    def version(self) -> str:
        """Return adapter version."""
        return "0.1.0"

    @property
    def health(self) -> HealthStatus:
        """Return current health status."""
        return self._health

    async def start(self, bus: EventBus) -> None:
        """Register event handler and mark adapter as running."""
        self._bus = bus
        await bus.subscribe(self._subscribe_topic, self._on_bus_event)
        self._health = HealthStatus(online=True, detail="running")

    async def stop(self) -> None:
        """Unregister event handler and mark adapter as stopped."""
        if self._bus is not None:
            await self._bus.unsubscribe(self._subscribe_topic, self._on_bus_event)
        self._health = HealthStatus(online=False, detail="stopped")
        self._bus = None

    async def _on_bus_event(self, topic: Topic, payload: Payload) -> None:
        """Record published payload for assertions."""
        self.published.append((topic, payload.copy()))
