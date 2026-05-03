"""Pipeline tests between mock source and mock MQTT adapters."""

import asyncio

from nagabridge.core.bus import EventBus
from tests.mocks.mock_mqtt import MockMqttAdapter
from tests.mocks.mock_source import MockPowerstreamSourceAdapter


def test_mock_powerstream_to_mock_mqtt_pipeline() -> None:
    """Ensure source payload reaches MQTT mock through the event bus."""

    async def scenario() -> None:
        bus = EventBus()
        source = MockPowerstreamSourceAdapter()
        mqtt = MockMqttAdapter()

        await source.start(bus)
        await mqtt.start(bus)

        await source.publish_state(power=120, battery=80, pv_input=300)
        await asyncio.sleep(0)

        expected = [
            (
                "ecoflow/powerstream/state",
                {"power": 120, "battery": 80, "pv_input": 300},
            ),
        ]
        if mqtt.published != expected:
            msg = f"Unexpected MQTT payload list: {mqtt.published!r}"
            raise AssertionError(msg)

        await mqtt.stop()
        await source.stop()

    asyncio.run(scenario())


def test_mock_source_requires_start_before_publish() -> None:
    """Ensure source refuses publishing before `start` was called."""

    async def scenario() -> None:
        source = MockPowerstreamSourceAdapter()
        try:
            await source.publish_state(power=1, battery=2, pv_input=3)
            raised = False
        except RuntimeError:
            raised = True

        if raised is not True:
            msg = "Publishing before start() must raise RuntimeError"
            raise AssertionError(msg)

    asyncio.run(scenario())
