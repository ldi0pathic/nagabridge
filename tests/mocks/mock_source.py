"""Mock PowerStream source adapter for tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nagabridge.core.adapter import Adapter
from nagabridge.core.health import HealthStatus

if TYPE_CHECKING:
    from nagabridge.core.bus import EventBus


class MockPowerstreamSourceAdapter(Adapter):
    """Mock-Quelle für Powerstream-State ohne BLE-Hardware."""

    STATE_TOPIC = "ecoflow/powerstream/state"

    def __init__(self) -> None:
        """Initialize source adapter in stopped state."""
        self._bus: EventBus | None = None
        self._health = HealthStatus(online=False, detail="not started")

    @property
    def name(self) -> str:
        """Return adapter name."""
        return "mock-powerstream-source"

    @property
    def version(self) -> str:
        """Return adapter version."""
        return "0.1.0"

    @property
    def health(self) -> HealthStatus:
        """Return current health status."""
        return self._health

    async def start(self, bus: EventBus) -> None:
        """Store bus reference and mark adapter as running."""
        self._bus = bus
        self._health = HealthStatus(online=True, detail="running")

    async def stop(self) -> None:
        """Reset bus reference and mark adapter as stopped."""
        self._health = HealthStatus(online=False, detail="stopped")
        self._bus = None

    async def publish_state(self, power: int, battery: int, pv_input: int) -> None:
        """Publish a synthetic powerstream state payload onto the event bus."""
        if self._bus is None:
            msg = "Adapter not started"
            raise RuntimeError(msg)

        await self._bus.publish(
            self.STATE_TOPIC,
            {"power": power, "battery": battery, "pv_input": pv_input},
        )
