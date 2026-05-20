"""Delta 2 Max adapter implementation."""

from nagabridge.core.adapter import Adapter
from nagabridge.core.bus import EventBus
from nagabridge.core.config import BleDeviceConfig
from nagabridge.core.health import HealthState, HealthStatus


class Delta2MaxAdapter(Adapter):
    """Adapter stub for Delta 2 Max devices."""

    def __init__(self, config: BleDeviceConfig) -> None:
        """Initialize the adapter with BLE device configuration."""
        self._config = config
        self._health = HealthStatus()

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
        _ = bus
        self._health = HealthStatus(state=HealthState.degraded, detail="not implemented")

    @property
    def published_topics(self) -> list[str]:
        """Return state topics published by this adapter."""
        from nagabridge.core.topics import state_topic

        return [state_topic(self._config.domain, self._config.name)]

    async def stop(self) -> None:
        """Stop the adapter lifecycle."""
        self._health = HealthStatus(state=HealthState.failed, detail="stopped")
