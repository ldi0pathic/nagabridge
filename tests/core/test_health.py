"""Tests for HealthState enum and HealthStatus model."""

from nagabridge.core.health import HealthState, HealthStatus


def test_health_state_enum_values() -> None:
    assert HealthState.ok.value == "ok"
    assert HealthState.degraded.value == "degraded"
    assert HealthState.failed.value == "failed"


def test_health_status_default_is_failed_not_started() -> None:
    h = HealthStatus()
    assert h.state == HealthState.failed
    assert h.detail == "not started"
    assert h.is_failed
    assert not h.is_ok
    assert not h.is_degraded


def test_health_status_ok_state() -> None:
    h = HealthStatus(state=HealthState.ok, detail="running")
    assert h.is_ok
    assert not h.is_degraded
    assert not h.is_failed


def test_health_status_degraded_state() -> None:
    h = HealthStatus(state=HealthState.degraded, detail="no serial number configured")
    assert h.is_degraded
    assert not h.is_ok
    assert not h.is_failed


def test_health_status_failed_state() -> None:
    h = HealthStatus(state=HealthState.failed, detail="start failed: timeout")
    assert h.is_failed
    assert not h.is_ok
    assert not h.is_degraded


def test_health_status_timestamp_is_set() -> None:
    h = HealthStatus()
    assert h.timestamp > 0


def test_health_status_all_three_states_are_distinct() -> None:
    ok = HealthStatus(state=HealthState.ok, detail="running")
    degraded = HealthStatus(state=HealthState.degraded, detail="no data")
    failed = HealthStatus(state=HealthState.failed, detail="error")

    assert ok.is_ok and not ok.is_degraded and not ok.is_failed
    assert degraded.is_degraded and not degraded.is_ok and not degraded.is_failed
    assert failed.is_failed and not failed.is_ok and not failed.is_degraded
