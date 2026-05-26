import asyncio

from nagabridge.adapters.delta2.adapter import Delta2Adapter
from nagabridge.core.bus import EventBus
from nagabridge.core.config import BleDeviceConfig
from nagabridge.core.topics import command_topic, state_topic


def delta2_config() -> BleDeviceConfig:
    return BleDeviceConfig(name="Delta2", mac="AA:BB:CC:DD:EE:01", type="delta2", domain="ecoflow", poll_interval_seconds=3600)


def test_start_stop_lifecycle() -> None:
    async def scenario() -> None:
        bus = EventBus()
        adapter = Delta2Adapter(delta2_config())
        await adapter.start(bus)
        assert adapter.health.is_degraded
        assert bus.subscriber_count(command_topic("ecoflow", "Delta2")) == 1
        await adapter.stop()
        assert adapter.health.is_failed
    asyncio.run(scenario())


def test_ble_notification_updates_state_mapping() -> None:
    async def scenario() -> None:
        bus = EventBus()
        adapter = Delta2Adapter(delta2_config())
        await adapter.start(bus)
        states: list[dict[str, object]] = []
        async def recorder(_topic: str, payload: dict[str, object]) -> None:
            states.append(payload)
        await bus.subscribe(state_topic("ecoflow", "Delta2"), recorder)
        await adapter.on_ble_notification(bytes([110, 50]))
        await asyncio.sleep(0)
        state = states[-1]
        assert state["ac_output_watts"] == 110
        assert state["battery_soc"] == 50
        await adapter.stop()
    asyncio.run(scenario())


def test_command_payload_encodes_packet_and_unsupported_command() -> None:
    async def scenario() -> None:
        bus = EventBus()
        adapter = Delta2Adapter(delta2_config())
        await adapter.start(bus)

        await bus.publish(command_topic("ecoflow", "Delta2"), {"command": "set_ac_output", "watts": 77})
        await asyncio.sleep(0)
        assert adapter._last_encoded_command == bytes([0xA1, 77])  # type: ignore[attr-defined]

        states: list[dict[str, object]] = []
        async def recorder(_topic: str, payload: dict[str, object]) -> None:
            states.append(payload)
        await bus.subscribe(state_topic("ecoflow", "Delta2"), recorder)
        await bus.publish(command_topic("ecoflow", "Delta2"), {"command": "unsupported_x"})
        await asyncio.sleep(0.01)
        assert states and states[-1]["last_error"] == "unsupported_command:unsupported_x"
        await adapter.stop()

    asyncio.run(scenario())
