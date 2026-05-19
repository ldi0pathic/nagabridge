"""EcoFlow BLE protocol helpers for PowerStream adapters.

PowerStream devices use the EcoFlow Type1 transport: an ``AA`` packet header
followed by an AES-CBC encrypted packet body.  The AES key and IV are derived
from the device serial number.  Type7/ECDH crypto is intentionally not part of
this module because PowerStream does not use it.
"""

from __future__ import annotations

import hashlib
import logging
import struct
from collections.abc import Sequence
from dataclasses import dataclass

log = logging.getLogger(__name__)

# BLE GATT characteristics used by EcoFlow PowerStream.
UUID_WRITE = "00000002-0000-1000-8000-00805f9b34fb"
UUID_NOTIFY = "00000003-0000-1000-8000-00805f9b34fb"

# Frequently used protocol constants.  Additional command IDs will be added when
# parser and adapter command handling are implemented in later plan steps.
PACKET_PREFIX = b"\xaa"
ENC_PACKET_PREFIX = b"\x5a\x5a"
DEFAULT_VERSION = 0x13
DEFAULT_SEQUENCE = b"\x00\x00\x00\x00"
SIMPLE_FRAME_TYPE = 0x11
ENCRYPTED_FRAME_TYPE = 0x10
DEFAULT_PAYLOAD_TYPE = 0x01
HEADER_LENGTH = 5
CRC16_LENGTH = 2
COMMAND_SET_COMMON = 0x01
COMMAND_SET_POWERSTREAM = 0x02
COMMAND_SET_AUTH = 0x35
COMMAND_ID_AUTH = 0x86
COMMAND_ID_AUTH_STATUS = 0x89
COMMAND_ID_HEARTBEAT = 0x21
COMMAND_ID_GET_STATUS = 0x22
COMMAND_ID_SET_LOAD_POWER = 0x23


def crc8(data: bytes) -> int:
    """Return EcoFlow's CRC-8/CCITT checksum for *data*.

    This matches the prototype's ``crc.Crc8.CCITT`` use: polynomial ``0x07``,
    initial value ``0x00``, no reflection and no final XOR.
    """
    crc = 0x00
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 0x07) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc


def crc16(data: bytes) -> int:
    """Return EcoFlow's reflected CRC-16/IBM checksum for *data*."""
    crc = 0x0000
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


@dataclass(frozen=True, slots=True)
class Packet:
    """EcoFlow inner packet.

    The public constructor intentionally accepts the same core fields that the
    prototype used, but PowerStream-specific code should prefer the snake_case
    properties.  ``cmdSet`` and ``cmdId`` remain as read-only compatibility
    aliases until the rest of the adapter is migrated.
    """

    src: int
    dst: int
    cmd_set: int
    cmd_id: int
    payload: bytes = b""
    dsrc: int = 1
    ddst: int = 1
    version: int = DEFAULT_VERSION
    seq: bytes = DEFAULT_SEQUENCE

    PREFIX = PACKET_PREFIX

    def __post_init__(self) -> None:
        if len(self.seq) != 4:
            msg = "Packet sequence must be exactly four bytes"
            raise ValueError(msg)
        for field_name in ("src", "dst", "cmd_set", "cmd_id", "dsrc", "ddst", "version"):
            value = getattr(self, field_name)
            if not 0 <= value <= 0xFF:
                msg = f"Packet {field_name} must fit into one byte"
                raise ValueError(msg)
        if len(self.payload) > 0xFFFF:
            msg = "Packet payload is too large"
            raise ValueError(msg)

    @property
    def cmdSet(self) -> int:  # noqa: N802 - legacy adapter compatibility
        """Compatibility alias for legacy camelCase callers."""
        return self.cmd_set

    @property
    def cmdId(self) -> int:  # noqa: N802 - legacy adapter compatibility
        """Compatibility alias for legacy camelCase callers."""
        return self.cmd_id

    def to_bytes(self) -> bytes:
        """Serialize this packet and append protocol checksums."""
        data = bytearray(PACKET_PREFIX)
        data.extend(struct.pack("<BH", self.version, len(self.payload)))
        data.append(crc8(bytes(data)))
        data.extend(b"\x0d")
        data.extend(self.seq)
        data.extend(b"\x00\x00")
        data.extend(struct.pack("<BB", self.src, self.dst))
        if self.version >= 0x03:
            data.extend(struct.pack("<BB", self.dsrc, self.ddst))
        data.extend(struct.pack("<BB", self.cmd_set, self.cmd_id))
        data.extend(self.payload)
        data.extend(struct.pack("<H", crc16(bytes(data))))
        return bytes(data)

    def toBytes(self) -> bytes:  # noqa: N802 - legacy adapter compatibility
        """Compatibility wrapper around :meth:`to_bytes`."""
        return self.to_bytes()

    @classmethod
    def from_bytes(cls, data: bytes, *, xor_payload: bool = False) -> Packet:
        """Parse and validate an EcoFlow packet.

        Args:
            data: Raw packet bytes starting with ``0xAA``.
            xor_payload: Undo the PowerStream payload XOR using ``seq[0]``.

        Raises:
            ValueError: If the frame is truncated, malformed or has invalid CRCs.
        """
        if len(data) < HEADER_LENGTH:
            raise ValueError(f"Packet too short: {data.hex()}")
        if not data.startswith(PACKET_PREFIX):
            raise ValueError(f"Bad prefix: {data.hex()}")

        version = data[1]
        payload_length = struct.unpack("<H", data[2:4])[0]
        payload_start = 16 if version == 2 else 18
        frame_length = payload_start + payload_length + CRC16_LENGTH
        if len(data) < frame_length:
            raise ValueError(f"Packet truncated: {data.hex()}")
        frame = data[:frame_length]

        if crc8(frame[:4]) != frame[4]:
            raise ValueError(f"CRC8 mismatch: {frame.hex()}")
        expected_crc16 = struct.unpack("<H", frame[-CRC16_LENGTH:])[0]
        if crc16(frame[:-CRC16_LENGTH]) != expected_crc16:
            raise ValueError(f"CRC16 mismatch: {frame.hex()}")

        seq = frame[6:10]
        src = frame[12]
        dst = frame[13]
        if version == 2:
            dsrc = ddst = 0
            cmd_set, cmd_id = frame[14:16]
        else:
            dsrc, ddst, cmd_set, cmd_id = frame[14:18]

        payload = frame[payload_start : payload_start + payload_length]
        if xor_payload and seq[0] != 0:
            payload = bytes(byte ^ seq[0] for byte in payload)

        return cls(src=src, dst=dst, cmd_set=cmd_set, cmd_id=cmd_id, payload=payload, dsrc=dsrc, ddst=ddst, version=version, seq=seq)

    @classmethod
    def fromBytes(cls, data: bytes, xor_payload: bool = False) -> Packet:  # noqa: N802 - legacy adapter compatibility
        """Compatibility wrapper around :meth:`from_bytes`."""
        return cls.from_bytes(data, xor_payload=xor_payload)


def encode_simple(payload: bytes) -> bytes:
    """Wrap *payload* in an unencrypted ``5A5A`` frame for auth handshakes."""
    inner = bytes([SIMPLE_FRAME_TYPE, DEFAULT_PAYLOAD_TYPE]) + struct.pack("<H", len(payload)) + payload
    return ENC_PACKET_PREFIX + inner + struct.pack("<H", crc16(inner))


def parse_simple(data: bytes) -> bytes | None:
    """Extract a payload from an unencrypted ``5A5A`` frame.

    Returns ``None`` when the input contains no complete frame or the frame CRC
    is invalid.  Leading garbage bytes are ignored, mirroring BLE notification
    streams seen in the prototype.
    """
    start = data.find(ENC_PACKET_PREFIX)
    if start < 0:
        return None
    data = data[start:]
    if len(data) < 8:
        return None

    payload_len = struct.unpack("<H", data[4:6])[0]
    frame_end = 6 + payload_len + CRC16_LENGTH
    if frame_end > len(data):
        return None

    inner = data[2 : 6 + payload_len]
    crc_recv = struct.unpack("<H", data[6 + payload_len : frame_end])[0]
    if crc16(inner) != crc_recv:
        log.debug("Ignoring simple PowerStream frame with invalid CRC16")
        return None
    return inner[4:]


class Type1Crypto:
    """PowerStream Type1 AES-CBC transport keyed by device serial number."""

    block_size = 16

    def __init__(self, dev_sn: str) -> None:
        if not dev_sn:
            msg = "PowerStream serial number must not be empty"
            raise ValueError(msg)
        self._dev_sn = dev_sn
        self._key = hashlib.md5(dev_sn.encode(), usedforsecurity=False).digest()
        self._iv = hashlib.md5(dev_sn[::-1].encode(), usedforsecurity=False).digest()
        log.debug("Initialized Type1Crypto for PowerStream serial ending in %s", dev_sn[-4:])

    def encrypt(self, data: bytes) -> bytes:
        """Encrypt *data* using AES-CBC with null padding."""
        padded_len = ((len(data) + self.block_size - 1) // self.block_size) * self.block_size
        padded = data.ljust(padded_len, b"\x00")
        from Crypto.Cipher import AES  # nosec B413 - protocol compatibility with EcoFlow Type1

        cipher = AES.new(self._key, AES.MODE_CBC, self._iv)
        return bytes(cipher.encrypt(padded))

    def decrypt(self, data: bytes) -> bytes:
        """Decrypt *data* using AES-CBC without stripping null padding."""
        if len(data) % self.block_size != 0:
            msg = "Encrypted Type1 payload length must be a multiple of AES block size"
            raise ValueError(msg)
        from Crypto.Cipher import AES  # nosec B413 - protocol compatibility with EcoFlow Type1

        cipher = AES.new(self._key, AES.MODE_CBC, self._iv)
        return bytes(cipher.decrypt(data))

    def encode_packet(self, packet: Packet) -> bytes:
        """Serialize and encrypt a packet for the PowerStream write characteristic."""
        raw = packet.to_bytes()
        return raw[:HEADER_LENGTH] + self.encrypt(raw[HEADER_LENGTH:])

    def decode_packets(self, data: bytes, buffer: bytearray) -> tuple[Sequence[Packet], bytearray]:
        """Decode all complete Type1 packets from a BLE notification chunk.

        Incomplete trailing data is returned as the next buffer.  Invalid frames
        are skipped with debug/warning logs rather than aborting the stream.
        """
        data = bytes(buffer) + data
        buffer = bytearray()
        packets: list[Packet] = []

        while data:
            start = data.find(PACKET_PREFIX)
            if start < 0:
                log.debug("Dropping %d bytes before PowerStream packet prefix", len(data))
                break
            if start > 0:
                log.debug("Skipping %d garbage bytes before PowerStream packet", start)
                data = data[start:]

            if len(data) < HEADER_LENGTH:
                buffer = bytearray(data)
                break
            if crc8(data[:4]) != data[4]:
                log.debug("Skipping byte after invalid Type1 header CRC8")
                data = data[1:]
                continue

            payload_length = struct.unpack("<H", data[2:4])[0]
            version = data[1]
            body_len = (15 if version >= 3 else 13) + payload_length
            encrypted_len = ((body_len + self.block_size - 1) // self.block_size) * self.block_size
            frame_len = HEADER_LENGTH + encrypted_len
            if len(data) < frame_len:
                buffer = bytearray(data)
                break

            header = data[:HEADER_LENGTH]
            encrypted_body = data[HEADER_LENGTH:frame_len]
            data = data[frame_len:]
            try:
                decrypted = self.decrypt(encrypted_body)
                packets.append(Packet.from_bytes(header + decrypted[:body_len], xor_payload=True))
            except ValueError as exc:
                log.debug("Type1 decode error, skipping packet (%s): %s", type(exc).__name__, exc)
            except Exception as exc:
                log.warning("Type1 decode error (%s): %s", type(exc).__name__, exc)

        return packets, buffer

    @property
    def is_ready(self) -> bool:
        """Type1 is ready immediately after serial-derived key initialization."""
        return True


def build_auth_md5(user_id: str, dev_sn: str) -> bytes:
    """Return ``MD5(user_id + serial)`` as uppercase ASCII hex bytes."""
    md5_data = hashlib.md5((user_id + dev_sn).encode("ASCII"), usedforsecurity=False).digest()
    return md5_data.hex().upper().encode("ASCII")
