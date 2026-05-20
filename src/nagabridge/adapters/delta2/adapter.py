"""Delta 2 adapter implementation."""

import logging

from nagabridge.core.adapter import Adapter
from nagabridge.core.bus import EventBus
from nagabridge.core.config import BleDeviceConfig
from nagabridge.core.health import HealthState, HealthStatus
from nagabridge.core.topics import health_topic

_MODULE = __name__.rsplit(".", 1)[0]


class Delta2Adapter(Adapter):
    """Adapter stub for Delta 2 devices."""

    def __init__(self, config: BleDeviceConfig) -> None:
        """Initialize the adapter with BLE device configuration."""
        self._config = config
        self._log = logging.getLogger(f"{_MODULE}.{config.name.lower().replace(' ', '-')}")
        self._health = HealthStatus()
        self._bus: EventBus | None = None

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
        """Start the adapter lifecycle."""
        self._bus = bus
        self._health = HealthStatus(state=HealthState.degraded, detail="not implemented")
        await self._publish_health()

    @property
    def published_topics(self) -> list[str]:
        """Return state topics published by this adapter."""
        from nagabridge.core.topics import state_topic

        return [state_topic(self._config.domain, self._config.name)]

    async def _publish_health(self) -> None:
        if self._bus is None:
            return
        try:
            await self._bus.publish(health_topic(self.name), self._health.to_payload(self.name))
        except Exception:
            self._log.exception("Failed to publish health for %s", self.name)

    async def stop(self) -> None:
        """Stop the adapter lifecycle."""
        self._health = HealthStatus(state=HealthState.failed, detail="stopped")
        await self._publish_health()
        self._bus = None
