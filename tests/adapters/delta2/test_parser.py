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
