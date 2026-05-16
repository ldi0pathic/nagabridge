"""Tests for PowerStream protobuf payload parsing."""

from __future__ import annotations

from nagabridge.adapters.powerstream.parser import parse, parse_payload, parse_type2


def test_parse_unknown_payload_returns_unknown() -> None:
    result = parse(b"\xff")
    assert result["message_type"] == "unknown"
    assert result["raw_len"] == 1


def test_parse_payload_is_backward_compatible_alias() -> None:
    result1 = parse(b"\xff")
    result2 = parse_payload(b"\xff")
    assert result1 == result2


def test_parse_real_inverter_heartbeat() -> None:
    from nagabridge.adapters.powerstream.wn511_sys_pb2 import inverter_heartbeat  # type: ignore[attr-defined]

    hb = inverter_heartbeat()
    hb.pv1_input_watts = 140
    hb.pv2_input_watts = 270
    hb.bat_soc = 44
    hb.inv_output_watts = 2000
    hb.permanent_watts = 2000
    payload = hb.SerializeToString()

    result = parse(payload)

    assert result["message_type"] == "inverter_heartbeat"
    assert result["pv1_input_watts"] == 14.0
    assert result["pv2_input_watts"] == 27.0
    assert result["pv_input_watts"] == 41.0
    assert result["bat_soc"] == 44
    assert result["inv_output_watts"] == 200.0
    assert result["permanent_watts"] == 200.0


def test_parse_type2_battery_level() -> None:
    from nagabridge.adapters.powerstream.wn511_sys_pb2 import inv_heartbeat_type2  # type: ignore[attr-defined]

    hb2 = inv_heartbeat_type2()
    hb2.new_psdr_heartbeat.f32_lcd_show_soc = 44.5
    hb2.new_psdr_heartbeat.dsg_remain_time = 400
    payload = hb2.SerializeToString()

    result = parse_type2(payload)

    assert result["message_type"] == "heartbeat_type2"
    assert result["battery_level"] == 44.5
    assert result["discharge_time_min"] == 400
