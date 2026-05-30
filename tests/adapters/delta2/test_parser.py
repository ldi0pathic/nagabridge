from nagabridge.adapters.delta2.parser import parse_payload


def delta2_payload() -> bytes:
    return bytes([120, 55])


def test_parse_payload_maps_delta2_fields() -> None:
    result = parse_payload(delta2_payload())
    assert result["message_type"] == "delta2_status"
    assert result["ac_output_watts"] == 120
    assert result["battery_soc"] == 55


def test_parse_payload_does_not_include_delta2max_fields() -> None:
    result = parse_payload(delta2_payload())
    assert "dual_xt60_input_watts" not in result


def test_parse_status_payload_maps_extended_delta2_telemetry() -> None:
    """Extended Delta 2 telemetry should decode all documented status fields."""
    from nagabridge.adapters.delta2.parser import parse_status_payload

    raw = b"\x02\x27\x00\x78\x01\x2c\x00\xfa\x01"

    assert parse_status_payload(raw) == {
        "battery_percent": 55.1,
        "output_watts": 120,
        "input_watts": 300,
        "xt60_input_watts": 250,
        "ac_output_enabled": True,
    }


def test_parse_status_payload_returns_diagnostics_for_short_payloads() -> None:
    """Short Delta 2 status frames should be diagnosable instead of raising."""
    from nagabridge.adapters.delta2.parser import parse_status_payload

    assert parse_status_payload(b"\x01\x02") == {"raw_len": 2}
