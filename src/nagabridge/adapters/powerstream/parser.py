"""Parsing helpers for PowerStream payloads."""

from __future__ import annotations

from typing import Any

from .protocol import Packet


def parse_payload(raw: bytes) -> dict[str, Any]:
    """
    Parse a raw PowerStream payload into a normalized dictionary.

    The transport-specific decoding (framing, crypto, protobuf) is handled by
    adapter/prototype logic. This function exposes a stable normalized shape
    for downstream consumers and tests.
    """
    seq = b"\x00\x00\x00\x00"
    packet = Packet(
        src=0,
        dst=0,
        cmd_set=0,
        cmd_id=0,
        seq=seq,
        payload=raw,
    )
    return {
        "raw_len": len(raw),
        "src": packet.src,
        "dst": packet.dst,
        "cmd_set": packet.cmdSet,
        "cmd_id": packet.cmdId,
        "seq": seq,
    }
