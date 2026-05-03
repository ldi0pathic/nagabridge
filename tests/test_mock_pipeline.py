import asyncio

from tests.mocks.mock_mqtt import MockMqttAdapter
from tests.mocks.mock_source import MockPowerstreamSourceAdapter
from nagabridge.core.bus import EventBus


def test_mock_powerstream_to_mock_mqtt_pipeline():
    async def scenario() -> None:
        bus = EventBus()
        source = MockPowerstreamSourceAdapter()
        mqtt = MockMqttAdapter()

        await source.start(bus)
        await mqtt.start(bus)

        await source.publish_state(power=120, battery=80, pv_input=300)
        await asyncio.sleep(0)

        assert mqtt.published == [
            (
                "ecoflow/powerstream/state",
                {"power": 120, "battery": 80, "pv_input": 300},
            )
        ]

        await mqtt.stop()
        await source.stop()

    asyncio.run(scenario())


def test_mock_source_requires_start_before_publish():
    async def scenario() -> None:
        source = MockPowerstreamSourceAdapter()
        try:
            await source.publish_state(power=1, battery=2, pv_input=3)
            raised = False
        except RuntimeError:
            raised = True

        assert raised is True

    asyncio.run(scenario())
