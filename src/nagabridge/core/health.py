"""Health status model shared by all adapters."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class HealthState(Enum):
    ok = "ok"
    degraded = "degraded"
    failed = "failed"


@dataclass(slots=True)
class HealthStatus:
    """Snapshot of adapter runtime health."""

    state: HealthState = HealthState.failed
    detail: str = "not started"
    timestamp: float = field(default_factory=time.monotonic)

    @property
    def is_ok(self) -> bool:
        return self.state == HealthState.ok

    @property
    def is_degraded(self) -> bool:
        return self.state == HealthState.degraded

    @property
    def is_failed(self) -> bool:
        return self.state == HealthState.failed
