"""Tests for PowerStream protobuf payload parsing."""

from __future__ import annotations

import logging

from nagabridge.adapters.powerstream.parser import parse, parse_payload


def _varint(value: int) -> bytes:
    if value < 0:
        value = (1 << 64) + value
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _field(number: int, value: int | bytes, wire_type: int = 0) -> bytes:
    key = (number << 3) | wire_type
    if wire_type == 0:
        assert isinstance(value, int)
        return _varint(key) + _varint(value)
    if wire_type == 2:
        assert isinstance(value, bytes)
        return _varint(key) + _varint(len(value)) + value
    raise AssertionError(f"unsupported test wire type {wire_type}")


def test_parse_inverter_heartbeat_core_values_and_derived_sum() -> None:
    payload = b"".join(
        [
            _field(19, 1234),
            _field(24, 567),
            _field(29, -42),
            _field(31, 88),
            _field(38, 1700),
            _field(48, 600),
            _field(50, 1),
            _field(53, 1),
            _field(58, 8000),
        ],
    )

    result = parse(payload)

    assert result["message_type"] == "inverter_heartbeat"
    assert result["raw_len"] == len(payload)
    assert result["pv1_input_watts"] == 1234
    assert result["pv2_input_watts"] == 567
    assert result["pv_input_watts"] == 1801
    assert result["bat_input_watts"] == -42
    assert result["battery_discharge_watts"] == 42
    assert result["battery_charge_watts"] == 0
    assert result["bat_soc"] == 88
    assert result["inv_output_watts"] == 1700
    assert result["permanent_watts"] == 600
    assert result["supply_priority"] == 1
    assert result["inv_on_off"] == 1
    assert result["rated_power"] == 8000


def test_parse_inverter_heartbeat_preserves_repeated_values() -> None:
    result = parse(_field(19, 100) + _field(19, 200))

    assert result["message_type"] == "inverter_heartbeat"
    assert result["pv1_input_watts"] == [100, 200]


def test_parse_power_pack_with_repeated_power_items() -> None:
    item1 = b"".join([_field(1, 1_700_000_001), _field(2, 0), _field(3, 100), _field(5, -25), _field(6, 90)])
    item2 = b"".join([_field(1, 1_700_000_002), _field(2, 1), _field(4, 10), _field(7, 80)])
    payload = _field(1, 7) + _field(2, item1, wire_type=2) + _field(2, item2, wire_type=2)

    result = parse(payload)

    assert result == {
        "message_type": "power_pack",
        "raw_len": len(payload),
        "sys_seq": 7,
        "sys_power_stream": [
            {
                "timestamp": 1_700_000_001,
                "timezone": 0,
                "inv_to_grid_power": 100,
                "battery_power": -25,
                "pv1_output_power": 90,
            },
            {
                "timestamp": 1_700_000_002,
                "timezone": -1,
                "inv_to_plug_power": 10,
                "pv2_output_power": 80,
            },
        ],
    }


def test_parse_header_message_with_nested_pdata() -> None:
    heartbeat = _field(31, 77) + _field(38, 123)
    header = b"".join([_field(1, heartbeat, wire_type=2), _field(9, 1), _field(24, b"MODULE", wire_type=2), _field(25, b"DEVICE", wire_type=2)])
    payload = _field(1, header, wire_type=2)

    result = parse(payload)

    assert result["message_type"] == "header_message"
    assert result["headers"][0]["cmd_id"] == 1
    assert result["headers"][0]["module_sn"] == "MODULE"
    assert result["headers"][0]["device_sn"] == "DEVICE"
    assert result["headers"][0]["parsed_pdata"]["message_type"] == "inverter_heartbeat"
    assert result["headers"][0]["parsed_pdata"]["bat_soc"] == 77


def test_parse_unknown_payload_logs_hex_dump(caplog) -> None:
    with caplog.at_level(logging.DEBUG, logger="nagabridge.adapters.powerstream.parser"):
        result = parse(b"\xff")

    assert result == {"message_type": "unknown", "raw_len": 1, "raw_hex": "ff"}
    assert "Unknown PowerStream payload" in caplog.text or "Malformed PowerStream payload" in caplog.text
    assert "ff" in caplog.text


def test_parse_payload_is_backward_compatible_alias() -> None:
    payload = _field(31, 55)

    assert parse_payload(payload) == parse(payload)
