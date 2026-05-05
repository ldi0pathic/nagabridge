import struct
import sys
import types

import pytest

if "ecdsa" not in sys.modules:
    ecdsa_stub = types.ModuleType("ecdsa")

    class _DummyVerifyingKey:
        def to_string(self) -> bytes:
            return b"\x01" * 40

        @staticmethod
        def from_string(data: bytes, curve: object = None) -> "_DummyVerifyingKey":
            _ = data
            _ = curve
            return _DummyVerifyingKey()

    class _DummySigningKey:
        @staticmethod
        def generate(curve: object = None) -> "_DummySigningKey":
            _ = curve
            return _DummySigningKey()

        def get_verifying_key(self) -> _DummyVerifyingKey:
            return _DummyVerifyingKey()

    class _DummyECDH:
        def __init__(self, curve: object, priv: object, pub: object) -> None:
            _ = curve
            _ = priv
            _ = pub

        def generate_sharedsecret_bytes(self) -> bytes:
            return b"\x02" * 20

    ecdsa_stub.SECP160r1 = object()
    ecdsa_stub.SigningKey = _DummySigningKey
    ecdsa_stub.VerifyingKey = _DummyVerifyingKey
    ecdsa_stub.ECDH = _DummyECDH
    sys.modules["ecdsa"] = ecdsa_stub

if "crc" not in sys.modules:
    crc_stub = types.ModuleType("crc")

    class _DummyConfig:
        def __init__(self, **kwargs: object) -> None:
            self.width = int(kwargs.get("width", 8))

    class _DummyCalculator:
        def __init__(self, config: _DummyConfig) -> None:
            self._mask = (1 << config.width) - 1

        def checksum(self, data: bytes) -> int:
            return sum(data) & self._mask

    crc_stub.Configuration = _DummyConfig
    crc_stub.Calculator = _DummyCalculator
    sys.modules["crc"] = crc_stub

if "Crypto" not in sys.modules:
    crypto_pkg = types.ModuleType("Crypto")
    cipher_mod = types.ModuleType("Crypto.Cipher")
    publickey_mod = types.ModuleType("Crypto.PublicKey")
    util_mod = types.ModuleType("Crypto.Util")
    padding_mod = types.ModuleType("Crypto.Util.Padding")

    class _DummyAESCipher:
        def __init__(self, key: bytes, mode: int, iv: bytes) -> None:
            _ = key
            _ = mode
            _ = iv

        def encrypt(self, data: bytes) -> bytes:
            return data

        def decrypt(self, data: bytes) -> bytes:
            return data

    class _DummyAES:
        MODE_CBC = 1
        block_size = 16

        @staticmethod
        def new(key: bytes, mode: int, iv: bytes) -> _DummyAESCipher:
            return _DummyAESCipher(key, mode, iv)

    class _DummyECC:
        @staticmethod
        def import_key(key: str) -> object:
            _ = key
            return object()

    def _pad(data: bytes, block_size: int) -> bytes:
        pad_len = block_size - (len(data) % block_size)
        return data + bytes([pad_len]) * pad_len

    def _unpad(data: bytes, block_size: int) -> bytes:
        _ = block_size
        return data[: -data[-1]]

    cipher_mod.AES = _DummyAES
    publickey_mod.ECC = _DummyECC
    padding_mod.pad = _pad
    padding_mod.unpad = _unpad
    util_mod.Padding = padding_mod

    sys.modules["Crypto"] = crypto_pkg
    sys.modules["Crypto.Cipher"] = cipher_mod
    sys.modules["Crypto.PublicKey"] = publickey_mod
    sys.modules["Crypto.Util"] = util_mod
    sys.modules["Crypto.Util.Padding"] = padding_mod

from nagabridge.adapters.powerstream.protocol import (
    Packet,
    Type1Crypto,
    Type7Crypto,
    build_auth_md5,
    crc16,
    encode_simple,
    parse_simple,
)

# PREFIX_5A ist jetzt _PREFIX_5A (modulintern) - wir rekonstruieren es lokal
_PREFIX_5A = b"\x5a\x5a"


# =============================================================================
# Packet - toBytes / fromBytes
# =============================================================================


def test_packet_roundtrip_v3():
    pkt = Packet(
        src=1,
        dst=2,
        dsrc=3,
        ddst=4,
        cmd_set=5,
        cmd_id=6,
        payload=b"abc",
        version=3,
        seq=b"\x01\x02\x03\x04",
    )
    raw = pkt.toBytes()
    parsed = Packet.fromBytes(raw)

    assert parsed.src == 1
    assert parsed.dst == 2
    assert parsed.cmdSet == 5
    assert parsed.cmdId == 6
    assert parsed.payload == b"abc"
    assert parsed.version == 3


def test_packet_roundtrip_v2():
    pkt = Packet(
        src=3, dst=4, cmd_set=1, cmd_id=2, payload=b"xy", version=2,
        seq=b"\x00\x00\x00\x00",
    )
    raw = pkt.toBytes()
    parsed = Packet.fromBytes(raw)

    assert parsed.src == 3
    assert parsed.dst == 4
    assert parsed.cmdSet == 1
    assert parsed.cmdId == 2
    assert parsed.payload == b"xy"
    assert parsed.version == 2


def test_packet_roundtrip_empty_payload():
    pkt = Packet(src=1, dst=2, cmd_set=0, cmd_id=0, payload=b"")
    raw = pkt.toBytes()
    parsed = Packet.fromBytes(raw)
    assert parsed.payload == b""


def test_packet_default_seq_is_four_zero_bytes():
    pkt = Packet(src=1, dst=2, cmd_set=0, cmd_id=0)
    raw = pkt.toBytes()
    # seq starts at offset 6
    assert raw[6:10] == b"\x00\x00\x00\x00"


def test_packet_xor_payload_roundtrip():
    """``fromBytes`` mit xor_payload=True muss das XOR korrekt rueckgaengig machen."""
    original_payload = bytes([0x10, 0x20, 0x30])
    seq = b"\x05\x00\x00\x00"
    pkt = Packet(
        src=1, dst=2, cmd_set=7, cmd_id=8,
        payload=original_payload, version=2, seq=seq,
    )
    raw = pkt.toBytes()

    # Payload im Frame manuell XOR-en (wie das Gerät es sendet)
    payload_start = 16
    payload_end = payload_start + len(original_payload)
    xor_payload = bytes(c ^ seq[0] for c in original_payload)
    tampered = raw[:payload_start] + xor_payload + raw[payload_end:]
    tampered = tampered[:-2] + struct.pack("<H", crc16(tampered[:-2]))

    parsed = Packet.fromBytes(tampered, xor_payload=True)
    assert parsed.payload == original_payload


def test_packet_xor_payload_skipped_when_seq0_is_zero():
    """Xor_payload=True darf bei seq[0]==0 nichts verändern."""
    payload = bytes([0xAA, 0xBB])
    pkt = Packet(src=1, dst=2, cmd_set=1, cmd_id=1, payload=payload,
                 seq=b"\x00\x00\x00\x00")
    raw = pkt.toBytes()
    parsed = Packet.fromBytes(raw, xor_payload=True)
    assert parsed.payload == payload


def test_packet_from_bytes_rejects_bad_prefix():
    pkt = Packet(src=1, dst=2, cmd_set=1, cmd_id=1, payload=b"x")
    raw = pkt.toBytes()
    with pytest.raises(ValueError, match="Bad prefix"):
        Packet.fromBytes(b"\x00" + raw[1:])


def test_packet_from_bytes_rejects_bad_crc8():
    pkt = Packet(src=1, dst=2, cmd_set=1, cmd_id=1, payload=b"x")
    raw = bytearray(pkt.toBytes())
    raw[4] ^= 0xFF
    with pytest.raises(ValueError, match="CRC8 mismatch"):
        Packet.fromBytes(bytes(raw))


def test_packet_from_bytes_rejects_bad_crc16():
    pkt = Packet(src=1, dst=2, cmd_set=1, cmd_id=1, payload=b"x")
    raw = bytearray(pkt.toBytes())
    raw[-1] ^= 0xFF
    with pytest.raises(ValueError, match="CRC16 mismatch"):
        Packet.fromBytes(bytes(raw))


def test_packet_no_product_id_in_constructor():
    """Product_id wurde entfernt - Konstruktor kennt dieses Argument nicht mehr."""
    with pytest.raises(TypeError):
        Packet(  # type: ignore[call-arg]
            src=1, dst=2, cmd_set=0, cmd_id=0, product_id=99
        )


# =============================================================================
# encode_simple / parse_simple
# =============================================================================


def test_encode_simple_starts_with_prefix():
    encoded = encode_simple(b"hello")
    assert encoded.startswith(_PREFIX_5A)


def test_encode_and_parse_simple_roundtrip():
    """Parse_simple muss die ursprüngliche Payload zurückgeben."""
    payload = b"hello"
    encoded = encode_simple(payload)
    result = parse_simple(encoded)
    assert result == payload


def test_encode_and_parse_simple_empty_payload():
    result = parse_simple(encode_simple(b""))
    assert result == b""


def test_parse_simple_returns_none_for_no_prefix():
    assert parse_simple(b"no-prefix-here") is None


def test_parse_simple_returns_none_for_truncated_data():
    assert parse_simple(_PREFIX_5A + b"\x11\x01\x05") is None


def test_parse_simple_returns_none_for_bad_crc():
    encoded = bytearray(encode_simple(b"abc"))
    encoded[-1] ^= 0x01
    assert parse_simple(bytes(encoded)) is None


def test_parse_simple_ignores_leading_garbage():
    """Führende Bytes vor dem Präfix werden übersprungen."""
    payload = b"test"
    encoded = b"\xde\xad\xbe\xef" + encode_simple(payload)
    assert parse_simple(encoded) == payload


# =============================================================================
# Type7Crypto
# =============================================================================


def test_type7_not_ready_before_key_exchange():
    crypto = Type7Crypto()
    assert not crypto.is_ready


def test_type7_ready_after_compute_shared_key():
    crypto = Type7Crypto()
    crypto.compute_shared_key(b"\x03" * 40)
    assert crypto.is_ready


def test_type7_requires_session_key_before_encrypt():
    crypto = Type7Crypto()
    with pytest.raises(ValueError, match="Session key not initialized"):
        crypto.encrypt(b"data")


def test_type7_requires_iv_before_encrypt():
    crypto = Type7Crypto()
    crypto._session_key = b"1" * 16  # type: ignore[attr-defined]
    with pytest.raises(ValueError, match="IV not initialized"):
        crypto.encrypt(b"data")


def test_type7_requires_initialization_before_decrypt_raw():
    crypto = Type7Crypto()
    with pytest.raises(ValueError, match="Session key not initialized"):
        crypto.decrypt_raw(b"\x00" * 16)


def test_type7_process_key_info_requires_initialization():
    """Process_key_info ohne Init muss ValueError werfen."""
    crypto = Type7Crypto()
    with pytest.raises(ValueError, match="Session key not initialized"):
        crypto.process_key_info(b"\x00" * 32)


def test_type7_encode_decode_packet_roundtrip():
    crypto = Type7Crypto()
    crypto._session_key = b"1" * 16  # type: ignore[attr-defined]
    crypto._iv = b"2" * 16  # type: ignore[attr-defined]

    pkt = Packet(
        src=10, dst=20, dsrc=1, ddst=1, cmd_set=2, cmd_id=3, payload=b"payload"
    )
    frame = crypto.encode_packet(pkt)

    assert frame.startswith(_PREFIX_5A)
    # Stub-AES ist identity → decode sollte Paket wiederherstellen
    decoded = crypto.decode_packets(frame)
    assert isinstance(decoded, list)
    assert len(decoded) == 1
    assert decoded[0].src == 10
    assert decoded[0].cmdSet == 2


def test_type7_decode_packets_skips_bad_crc():
    crypto = Type7Crypto()
    crypto._session_key = b"1" * 16  # type: ignore[attr-defined]
    crypto._iv = b"2" * 16  # type: ignore[attr-defined]

    frame = bytearray(crypto.encode_packet(
        Packet(src=1, dst=2, cmd_set=1, cmd_id=1, payload=b"x")
    ))
    frame[-3] ^= 0xFF  # CRC des äußeren Frames kaputtmachen
    result = crypto.decode_packets(bytes(frame))
    assert result == []


def test_type7_decode_packets_empty_input():
    crypto = Type7Crypto()
    crypto._session_key = b"1" * 16  # type: ignore[attr-defined]
    crypto._iv = b"2" * 16  # type: ignore[attr-defined]
    assert crypto.decode_packets(b"") == []


def test_type7_decode_packets_ignores_leading_garbage():
    crypto = Type7Crypto()
    crypto._session_key = b"1" * 16  # type: ignore[attr-defined]
    crypto._iv = b"2" * 16  # type: ignore[attr-defined]

    frame = crypto.encode_packet(
        Packet(src=5, dst=6, cmd_set=3, cmd_id=4, payload=b"hi")
    )
    garbage = b"\xde\xad\xbe\xef" + frame
    decoded = crypto.decode_packets(garbage)
    assert len(decoded) == 1
    assert decoded[0].src == 5


# =============================================================================
# Type1Crypto
# =============================================================================


def test_type1_is_always_ready():
    assert Type1Crypto("SN-XYZ").is_ready


def test_type1_encode_decode_roundtrip():
    crypto = Type1Crypto("SN123")
    pkt = Packet(
        src=1, dst=2, dsrc=1, ddst=1, cmd_set=9, cmd_id=10,
        payload=b"abcdef", seq=b"\x00\x00\x00\x00",
    )
    frame = crypto.encode_packet(pkt)
    packets, buffer = crypto.decode_packets(frame, bytearray())

    assert len(packets) == 1
    assert packets[0].src == 1
    assert packets[0].payload == b"abcdef"
    assert buffer == bytearray()


def test_type1_xor_payload_applied_on_decode():
    """Decode_packets wendet XOR an; seq[0] != 0 muss payload transformieren."""
    crypto = Type1Crypto("SN123")
    pkt = Packet(
        src=1, dst=2, dsrc=1, ddst=1, cmd_set=9, cmd_id=10,
        payload=b"abcdef", seq=b"\x01\x00\x00\x00",
    )
    frame = crypto.encode_packet(pkt)
    packets, _ = crypto.decode_packets(frame, bytearray())

    assert len(packets) == 1
    assert packets[0].payload == bytes(c ^ 0x01 for c in b"abcdef")


def test_type1_buffering_partial_frame():
    """Unvollständiger Frame landet im Buffer, zweiter Aufruf ergänzt ihn."""
    crypto = Type1Crypto("SN123")
    pkt = Packet(
        src=1, dst=2, dsrc=1, ddst=1, cmd_set=9, cmd_id=10,
        payload=b"abcdef", seq=b"\x01\x00\x00\x00",
    )
    frame = crypto.encode_packet(pkt)

    partial = frame[:8]
    packets, buffer = crypto.decode_packets(partial, bytearray())
    assert packets == []
    assert buffer

    packets, buffer = crypto.decode_packets(frame[8:], buffer)
    assert len(packets) == 1
    assert buffer == bytearray()


def test_type1_empty_input_returns_empty():
    crypto = Type1Crypto("SN123")
    packets, buffer = crypto.decode_packets(b"", bytearray())
    assert packets == []
    assert buffer == bytearray()


def test_type1_different_serials_produce_different_keys():
    c1 = Type1Crypto("SN-AAA")
    c2 = Type1Crypto("SN-BBB")
    data = b"test" * 4
    assert c1.encrypt(data) != c2.encrypt(data)


def test_type1_skips_garbage_before_valid_prefix():
    crypto = Type1Crypto("SN123")
    pkt = Packet(src=1, dst=2, cmd_set=1, cmd_id=1, payload=b"hi")
    frame = crypto.encode_packet(pkt)
    # Führende Nullen vor dem Frame - Decoder soll überspringen
    packets, _ = crypto.decode_packets(b"\x00\x00\x00" + frame, bytearray())
    assert len(packets) == 1


# =============================================================================
# build_auth_md5
# =============================================================================


def test_build_auth_md5_returns_bytes():
    result = build_auth_md5("user", "device")
    assert isinstance(result, bytes)


def test_build_auth_md5_length_is_32():
    result = build_auth_md5("user", "device")
    assert len(result) == 32


def test_build_auth_md5_is_uppercase_hex():
    result = build_auth_md5("user", "device")
    decoded = result.decode("ASCII")
    assert decoded == decoded.upper()
    assert all(c in "0123456789ABCDEF" for c in decoded)


def test_build_auth_md5_is_deterministic():
    assert build_auth_md5("u", "d") == build_auth_md5("u", "d")


def test_build_auth_md5_differs_by_input():
    assert build_auth_md5("user1", "dev") != build_auth_md5("user2", "dev")
    assert build_auth_md5("user", "dev1") != build_auth_md5("user", "dev2")
