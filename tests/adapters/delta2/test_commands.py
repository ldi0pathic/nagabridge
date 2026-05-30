"""Tests for Delta 2 command payload encoding."""

from nagabridge.adapters.delta2.commands import encode_command
from nagabridge.adapters.delta2.protocol import CMD_REFRESH, CMD_SET_AC_OUTPUT, CMD_SET_XT60_INPUT, KIND_COMMAND_ACK, decode_packets


def _single_payload(frame: bytes | None) -> bytes:
    assert frame is not None
    packets, buffer = decode_packets(frame, bytearray())
    assert buffer == bytearray()
    assert len(packets) == 1
    assert packets[0].kind == KIND_COMMAND_ACK
    return packets[0].payload


def test_encode_command_supports_refresh_aliases() -> None:
    """Both generic refresh command spellings should map to a status refresh."""
    assert _single_payload(encode_command({"command": "get_status"})) == bytes((CMD_REFRESH,))
    assert _single_payload(encode_command({"type": "refresh"})) == bytes((CMD_REFRESH,))


def test_encode_command_maps_ac_output_enabled_and_disabled() -> None:
    """AC output commands should preserve the requested boolean state."""
    assert _single_payload(encode_command({"command": "set_ac_output", "enabled": True})) == bytes((CMD_SET_AC_OUTPUT, 1))
    assert _single_payload(encode_command({"command": "set_ac_output", "enabled": False})) == bytes((CMD_SET_AC_OUTPUT, 0))


def test_encode_command_clamps_xt60_input_watts_to_supported_range() -> None:
    """XT60 input limits should be clamped into the Delta 2 supported range."""
    assert _single_payload(encode_command({"command": "set_xt60_input", "watts": -5})) == bytes((CMD_SET_XT60_INPUT, 0, 0))
    assert _single_payload(encode_command({"command": "set_xt60_input", "watts": 700})) == bytes((CMD_SET_XT60_INPUT, 0x01, 0xF4))


def test_encode_command_ignores_unknown_commands() -> None:
    """Unknown command payloads should be ignored by returning None."""
    assert encode_command({"command": "unsupported"}) is None
