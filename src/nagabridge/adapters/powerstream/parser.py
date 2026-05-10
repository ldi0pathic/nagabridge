"""Parsing helpers for PowerStream protobuf payloads.

The PowerStream BLE protocol transports protobuf-encoded command payloads inside
Type1 packets.  The project intentionally does not generate protobuf classes at
runtime; instead this module implements the small protobuf-wire subset needed to
extract the inverter values used by nagabridge.
"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass
from typing import Any, Final

log = logging.getLogger(__name__)

WIRE_VARINT: Final = 0
WIRE_FIXED64: Final = 1
WIRE_LENGTH_DELIMITED: Final = 2
WIRE_FIXED32: Final = 5

# Field names from the public PowerStream protobuf definitions used by the old
# prototype and community integrations.  The historic typo "statue" is kept
# because it is part of the device schema.
INVERTER_HEARTBEAT_FIELDS: Final[dict[int, str]] = {
    1: "inv_err_code",
    2: "pv1_err_code",
    3: "inv_warn_code",
    4: "pv1_warn_code",
    5: "pv2_err_code",
    6: "pv2_warning_code",
    7: "bat_err_code",
    8: "bat_warning_code",
    9: "llc_err_code",
    10: "llc_warning_code",
    11: "pv1_statue",
    12: "pv2_statue",
    13: "bat_statue",
    14: "llc_statue",
    15: "inv_statue",
    16: "pv1_input_volt",
    17: "pv1_op_volt",
    18: "pv1_input_cur",
    19: "pv1_input_watts",
    20: "pv1_temp",
    21: "pv2_input_volt",
    22: "pv2_op_volt",
    23: "pv2_input_cur",
    24: "pv2_input_watts",
    25: "pv2_temp",
    26: "bat_input_volt",
    27: "bat_op_volt",
    28: "bat_input_cur",
    29: "bat_input_watts",
    30: "bat_temp",
    31: "bat_soc",
    32: "llc_input_volt",
    33: "llc_op_volt",
    34: "llc_temp",
    35: "inv_input_volt",
    36: "inv_op_volt",
    37: "inv_output_cur",
    38: "inv_output_watts",
    39: "inv_temp",
    40: "inv_freq",
    41: "inv_dc_cur",
    42: "bp_type",
    43: "inv_relay_status",
    44: "pv1_relay_status",
    45: "pv2_relay_status",
    46: "install_country",
    47: "install_town",
    48: "permanent_watts",
    49: "dynamic_watts",
    50: "supply_priority",
    51: "lower_limit",
    52: "upper_limit",
    53: "inv_on_off",
    54: "wireless_err_code",
    55: "wireless_warn_code",
    56: "inv_brightness",
    57: "heartbeat_frequency",
    58: "rated_power",
}

SIGNED_INVERTER_FIELDS: Final[frozenset[int]] = frozenset(
    {
        16,
        17,
        18,
        19,
        20,
        21,
        22,
        23,
        24,
        25,
        26,
        27,
        28,
        29,
        30,
        32,
        33,
        34,
        35,
        36,
        37,
        38,
        39,
        40,
        41,
        42,
        43,
        44,
        45,
    },
)

CORE_INVERTER_FIELDS: Final[frozenset[int]] = frozenset({19, 24, 29, 31, 38, 48, 49, 50, 51, 52, 53, 58})

POWER_ITEM_FIELDS: Final[dict[int, str]] = {
    1: "timestamp",
    2: "timezone",
    3: "inv_to_grid_power",
    4: "inv_to_plug_power",
    5: "battery_power",
    6: "pv1_output_power",
    7: "pv2_output_power",
}

HEADER_FIELDS: Final[dict[int, str]] = {
    1: "pdata",
    2: "src",
    3: "dest",
    4: "d_src",
    5: "d_dest",
    6: "enc_type",
    7: "check_type",
    8: "cmd_func",
    9: "cmd_id",
    10: "data_len",
    11: "need_ack",
    12: "is_ack",
    14: "seq",
    15: "product_id",
    16: "version",
    17: "payload_ver",
    18: "time_snap",
    19: "is_rw_cmd",
    20: "is_queue",
    21: "ack_type",
    22: "code",
    23: "from",
    24: "module_sn",
    25: "device_sn",
}

HEADER_STRING_FIELDS: Final[frozenset[int]] = frozenset({22, 23, 24, 25})


@dataclass(frozen=True, slots=True)
class ProtoField:
    """One decoded protobuf wire field."""

    number: int
    wire_type: int
    value: int | bytes


def parse(payload: bytes) -> dict[str, Any]:
    """Parse a PowerStream protobuf payload into snake_case values.

    Unknown or malformed payloads are returned as ``message_type="unknown"`` and
    logged with a hex dump to make future fixture-driven parser additions easy.
    """
    result = _parse_known_payload(payload)
    if result is None:
        log.debug("Unknown PowerStream payload (%d bytes): %s", len(payload), payload.hex(" "))
        return {"message_type": "unknown", "raw_len": len(payload), "raw_hex": payload.hex()}
    return result


def parse_payload(raw: bytes) -> dict[str, Any]:
    """Backward-compatible alias for older adapter code."""
    return parse(raw)


def _parse_known_payload(payload: bytes) -> dict[str, Any] | None:
    try:
        fields = _decode_message(payload)
    except ValueError as exc:
        log.debug("Malformed PowerStream payload (%d bytes): %s; hex=%s", len(payload), exc, payload.hex(" "))
        return None

    if not fields:
        return {"message_type": "empty", "raw_len": 0}

    heartbeat = _parse_inverter_heartbeat(fields, len(payload))
    if heartbeat is not None:
        return heartbeat

    power_pack = _parse_power_pack(fields, len(payload))
    if power_pack is not None:
        return power_pack

    header_message = _parse_header_message(fields, len(payload))
    if header_message is not None:
        return header_message

    return None


def _decode_message(data: bytes) -> list[ProtoField]:
    fields: list[ProtoField] = []
    offset = 0
    while offset < len(data):
        key, offset = _read_varint(data, offset)
        if key == 0:
            msg = "protobuf field key must not be zero"
            raise ValueError(msg)
        number = key >> 3
        wire_type = key & 0x07

        if wire_type == WIRE_VARINT:
            value, offset = _read_varint(data, offset)
        elif wire_type == WIRE_FIXED64:
            end = offset + 8
            if end > len(data):
                msg = "truncated fixed64 field"
                raise ValueError(msg)
            value = data[offset:end]
            offset = end
        elif wire_type == WIRE_LENGTH_DELIMITED:
            size, offset = _read_varint(data, offset)
            end = offset + size
            if end > len(data):
                msg = "truncated length-delimited field"
                raise ValueError(msg)
            value = data[offset:end]
            offset = end
        elif wire_type == WIRE_FIXED32:
            end = offset + 4
            if end > len(data):
                msg = "truncated fixed32 field"
                raise ValueError(msg)
            value = data[offset:end]
            offset = end
        else:
            msg = f"unsupported protobuf wire type {wire_type}"
            raise ValueError(msg)

        fields.append(ProtoField(number=number, wire_type=wire_type, value=value))
    return fields


def _read_varint(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while offset < len(data):
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, offset
        shift += 7
        if shift >= 70:
            msg = "varint is too long"
            raise ValueError(msg)
    msg = "truncated varint"
    raise ValueError(msg)


def _parse_inverter_heartbeat(fields: list[ProtoField], raw_len: int) -> dict[str, Any] | None:
    field_numbers = {field.number for field in fields}
    if not field_numbers & CORE_INVERTER_FIELDS:
        return None
    if not field_numbers <= set(INVERTER_HEARTBEAT_FIELDS):
        return None
    if any(field.wire_type != WIRE_VARINT for field in fields):
        return None

    result: dict[str, Any] = {"message_type": "inverter_heartbeat", "raw_len": raw_len}
    for field in fields:
        name = INVERTER_HEARTBEAT_FIELDS[field.number]
        value = _coerce_int32(field.value) if field.number in SIGNED_INVERTER_FIELDS else int(field.value)
        _put_repeated(result, name, value)
    _add_heartbeat_derived_values(result)
    return result


def _add_heartbeat_derived_values(result: dict[str, Any]) -> None:
    pv1 = _as_number(result.get("pv1_input_watts"))
    pv2 = _as_number(result.get("pv2_input_watts"))
    if pv1 is not None or pv2 is not None:
        result["pv_input_watts"] = (pv1 or 0) + (pv2 or 0)

    inv_output = _as_number(result.get("inv_output_watts"))
    bat_input = _as_number(result.get("bat_input_watts"))
    if inv_output is not None and bat_input is not None:
        result["battery_charge_watts"] = bat_input if bat_input > 0 else 0
        result["battery_discharge_watts"] = abs(bat_input) if bat_input < 0 else 0


def _parse_power_pack(fields: list[ProtoField], raw_len: int) -> dict[str, Any] | None:
    field_numbers = {field.number for field in fields}
    if not field_numbers <= {1, 2} or 2 not in field_numbers:
        return None

    result: dict[str, Any] = {"message_type": "power_pack", "raw_len": raw_len, "sys_power_stream": []}
    for field in fields:
        if field.number == 1 and field.wire_type == WIRE_VARINT:
            result["sys_seq"] = int(field.value)
        elif field.number == 2 and field.wire_type == WIRE_LENGTH_DELIMITED and isinstance(field.value, bytes):
            result["sys_power_stream"].append(_parse_power_item(field.value))
        else:
            return None
    return result


def _parse_power_item(payload: bytes) -> dict[str, Any]:
    fields = _decode_message(payload)
    item: dict[str, Any] = {}
    for field in fields:
        name = POWER_ITEM_FIELDS.get(field.number, f"unknown_{field.number}")
        if field.wire_type != WIRE_VARINT:
            item[name] = _format_wire_value(field.value)
        elif field.number == 2:
            item[name] = _decode_zigzag32(int(field.value))
        elif field.number == 5:
            item[name] = _coerce_int32(field.value)
        else:
            item[name] = int(field.value)
    return item


def _parse_header_message(fields: list[ProtoField], raw_len: int) -> dict[str, Any] | None:
    if not all(field.number in {1, 2} for field in fields):
        return None
    if not any(field.number == 1 and field.wire_type == WIRE_LENGTH_DELIMITED for field in fields):
        return None

    result: dict[str, Any] = {"message_type": "header_message", "raw_len": raw_len, "headers": []}
    for field in fields:
        if field.number == 1 and isinstance(field.value, bytes):
            result["headers"].append(_parse_header(field.value))
        elif field.number == 2 and isinstance(field.value, bytes):
            result["payload"] = field.value.hex()
        else:
            return None
    return result


def _parse_header(payload: bytes) -> dict[str, Any]:
    header: dict[str, Any] = {}
    for field in _decode_message(payload):
        name = HEADER_FIELDS.get(field.number, f"unknown_{field.number}")
        if field.wire_type == WIRE_LENGTH_DELIMITED and isinstance(field.value, bytes):
            if field.number == 1:
                header[name] = field.value.hex()
                nested = _parse_known_payload(field.value)
                if nested is not None:
                    header["parsed_pdata"] = nested
            elif field.number in HEADER_STRING_FIELDS:
                header[name] = field.value.decode("utf-8", errors="replace")
            else:
                header[name] = field.value.hex()
        elif field.wire_type == WIRE_VARINT:
            header[name] = _coerce_int32(field.value)
        else:
            header[name] = _format_wire_value(field.value)
    return header


def _put_repeated(result: dict[str, Any], name: str, value: int) -> None:
    existing = result.get(name)
    if existing is None:
        result[name] = value
    elif isinstance(existing, list):
        existing.append(value)
    else:
        result[name] = [existing, value]


def _coerce_int32(value: int | bytes) -> int:
    value = int(value)
    if value >= 1 << 63:
        return value - (1 << 64)
    if value >= 1 << 31:
        return value - (1 << 32)
    return value


def _decode_zigzag32(value: int) -> int:
    return (value >> 1) ^ -(value & 1)


def _as_number(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def _format_wire_value(value: int | bytes) -> int | str | float:
    if isinstance(value, int):
        return value
    if len(value) == 4:
        return struct.unpack("<f", value)[0]
    return value.hex()
