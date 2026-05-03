from typing import Any


def parse_payload(raw: bytes) -> dict[str, Any]:
    return {"raw_len": len(raw)}
