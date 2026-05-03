from nagabridge.core.adapter import Adapter, AdapterHealth
from nagabridge.core.bus import EventBus


class Delta2Adapter(Adapter):
    def __init__(self) -> None:
        self._health = AdapterHealth(False, "not started")

    @property
    def name(self) -> str:
        return "delta2"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def health(self) -> AdapterHealth:
        return self._health

    async def start(self, bus: EventBus) -> None:
        self._health = AdapterHealth(True, "running")

    async def stop(self) -> None:
        self._health = AdapterHealth(False, "stopped")
