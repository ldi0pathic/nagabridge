from __future__ import annotations

import asyncio

from nagabridge.core.bus import EventBus
from nagabridge.core.logging import configure_logging


async def run() -> None:
    configure_logging("INFO")
    bus = EventBus()
    _ = bus


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
