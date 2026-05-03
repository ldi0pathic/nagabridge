import asyncio
import os
import signal
from pathlib import Path

from nagabridge.core.bus import EventBus
from nagabridge.core.config import BleDeviceConfig
from nagabridge.main import build_adapters_from_config, run


class FakeMqttClient:
    def __init__(self) -> None:
        self.connected = False

    def username_pw_set(self, user, password=None):
        pass

    def connect(self, host, port):
        self.connected = True

    def loop_start(self):
        pass

    def loop_stop(self):
        pass

    def disconnect(self):
        self.connected = False

    def publish(self, topic, payload, qos=0, retain=False):
        pass


def _write_config(tmp_path: Path, with_mqtt: bool = False) -> Path:
    mqtt_section = (
        """
[mqtt]
host = "127.0.0.1"
port = 1883
"""
        if with_mqtt
        else ""
    )
    config = tmp_path / "nagabridge.toml"
    config.write_text(
        f"""
[system]
log_level = "INFO"
{mqtt_section}
[[adapters.ble_device]]
name = "Powerstream"
mac = "AA:BB:CC:DD:EE:FF"
type = "powerstream"

[[adapters.ble_device]]
name = "Delta2"
mac = "AA:BB:CC:DD:EE:FE"
type = "delta2"
""",
        encoding="utf-8",
    )
    return config


def test_build_adapters_from_config_builds_ble_and_mqtt(tmp_path: Path):
    adapters = build_adapters_from_config(_write_config(tmp_path, with_mqtt=True))
    names = [a.name for a in adapters]
    assert "Powerstream" in names
    assert "Delta2" in names
    assert "mqtt" in names


def test_run_starts_and_stops_cleanly(tmp_path: Path):
    """run() wartet auf Signal und stoppt alle Adapter sauber."""

    async def scenario():
        config = _write_config(tmp_path)

        async def trigger_shutdown():
            await asyncio.sleep(0)
            os.kill(os.getpid(), signal.SIGINT)

        asyncio.create_task(trigger_shutdown())
        await run(config)

    asyncio.run(scenario())


def test_run_all_adapters_offline_after_shutdown(tmp_path: Path):
    """Nach Shutdown sind alle Adapter offline."""
    from nagabridge.adapters.delta2.adapter import Delta2Adapter
    from nagabridge.adapters.powerstream.adapter import PowerstreamAdapter

    adapters = [
        PowerstreamAdapter(
            BleDeviceConfig("Powerstream", "AA:BB:CC:DD:EE:FF", "powerstream"),
        ),
        Delta2Adapter(BleDeviceConfig("Delta2", "AA:BB:CC:DD:EE:FE", "delta2")),
    ]

    async def scenario():
        bus = EventBus()
        shutdown_event = asyncio.Event()

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, shutdown_event.set)

        for adapter in adapters:
            await adapter.start(bus)

        assert all(a.health.online for a in adapters)

        os.kill(os.getpid(), signal.SIGINT)
        await shutdown_event.wait()

        for adapter in reversed(adapters):
            await adapter.stop()

    asyncio.run(scenario())

    assert all(not a.health.online for a in adapters)
