"""Tests for the PowerStream BLE protocol helpers."""
# ruff: noqa: I001

from __future__ import annotations

import struct

import sys
import types


if "Crypto.Cipher" not in sys.modules:
    crypto_module = types.ModuleType("Crypto")
    cipher_module = types.ModuleType("Crypto.Cipher")
    aes_module = types.ModuleType("Crypto.Cipher.AES")

    class _FakeAesCipher:
        def __init__(self, key: bytes, iv: bytes) -> None:
            self._stream = (key + iv) or b"\x00"

        def encrypt(self, data: bytes) -> bytes:
            return bytes(byte ^ self._stream[index % len(self._stream)] for index, byte in enumerate(data))

        def decrypt(self, data: bytes) -> bytes:
            return self.encrypt(data)

    def _new(key: bytes, mode: int, iv: bytes) -> _FakeAesCipher:
        assert mode == aes_module.MODE_CBC
        return _FakeAesCipher(key, iv)

    aes_module.MODE_CBC = 2
    aes_module.block_size = 16
    aes_module.new = _new
    cipher_module.AES = aes_module
    sys.modules["Crypto"] = crypto_module
    sys.modules["Crypto.Cipher"] = cipher_module
    sys.modules["Crypto.Cipher.AES"] = aes_module

import pytest

from nagabridge.adapters.powerstream.protocol import (
    COMMAND_ID_AUTH,
    COMMAND_ID_GET_STATUS,
    COMMAND_ID_HEARTBEAT,
    COMMAND_ID_SET_LOAD_POWER,
    COMMAND_SET_COMMON,
    COMMAND_SET_POWERSTREAM,
    ENC_PACKET_PREFIX,
    Packet,
    Type1Crypto,
    UUID_NOTIFY,
    UUID_WRITE,
    build_auth_md5,
    crc8,
    crc16,
    encode_simple,
    parse_simple,
)


def test_ble_and_command_constants_are_defined() -> None:
    assert UUID_WRITE == "00000002-0000-1000-8000-00805f9b34fb"
    assert UUID_NOTIFY == "00000003-0000-1000-8000-00805f9b34fb"
    assert COMMAND_SET_COMMON == 0x01
    assert COMMAND_SET_POWERSTREAM == 0x02
    assert {COMMAND_ID_AUTH, COMMAND_ID_HEARTBEAT, COMMAND_ID_GET_STATUS, COMMAND_ID_SET_LOAD_POWER} == {0x20, 0x21, 0x22, 0x23}


def test_crc_reference_vectors_match_prototype_algorithms() -> None:
    assert crc8(b"123456789") == 0xF4
    assert crc16(b"123456789") == 0xBB3D


def test_packet_roundtrip_v3_keeps_routing_and_payload() -> None:
    pkt = Packet(src=1, dst=2, dsrc=3, ddst=4, cmd_set=5, cmd_id=6, payload=b"abc", version=3, seq=b"\x01\x02\x03\x04")
    parsed = Packet.from_bytes(pkt.to_bytes())

    assert parsed.src == 1
    assert parsed.dst == 2
    assert parsed.dsrc == 3
    assert parsed.ddst == 4
    assert parsed.cmd_set == 5
    assert parsed.cmd_id == 6
    assert parsed.cmdSet == 5
    assert parsed.cmdId == 6
    assert parsed.payload == b"abc"
    assert parsed.version == 3
    assert parsed.seq == b"\x01\x02\x03\x04"


def test_packet_roundtrip_v2_uses_short_routing_header() -> None:
    pkt = Packet(src=3, dst=4, cmd_set=1, cmd_id=2, payload=b"xy", version=2, seq=b"\x00\x00\x00\x00")
    raw = pkt.toBytes()
    parsed = Packet.fromBytes(raw)

    assert parsed.src == 3
    assert parsed.dst == 4
    assert parsed.dsrc == 0
    assert parsed.ddst == 0
    assert parsed.cmd_set == 1
    assert parsed.cmd_id == 2
    assert parsed.payload == b"xy"
    assert parsed.version == 2


def test_packet_rejects_invalid_seq_length() -> None:
    with pytest.raises(ValueError, match="sequence"):
        Packet(src=1, dst=2, cmd_set=0, cmd_id=0, seq=b"\x00")


def test_packet_rejects_product_id_constructor_argument() -> None:
    with pytest.raises(TypeError):
        Packet(src=1, dst=2, cmd_set=0, cmd_id=0, product_id=99)  # type: ignore[call-arg]


def test_packet_from_bytes_rejects_bad_prefix() -> None:
    raw = Packet(src=1, dst=2, cmd_set=1, cmd_id=1, payload=b"x").to_bytes()
    with pytest.raises(ValueError, match="Bad prefix"):
        Packet.from_bytes(b"\x00" + raw[1:])


def test_packet_from_bytes_rejects_bad_crc8() -> None:
    raw = bytearray(Packet(src=1, dst=2, cmd_set=1, cmd_id=1, payload=b"x").to_bytes())
    raw[4] ^= 0xFF
    with pytest.raises(ValueError, match="CRC8 mismatch"):
        Packet.from_bytes(bytes(raw))


def test_packet_from_bytes_rejects_bad_crc16() -> None:
    raw = bytearray(Packet(src=1, dst=2, cmd_set=1, cmd_id=1, payload=b"x").to_bytes())
    raw[-1] ^= 0xFF
    with pytest.raises(ValueError, match="CRC16 mismatch"):
        Packet.from_bytes(bytes(raw))


def test_packet_xor_payload_roundtrip() -> None:
    payload = b"abc"
    seq = b"\x05\x00\x00\x00"
    pkt = Packet(src=1, dst=2, cmd_set=7, cmd_id=8, payload=payload, version=2, seq=seq)
    raw = pkt.to_bytes()
    payload_start = 16
    payload_end = payload_start + len(payload)
    tampered = raw[:payload_start] + bytes(byte ^ seq[0] for byte in payload) + raw[payload_end:]
    tampered = tampered[:-2] + struct.pack("<H", crc16(tampered[:-2]))

    assert Packet.from_bytes(tampered, xor_payload=True).payload == payload


def test_encode_and_parse_simple_roundtrip() -> None:
    payload = b"hello"
    encoded = encode_simple(payload)

    assert encoded.startswith(ENC_PACKET_PREFIX)
    assert parse_simple(encoded) == payload


def test_parse_simple_returns_none_for_invalid_frames() -> None:
    assert parse_simple(b"no-prefix") is None
    assert parse_simple(ENC_PACKET_PREFIX + b"\x11\x01\x05") is None
    encoded = bytearray(encode_simple(b"abc"))
    encoded[-1] ^= 0x01
    assert parse_simple(bytes(encoded)) is None


def test_parse_simple_ignores_leading_garbage() -> None:
    assert parse_simple(b"\xde\xad" + encode_simple(b"test")) == b"test"


def test_type1_is_ready_after_serial_key_derivation() -> None:
    assert Type1Crypto("SN-XYZ").is_ready


def test_type1_rejects_empty_serial() -> None:
    with pytest.raises(ValueError, match="serial"):
        Type1Crypto("")


def test_type1_encode_decode_roundtrip() -> None:
    crypto = Type1Crypto("SN123")
    pkt = Packet(src=1, dst=2, dsrc=1, ddst=1, cmd_set=9, cmd_id=10, payload=b"abcdef", seq=b"\x00\x00\x00\x00")
    frame = crypto.encode_packet(pkt)
    packets, buffer = crypto.decode_packets(frame, bytearray())

    assert len(packets) == 1
    assert packets[0].src == 1
    assert packets[0].cmd_set == 9
    assert packets[0].payload == b"abcdef"
    assert buffer == bytearray()


def test_type1_xor_payload_applied_on_decode() -> None:
    crypto = Type1Crypto("SN123")
    pkt = Packet(src=1, dst=2, dsrc=1, ddst=1, cmd_set=9, cmd_id=10, payload=b"abcdef", seq=b"\x01\x00\x00\x00")
    packets, _ = crypto.decode_packets(crypto.encode_packet(pkt), bytearray())

    assert len(packets) == 1
    assert packets[0].payload == bytes(byte ^ 0x01 for byte in b"abcdef")


def test_type1_buffers_partial_frame() -> None:
    crypto = Type1Crypto("SN123")
    frame = crypto.encode_packet(Packet(src=1, dst=2, cmd_set=9, cmd_id=10, payload=b"abcdef"))

    packets, buffer = crypto.decode_packets(frame[:8], bytearray())
    assert packets == []
    assert buffer

    packets, buffer = crypto.decode_packets(frame[8:], buffer)
    assert len(packets) == 1
    assert buffer == bytearray()


def test_type1_skips_garbage_before_valid_prefix() -> None:
    crypto = Type1Crypto("SN123")
    frame = crypto.encode_packet(Packet(src=1, dst=2, cmd_set=1, cmd_id=1, payload=b"hi"))

    packets, buffer = crypto.decode_packets(b"\x00\x00\x00" + frame, bytearray())

    assert len(packets) == 1
    assert buffer == bytearray()


def test_type1_empty_input_returns_empty() -> None:
    assert Type1Crypto("SN123").decode_packets(b"", bytearray()) == ([], bytearray())


def test_type1_different_serials_produce_different_ciphertexts() -> None:
    data = b"test" * 4
    assert Type1Crypto("SN-AAA").encrypt(data) != Type1Crypto("SN-BBB").encrypt(data)


def test_build_auth_md5_returns_uppercase_ascii_hex() -> None:
    result = build_auth_md5("user", "device")
    decoded = result.decode("ASCII")

    assert len(result) == 32
    assert decoded == decoded.upper()
    assert all(char in "0123456789ABCDEF" for char in decoded)
    assert build_auth_md5("u", "d") == build_auth_md5("u", "d")
    assert build_auth_md5("user1", "dev") != build_auth_md5("user2", "dev")
