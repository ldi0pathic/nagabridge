from __future__ import annotations

from abc import ABC, abstractmethod

from nagabridge.core.bus import EventBus
from nagabridge.core.health import HealthStatus

# Backward compatible alias; avoid duplicate health model classes.
AdapterHealth = HealthStatus


class Adapter(ABC):
    """Formaler Vertrag für alle NagaBridge-Adapter."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def version(self) -> str: ...

    @property
    @abstractmethod
    def health(self) -> HealthStatus: ...

    @abstractmethod
    async def start(self, bus: EventBus) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...
