import asyncio
import json
import os

import pytest

from nagabridge.adapters.mqtt.adapter import MqttAdapter, MqttAdapterConfig
from nagabridge.core.bus import EventBus
from tests.mocks.mock_source import MockPowerstreamSourceAdapter


class FakeMqttClient:
    def __init__(self) -> None:
        self.connected = False
        self.loop_running = False
        self.auth = None
        self.published = []

    def username_pw_set(self, user, password=None):
        self.auth = (user, password)

    def connect(self, host, port):
        self.connected = True
        self.connect_args = (host, port)

    def loop_start(self):
        self.loop_running = True

    def loop_stop(self):
        self.loop_running = False

    def disconnect(self):
        self.connected = False

    def publish(self, topic, payload, qos=0, retain=False):
        self.published.append((topic, payload, qos, retain))


def test_mqtt_adapter_forwards_bus_events_with_fake_client():
    async def scenario():
        bus = EventBus()
        source = MockPowerstreamSourceAdapter()
        fake_client = FakeMqttClient()

        adapter = MqttAdapter(
            config=MqttAdapterConfig(
                host="broker.local",
                port=1883,
                subscribe_topics=["ecoflow/powerstream/state"],
                publish_prefix="nagabridge",
            ),
            client_factory=lambda: fake_client,
        )

        await source.start(bus)
        await adapter.start(bus)
        await source.publish_state(power=100, battery=90, pv_input=250)
        await asyncio.sleep(0)

        assert fake_client.connected is True
        assert fake_client.loop_running is True
        assert fake_client.published == [
            (
                "nagabridge/ecoflow/powerstream/state",
                json.dumps({"power": 100, "battery": 90, "pv_input": 250}),
                0,
                False,
            )
        ]

        await adapter.stop()
        await source.stop()

    asyncio.run(scenario())


def test_mqtt_adapter_stop_before_start_is_safe():
    async def scenario():
        adapter = MqttAdapter(
            MqttAdapterConfig(host="broker.local"), client_factory=FakeMqttClient
        )
        await adapter.stop()
        assert adapter.health.online is False

    asyncio.run(scenario())


def test_mqtt_adapter_with_empty_subscribe_topics_still_starts():
    async def scenario():
        bus = EventBus()
        fake_client = FakeMqttClient()
        adapter = MqttAdapter(
            MqttAdapterConfig(host="broker.local", subscribe_topics=[]),
            client_factory=lambda: fake_client,
        )

        await adapter.start(bus)
        assert adapter.health.online is True
        assert bus.topics == []

        await adapter.stop()

    asyncio.run(scenario())


@pytest.mark.skipif(not os.getenv("MQTT_IT_BROKER"), reason="MQTT_IT_BROKER not set")
def test_mqtt_adapter_integration_with_real_broker():
    import paho.mqtt.client as mqtt

    host = os.getenv("MQTT_IT_BROKER", "127.0.0.1")
    port = int(os.getenv("MQTT_IT_PORT", "1883"))
    out_topic = "nagabridge/ecoflow/powerstream/state"
    received = []

    def on_message(client, userdata, msg):
        received.append((msg.topic, msg.payload.decode("utf-8")))

    subscriber = mqtt.Client()
    subscriber.on_message = on_message
    subscriber.connect(host, port)
    subscriber.subscribe(out_topic)
    subscriber.loop_start()

    async def scenario():
        bus = EventBus()
        source = MockPowerstreamSourceAdapter()
        adapter = MqttAdapter(MqttAdapterConfig(host=host, port=port))

        await source.start(bus)
        await adapter.start(bus)
        await source.publish_state(power=321, battery=77, pv_input=456)

        for _ in range(20):
            if received:
                break
            await asyncio.sleep(0.05)

        await adapter.stop()
        await source.stop()

    asyncio.run(scenario())

    subscriber.loop_stop()
    subscriber.disconnect()

    assert received
    assert received[0][0] == out_topic
