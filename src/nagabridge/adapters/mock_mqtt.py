from __future__ import annotations

from nagabridge.core.adapter import Adapter, AdapterHealth
from nagabridge.core.bus import EventBus, Payload, Topic


class MockMqttAdapter(Adapter):
    """Mock-MQTT Adapter: sammelt Bus-Events statt Netzwerk-I/O."""

    def __init__(self, subscribe_topic: str = "ecoflow/powerstream/state") -> None:
        self._subscribe_topic = subscribe_topic
        self._health = AdapterHealth(False, "not started")
        self._bus: EventBus | None = None
        self.published: list[tuple[Topic, Payload]] = []

    @property
    def name(self) -> str:
        return "mock-mqtt"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def health(self) -> AdapterHealth:
        return self._health

    async def start(self, bus: EventBus) -> None:
        self._bus = bus
        await bus.subscribe(self._subscribe_topic, self._on_bus_event)
        self._health = AdapterHealth(True, "running")

    async def stop(self) -> None:
        if self._bus is not None:
            await self._bus.unsubscribe(self._subscribe_topic, self._on_bus_event)
        self._health = AdapterHealth(False, "stopped")
        self._bus = None

    async def _on_bus_event(self, topic: Topic, payload: Payload) -> None:
        self.published.append((topic, payload.copy()))
