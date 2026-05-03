from nagabridge.core.adapter import Adapter
from nagabridge.core.health import HealthStatus
from nagabridge.core.bus import EventBus


class PowerstreamAdapter(Adapter):
    def __init__(self) -> None:
        self._health = HealthStatus(False, "not started")

    @property
    def name(self) -> str:
        return "powerstream"

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
