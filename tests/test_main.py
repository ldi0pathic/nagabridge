"""Tests for application bootstrap and runtime lifecycle."""

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from nagabridge.adapters.delta2.adapter import Delta2Adapter
from nagabridge.adapters.mqtt.adapter import MqttAdapter
from nagabridge.adapters.powerstream.adapter import PowerstreamAdapter
from nagabridge.core.adapter import Adapter
from nagabridge.core.bus import EventBus
from nagabridge.core.config import BleDeviceConfig
from nagabridge.core.health import HealthStatus
from nagabridge.main import (
    DEFAULT_CONFIG_PATH,
    EXIT_CONFIG_ACTION_REQUIRED,
    build_adapters_from_config,
    main,
    parse_args,
    run,
)
from tests.adapters.powerstream.test_adapter import FakeConnection, FakeCrypto


class FakeMqttClient:
    """Minimal MQTT client stub used for tests."""

    def __init__(self) -> None:
        """Initialize disconnected fake client."""
        self.connected = False

    def username_pw_set(self, user: str, password: str | None = None) -> None:
        """Accept credentials without side effects."""
        _ = user
        _ = password

    def connect(self, host: str, port: int) -> None:
        """Mark fake client as connected."""
        _ = host
        _ = port
        self.connected = True

    def loop_start(self) -> None:
        """No-op loop start."""

    def loop_stop(self) -> None:
        """No-op loop stop."""

    def disconnect(self) -> None:
        """Mark fake client as disconnected."""
        self.connected = False

    def publish(
        self,
        topic: str,
        payload: str,
        qos: int = 0,
        *,
        retain: bool = False,
    ) -> None:
        """No-op publish for API compatibility."""
        _ = topic
        _ = payload
        _ = qos
        _ = retain


class FailingStartAdapter(Adapter):
    """Test adapter that fails during start but can still be stopped."""

    def __init__(self, name: str = "failing") -> None:
        self._name = name
        self._health = HealthStatus()
        self.stop_called = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return "test"

    @property
    def health(self) -> HealthStatus:
        return self._health

    async def start(self, bus: EventBus) -> None:
        _ = bus
        self._health = HealthStatus(online=False, detail="start failed")
        raise RuntimeError("boom")

    async def stop(self) -> None:
        self.stop_called = True
        self._health = HealthStatus(online=False, detail="stopped")


class HealthyAdapter(Adapter):
    """Test adapter that starts and stops cleanly."""

    def __init__(self, name: str = "healthy") -> None:
        self._name = name
        self._health = HealthStatus()
        self.start_called = False
        self.stop_called = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return "test"

    @property
    def health(self) -> HealthStatus:
        return self._health

    async def start(self, bus: EventBus) -> None:
        _ = bus
        self.start_called = True
        self._health = HealthStatus(online=True, detail="running")

    async def stop(self) -> None:
        self.stop_called = True
        self._health = HealthStatus(online=False, detail="stopped")


def _write_config(tmp_path: Path) -> Path:
    """Write a temporary valid bridge configuration."""
    cfg = tmp_path / "nagabridge.toml"
    cfg.write_text(
        """
[system]
log_level = "INFO"

[adapters]
[[adapters.ble_device]]
name = "Powerstream"
mac = "AA:BB:CC:DD:EE:FF"
type = "powerstream"

[[adapters.ble_device]]
name = "Delta2"
mac = "AA:BB:CC:DD:EE:FE"
type = "delta2"

[mqtt]
host = "broker.local"
port = 1883
""".strip(),
        encoding="utf-8",
    )
    return cfg


def _ensure(condition: object, message: str) -> None:
    """Raise when a test invariant is violated."""
    if not condition:
        raise AssertionError(message)


def test_parse_args_defaults_to_adr_config_path() -> None:
    """CLI default config path should match ADR-011 location."""
    args = parse_args([])
    _ensure(args.config == DEFAULT_CONFIG_PATH, "Default config path should match ADR")


def test_main_creates_default_config_when_missing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Missing config should be bootstrapped with a default template."""
    config = tmp_path / "missing.toml"
    exit_code = main(["--config", str(config), "--check-config"])

    _ensure(
        exit_code == EXIT_CONFIG_ACTION_REQUIRED,
        "Missing config should request operator action",
    )
    _ensure(config.exists(), "Default config should be created")

    content = config.read_text(encoding="utf-8")
    _ensure("[system]" in content, "Default config should contain system section")
    _ensure("[adapters]" in content, "Default config should contain adapters section")

    captured = capsys.readouterr()
    _ensure("Config neu angelegt" in captured.err, "stderr should explain creation")


def test_main_check_config_returns_zero(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`main --check-config` should validate config and return success."""
    config = _write_config(tmp_path)
    exit_code = main(["--config", str(config), "--check-config"])
    _ensure(exit_code == 0, "check-config should exit 0 for valid config")
    captured = capsys.readouterr()
    _ensure("Config OK" in captured.out, "Success output should mention config status")


def test_build_adapters_from_config_includes_expected_names(tmp_path: Path) -> None:
    """`build_adapters_from_config` should create BLE + MQTT adapters."""
    config = _write_config(tmp_path)
    adapters = build_adapters_from_config(config)

    names = [a.name for a in adapters]
    _ensure("Powerstream" in names, "Powerstream adapter should be present")
    _ensure("Delta2" in names, "Delta2 adapter should be present")
    _ensure("mqtt" in names, "MQTT adapter should be present")

    mqtt = next(adapter for adapter in adapters if isinstance(adapter, MqttAdapter))
    assert mqtt._config.publish_prefix == "nagabridge"  # type: ignore[attr-defined]
    assert set(mqtt._config.subscribe_topics) == {  # type: ignore[attr-defined]
        "ecoflow/powerstream/state",
        "ecoflow/powerstream_battery/state",
        "ecoflow/delta2/state",
    }


def test_run_starts_and_stops_cleanly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`run` should start, receive signal, and shutdown cleanly."""

    def _fake_import_module(module_name: str) -> object:
        if module_name == "paho.mqtt.client":
            return SimpleNamespace(Client=FakeMqttClient)
        msg = f"Unexpected module import requested: {module_name}"
        raise ModuleNotFoundError(msg)

    monkeypatch.setattr(
        "nagabridge.adapters.mqtt.adapter.import_module",
        _fake_import_module,
    )

    async def scenario() -> None:
        config = _write_config(tmp_path)
        log_dir = tmp_path / "logs"

        def _register_shutdown(
            loop: asyncio.AbstractEventLoop,
            shutdown_event: asyncio.Event,
        ) -> None:
            loop.call_soon(shutdown_event.set)

        monkeypatch.setattr(
            "nagabridge.main._register_shutdown_signal_handlers",
            _register_shutdown,
        )
        await run(config, log_dir=log_dir)

    asyncio.run(scenario())


def test_run_continues_when_an_adapter_fails_during_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`run` should keep running when one adapter fails during startup."""

    async def scenario() -> None:
        failing = FailingStartAdapter()
        healthy = HealthyAdapter()

        def _register_shutdown(
            loop: asyncio.AbstractEventLoop,
            shutdown_event: asyncio.Event,
        ) -> None:
            loop.call_soon(shutdown_event.set)

        monkeypatch.setattr(
            "nagabridge.main.build_adapters_from_config",
            lambda *args, **kwargs: [failing, healthy],
        )
        monkeypatch.setattr(
            "nagabridge.main._register_shutdown_signal_handlers",
            _register_shutdown,
        )

        await run(tmp_path / "unused.toml", log_dir=tmp_path / "logs")

        assert healthy.start_called is True
        assert healthy.stop_called is True
        assert failing.stop_called is True

    asyncio.run(scenario())


def test_run_all_adapters_offline_after_shutdown() -> None:
    """Adapters should be offline after simulated shutdown."""
    adapters = [
        PowerstreamAdapter(
            BleDeviceConfig("Powerstream", "AA:BB:CC:DD:EE:FF", "powerstream", serial_number="SN123"),
            connection_factory=lambda cfg: FakeConnection(cfg),
            crypto_factory=lambda _sn: FakeCrypto("SN123"),
        ),
        Delta2Adapter(BleDeviceConfig("Delta2", "AA:BB:CC:DD:EE:FE", "delta2")),
    ]

    async def scenario() -> None:
        bus = EventBus()
        shutdown_event = asyncio.Event()

        for adapter in adapters:
            await adapter.start(bus)

        _ensure(
            adapters[0].health.online is True,
            "Implemented PowerStream adapter should be online after start",
        )
        _ensure(
            adapters[1].health.online is False,
            "Unimplemented Delta2 adapter should stay offline after start",
        )
        _ensure(
            adapters[1].health.detail == "not implemented",
            "Unimplemented Delta2 adapter should report not implemented",
        )

        shutdown_event.set()
        await shutdown_event.wait()

        await bus.publish("system/nagabridge/shutdown", {"reason": "test"})

        for adapter in reversed(adapters):
            await adapter.stop()

    asyncio.run(scenario())
    _ensure(
        all(not adapter.health.online for adapter in adapters),
        "All adapters should be offline after shutdown",
    )


def test_build_adapters_from_config_passes_powerstream_specific_fields(tmp_path: Path) -> None:
    """PowerStream-specific config values should reach the adapter factory."""
    config = tmp_path / "nagabridge.toml"
    config.write_text(
        """
[adapters]
[[adapters.ble_device]]
name = "Powerstream"
mac = "AA:BB:CC:DD:EE:FF"
type = "powerstream"
serial_number = "SN123"
user_id = "USER42"
poll_interval_seconds = 17
reconnect_attempts = 4
reconnect_backoff_seconds = 0.25
write_with_response = true
""".strip(),
        encoding="utf-8",
    )

    adapters = build_adapters_from_config(config)
    powerstream = next(adapter for adapter in adapters if isinstance(adapter, PowerstreamAdapter))

    assert powerstream._config.serial_number == "SN123"  # type: ignore[attr-defined]
    assert powerstream._config.user_id == "USER42"  # type: ignore[attr-defined]
    assert powerstream._config.poll_interval_seconds == 17.0  # type: ignore[attr-defined]
    assert powerstream._config.reconnect_attempts == 4  # type: ignore[attr-defined]
    assert powerstream._config.reconnect_backoff_seconds == 0.25  # type: ignore[attr-defined]
    assert powerstream._config.write_with_response is True  # type: ignore[attr-defined]
