from nagabridge.adapters.delta2max.parser import parse_payload


def delta2max_payload() -> bytes:
    return bytes([130, 60, 42])


def test_parse_payload_maps_delta2max_fields() -> None:
    result = parse_payload(delta2max_payload())
    assert result["message_type"] == "delta2max_status"
    assert result["ac_output_watts"] == 130
    assert result["battery_soc"] == 60
    assert result["dual_xt60_input_watts"] == 42
