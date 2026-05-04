"""Tests for application bootstrap and runtime lifecycle."""

import asyncio
import os
import signal
from pathlib import Path
from types import SimpleNamespace

import pytest

from nagabridge.adapters.delta2.adapter import Delta2Adapter
from nagabridge.adapters.powerstream.adapter import PowerstreamAdapter
from nagabridge.core.bus import EventBus
from nagabridge.core.config import BleDeviceConfig
from nagabridge.main import (
    DEFAULT_CONFIG_PATH,
    build_adapters_from_config,
    main,
    parse_args,
    run,
)


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

    _ensure(exit_code == 2, "Missing config should request operator action")
    _ensure(config.exists(), "Default config should be created")

    content = config.read_text(encoding="utf-8")
    _ensure("[system]" in content, "Default config should contain system section")
    _ensure("[adapters]" in content, "Default config should contain adapters section")

    captured = capsys.readouterr()
    _ensure("Config neu angelegt" in captured.err, "stderr should explain creation")


def test_main_check_config_returns_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
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

        async def trigger_shutdown() -> None:
            await asyncio.sleep(0)
            os.kill(os.getpid(), signal.SIGINT)

        trigger_task = asyncio.create_task(trigger_shutdown())
        _ = trigger_task
        await run(config)

    asyncio.run(scenario())


def test_run_all_adapters_offline_after_shutdown() -> None:
    """Adapters should be offline after simulated shutdown."""
    adapters = [
        PowerstreamAdapter(
            BleDeviceConfig("Powerstream", "AA:BB:CC:DD:EE:FF", "powerstream"),
        ),
        Delta2Adapter(BleDeviceConfig("Delta2", "AA:BB:CC:DD:EE:FE", "delta2")),
    ]

    async def scenario() -> None:
        bus = EventBus()
        shutdown_event = asyncio.Event()

        def _handle_shutdown() -> None:
            shutdown_event.set()

        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGINT, _handle_shutdown)

        for adapter in adapters:
            await adapter.start(bus)

        _ensure(all(a.health.online for a in adapters), "All adapters should be online")

        os.kill(os.getpid(), signal.SIGINT)
        await shutdown_event.wait()

        await bus.publish("system/nagabridge/shutdown", {"reason": "test"})

        for adapter in reversed(adapters):
            await adapter.stop()

    asyncio.run(scenario())
    _ensure(
        all(not adapter.health.online for adapter in adapters),
        "All adapters should be offline after shutdown",
    )
