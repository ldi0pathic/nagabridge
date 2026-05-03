from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from nagabridge.core.bus import EventBus


@dataclass(slots=True)
class AdapterHealth:
    online: bool = False
    detail: str = "unknown"


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
    def health(self) -> AdapterHealth: ...

    @abstractmethod
    async def start(self, bus: EventBus) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...
