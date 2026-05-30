"""Delta 2 packet protocol helpers."""

from __future__ import annotations

from dataclasses import dataclass

PACKET_PREFIX = 0xAA

KIND_STATUS = 0x01
KIND_COMMAND_ACK = 0x02

CMD_REFRESH = 0x01
CMD_SET_AC_OUTPUT = 0x10
CMD_SET_XT60_INPUT = 0x11


@dataclass(frozen=True, slots=True)
class Packet:
    """Simple Delta 2 packet frame."""

    kind: int
    payload: bytes


def encode_packet(kind: int, payload: bytes = b"") -> bytes:
    """Encode a packet using a small framed wire format."""
    length = len(payload)
    if length > 255:
        msg = "payload must be <=255 bytes"
        raise ValueError(msg)
    return bytes((PACKET_PREFIX, kind & 0xFF, length)) + payload


def decode_packets(data: bytes, buffer: bytearray) -> tuple[list[Packet], bytearray]:
    """Decode as many packets as possible from streamed BLE chunks."""
    buf = bytearray(buffer)
    buf.extend(data)
    packets: list[Packet] = []

    while len(buf) >= 3:
        if buf[0] != PACKET_PREFIX:
            buf.pop(0)
            continue
        kind = buf[1]
        length = buf[2]
        total_len = 3 + length
        if len(buf) < total_len:
            break
        payload = bytes(buf[3:total_len])
        packets.append(Packet(kind=kind, payload=payload))
        del buf[:total_len]

    return packets, buf
