"""Tests for Delta 2 packet framing helpers."""

import pytest

from nagabridge.adapters.delta2.protocol import PACKET_PREFIX, Packet, decode_packets, encode_packet


def test_encode_packet_frames_kind_length_and_payload() -> None:
    """Encoded packets should contain prefix, masked kind, length and payload."""
    assert encode_packet(0x1FF, b"abc") == bytes((PACKET_PREFIX, 0xFF, 3)) + b"abc"


def test_encode_packet_rejects_payloads_larger_than_single_byte_length() -> None:
    """The compact Delta 2 frame length is one byte and must be enforced."""
    with pytest.raises(ValueError, match="<=255"):
        encode_packet(0x01, bytes(range(256)))


def test_decode_packets_skips_garbage_and_decodes_multiple_complete_frames() -> None:
    """Stream decoding should resynchronize and return all complete packets."""
    data = b"garbage" + encode_packet(0x01, b"a") + encode_packet(0x02, b"bc")

    packets, buffer = decode_packets(data, bytearray())

    assert packets == [Packet(kind=0x01, payload=b"a"), Packet(kind=0x02, payload=b"bc")]
    assert buffer == bytearray()


def test_decode_packets_buffers_partial_frame_until_remaining_bytes_arrive() -> None:
    """Incomplete frames should remain in the caller-provided stream buffer."""
    frame = encode_packet(0x07, b"payload")

    packets, buffer = decode_packets(frame[:5], bytearray())
    assert packets == []
    assert buffer == bytearray(frame[:5])

    packets, buffer = decode_packets(frame[5:], buffer)
    assert packets == [Packet(kind=0x07, payload=b"payload")]
    assert buffer == bytearray()
