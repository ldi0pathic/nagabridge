from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class HealthStatus:
    online: bool = False
    detail: str = "unknown"
