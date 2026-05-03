from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(slots=True)
class HealthStatus:
    online: bool = False
    detail: str = "not started"
    timestamp: float = field(default_factory=time.monotonic)
