"""Parsing helpers for PowerStream payloads."""

from typing import Any


def parse_payload(raw: bytes) -> dict[str, Any]:
    """Parse a raw PowerStream payload into a normalized dictionary."""
    return {"raw_len": len(raw)}
