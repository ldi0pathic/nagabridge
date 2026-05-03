"""Health status model shared by all adapters."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(slots=True)
class HealthStatus:
    """Snapshot of adapter runtime health."""

    online: bool = False
    detail: str = "not started"
    timestamp: float = field(default_factory=time.monotonic)
