from __future__ import annotations

from dataclasses import dataclass, field
import time


@dataclass(slots=True)
class HealthStatus:
    online: bool = False
    detail: str = "not started"
    timestamp: float = field(default_factory=time.monotonic)
