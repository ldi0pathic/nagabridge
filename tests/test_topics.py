"""Tests for shared topic helper functions."""

from nagabridge.core.topics import bat_state_topic, command_topic, health_topic, normalize_entity, state_topic


def test_normalize_entity_trims_lowercases_and_replaces_spaces() -> None:
    """Device names should be normalized consistently for topic paths."""
    assert normalize_entity("  Delta 2 Max  ") == "delta_2_max"


def test_topic_helpers_apply_domain_and_normalized_entity_segments() -> None:
    """All topic helpers should use normalized entity names in stable topic layouts."""
    assert state_topic("ecoflow", "Delta 2") == "ecoflow/delta_2/state"
    assert command_topic("ecoflow", "Delta 2") == "ecoflow/delta_2/command"
    assert bat_state_topic("ecoflow", "Delta 2") == "ecoflow/delta_2_battery/state"
    assert health_topic("MQTT Adapter") == "system/health/mqtt_adapter"
