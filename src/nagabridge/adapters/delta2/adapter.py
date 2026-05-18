"""Delta 2 adapter implementation."""

from nagabridge.core.adapter import Adapter
from nagabridge.core.bus import EventBus
from nagabridge.core.config import BleDeviceConfig
from nagabridge.core.health import HealthStatus


class Delta2Adapter(Adapter):
    """Adapter stub for Delta 2 devices."""

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
        self._health = HealthStatus(online=False, detail="not implemented")

    async def stop(self) -> None:
        """Stop the adapter lifecycle."""
        self._health = HealthStatus(online=False, detail="stopped")
