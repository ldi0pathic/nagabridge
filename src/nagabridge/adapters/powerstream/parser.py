"""PowerStream protobuf parser using wn511_sys_pb2."""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


def _div10(value: int) -> float:
    return round(value / 10, 1)


def parse(payload: bytes) -> dict[str, Any]:
    """Parse a PowerStream payload - called with raw packet payload."""
    try:
        from . import wn511_sys_pb2

        hb = wn511_sys_pb2.inverter_heartbeat()  # type: ignore[attr-defined]
        hb.ParseFromString(payload)
        return _parse_heartbeat(hb)
    except Exception as exc:
        log.debug("inverter_heartbeat parse failed (%s), raw: %s", exc, payload.hex())
        return {"message_type": "unknown", "raw_len": len(payload), "raw_hex": payload.hex()}


def parse_type2(payload: bytes) -> dict[str, Any]:
    """Parse inv_heartbeat_type2."""
    try:
        from . import wn511_sys_pb2

        hb2 = wn511_sys_pb2.inv_heartbeat_type2()  # type: ignore[attr-defined]
        hb2.ParseFromString(payload)
        result: dict[str, Any] = {"message_type": "heartbeat_type2"}
        nh = hb2.new_psdr_heartbeat
        if nh.HasField("f32_lcd_show_soc") and nh.f32_lcd_show_soc > 0:
            result["battery_level"] = round(nh.f32_lcd_show_soc, 1)
        if nh.HasField("chg_remain_time") and nh.chg_remain_time > 0:
            result["charge_time_min"] = nh.chg_remain_time
        if nh.HasField("dsg_remain_time") and nh.dsg_remain_time < 5999:
            result["discharge_time_min"] = nh.dsg_remain_time
        return result
    except Exception as exc:
        log.debug("heartbeat_type2 parse failed: %s", exc)
        return {"message_type": "unknown_type2", "raw_len": len(payload)}


def _parse_heartbeat(hb: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"message_type": "inverter_heartbeat"}

    def _set(key: str, field_name: str, transform: Any = None) -> None:
        try:
            if not hb.HasField(field_name):
                return
            value = getattr(hb, field_name)
            result[key] = transform(value) if transform else value
        except Exception:
            pass

    _set("pv1_input_watts", "pv1_input_watts", _div10)
    _set("pv1_input_volt", "pv1_input_volt", _div10)
    _set("pv1_input_cur", "pv1_input_cur", _div10)
    _set("pv1_temp", "pv1_temp", _div10)

    _set("pv2_input_watts", "pv2_input_watts", _div10)
    _set("pv2_input_volt", "pv2_input_volt", _div10)
    _set("pv2_input_cur", "pv2_input_cur", _div10)
    _set("pv2_temp", "pv2_temp", _div10)

    _set("bat_input_watts", "bat_input_watts", _div10)
    _set("bat_temp", "bat_temp", _div10)
    _set("bat_soc", "bat_soc")

    _set("inv_output_watts", "inv_output_watts", _div10)
    _set("inv_op_volt", "inv_op_volt", _div10)
    _set("inv_freq", "inv_freq", _div10)
    _set("inv_temp", "inv_temp", _div10)
    _set("inv_output_cur", "inv_output_cur", lambda x: round(x / 1000, 2))

    _set("llc_temp", "llc_temp", _div10)
    _set("upper_limit", "upper_limit")
    _set("lower_limit", "lower_limit")
    _set("supply_priority", "supply_priority")
    _set("permanent_watts", "permanent_watts", _div10)
    _set("dynamic_watts", "dynamic_watts", _div10)

    # Derived
    pv1 = result.get("pv1_input_watts", 0)
    pv2 = result.get("pv2_input_watts", 0)
    if pv1 or pv2:
        result["pv_input_watts"] = round(pv1 + pv2, 1)

    return result


# backward compat
def parse_payload(raw: bytes) -> dict[str, Any]:
    return parse(raw)
