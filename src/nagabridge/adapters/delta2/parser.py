"""Parsing helpers for Delta 2 payloads."""

from typing import Any


def parse_payload(raw: bytes) -> dict[str, Any]:
    """Parse a raw Delta 2 payload into a normalized dictionary."""
    return {"raw_len": len(raw)}
