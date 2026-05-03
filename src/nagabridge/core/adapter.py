"""Abstract adapter contract used across all integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nagabridge.core.bus import EventBus
    from nagabridge.core.health import HealthStatus


class Adapter(ABC):
    """Formaler Vertrag für alle NagaBridge-Adapter."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return stable adapter name."""
        raise NotImplementedError

    @property
    @abstractmethod
    def version(self) -> str:
        """Return adapter implementation version."""
        raise NotImplementedError

    @property
    @abstractmethod
    def health(self) -> HealthStatus:
        """Return current runtime health snapshot."""
        raise NotImplementedError

    @abstractmethod
    async def start(self, bus: EventBus) -> None:
        """Start the adapter and attach to the event bus."""
        raise NotImplementedError

    @abstractmethod
    async def stop(self) -> None:
        """Stop the adapter and release resources."""
        raise NotImplementedError
