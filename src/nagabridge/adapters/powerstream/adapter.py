from nagabridge.core.adapter import Adapter
from nagabridge.core.bus import EventBus
from nagabridge.core.config import BleDeviceConfig
from nagabridge.core.health import HealthStatus


class PowerstreamAdapter(Adapter):
    def __init__(self, config: BleDeviceConfig) -> None:
        self._config = config
        self._health = HealthStatus()

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def health(self) -> HealthStatus:
        return self._health

    async def start(self, bus: EventBus) -> None:
        self._health = HealthStatus(True, "running")

    async def stop(self) -> None:
        self._health = HealthStatus(False, "stopped")
