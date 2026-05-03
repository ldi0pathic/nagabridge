from __future__ import annotations

from nagabridge.core.adapter import Adapter
from nagabridge.core.health import HealthStatus
from nagabridge.core.bus import EventBus


class MockPowerstreamSourceAdapter(Adapter):
    """Mock-Quelle für Powerstream-State ohne BLE-Hardware."""

    STATE_TOPIC = "ecoflow/powerstream/state"

    def __init__(self) -> None:
        self._bus: EventBus | None = None
        self._health = HealthStatus(False, "not started")

    @property
    def name(self) -> str:
        return "mock-powerstream-source"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def health(self) -> HealthStatus:
        return self._health

    async def start(self, bus: EventBus) -> None:
        self._bus = bus
        self._health = HealthStatus(True, "running")

    async def stop(self) -> None:
        self._health = HealthStatus(False, "stopped")
        self._bus = None

    async def publish_state(self, power: int, battery: int, pv_input: int) -> None:
        if self._bus is None:
            raise RuntimeError("Adapter not started")

        await self._bus.publish(
            self.STATE_TOPIC,
            {"power": power, "battery": battery, "pv_input": pv_input},
        )
