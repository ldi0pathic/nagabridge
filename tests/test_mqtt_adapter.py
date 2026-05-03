"""Tests for MQTT adapter forwarding and lifecycle behavior."""

import asyncio
import json
import os
from typing import Protocol

import pytest

from nagabridge.adapters.mqtt.adapter import MqttAdapter, MqttAdapterConfig
from nagabridge.core.bus import EventBus
from tests.mocks.mock_source import MockPowerstreamSourceAdapter


class FakeMqttClient:
    """In-memory fake MQTT client used for adapter tests."""

    def __init__(self) -> None:
        """Initialize fake client state trackers."""
        self.connected = False
        self.loop_running = False
        self.auth: tuple[str, str | None] | None = None
        self.published: list[tuple[str, str, int, bool]] = []

    def username_pw_set(self, user: str, password: str | None = None) -> None:
        """Store provided credentials."""
        self.auth = (user, password)

    def connect(self, host: str, port: int) -> None:
        """Mark client as connected."""
        self.connected = True
        _ = host
        _ = port

    def loop_start(self) -> None:
        """Mark background loop as running."""
        self.loop_running = True

    def loop_stop(self) -> None:
        """Mark background loop as stopped."""
        self.loop_running = False

    def disconnect(self) -> None:
        """Mark client as disconnected."""
        self.connected = False

    def publish(
        self,
        topic: str,
        payload: str,
        qos: int = 0,
        *,
        retain: bool = False,
    ) -> None:
        """Capture publish calls for assertions."""
        self.published.append((topic, payload, qos, retain))


class _MqttMessage(Protocol):
    topic: str
    payload: bytes


def _ensure(condition: object, message: str) -> None:
    """Raise AssertionError when condition is false."""
    if not condition:
        raise AssertionError(message)


def test_mqtt_adapter_forwards_bus_events_with_fake_client() -> None:
    """Adapter should publish bus events to fake MQTT client."""

    async def scenario() -> None:
        bus = EventBus()
        source = MockPowerstreamSourceAdapter()
        fake_client = FakeMqttClient()

        adapter = MqttAdapter(
            MqttAdapterConfig(host="broker.local"),
            client_factory=lambda: fake_client,
        )

        await source.start(bus)
        await adapter.start(bus)

        await source.publish_state(power=120, battery=80, pv_input=300)
        await asyncio.sleep(0)

        _ensure(fake_client.connected is True, "Client should connect on adapter start")
        _ensure(fake_client.loop_running is True, "Client loop should run")
        _ensure(
            fake_client.published
            == [
                (
                    "nagabridge/ecoflow/powerstream/state",
                    json.dumps({"power": 120, "battery": 80, "pv_input": 300}),
                    0,
                    False,
                ),
            ],
            "Published payload should match source state",
        )

        await adapter.stop()
        await source.stop()

    asyncio.run(scenario())


def test_mqtt_adapter_stop_before_start_is_safe() -> None:
    """Calling stop before start should not fail."""

    async def scenario() -> None:
        adapter = MqttAdapter(
            MqttAdapterConfig(host="broker.local"),
            client_factory=FakeMqttClient,
        )
        await adapter.stop()
        _ensure(adapter.health.online is False, "Adapter must remain offline")

    asyncio.run(scenario())


def test_mqtt_adapter_with_empty_subscribe_topics_still_starts() -> None:
    """Adapter should start even when no bus topics are configured."""

    async def scenario() -> None:
        bus = EventBus()
        fake_client = FakeMqttClient()
        adapter = MqttAdapter(
            MqttAdapterConfig(host="broker.local", subscribe_topics=[]),
            client_factory=lambda: fake_client,
        )

        await adapter.start(bus)
        _ensure(adapter.health.online is True, "Adapter should be online after start")
        _ensure(bus.topics == [], "No topics should be subscribed")

        await adapter.stop()

    asyncio.run(scenario())


@pytest.mark.skipif(not os.getenv("MQTT_IT_BROKER"), reason="MQTT_IT_BROKER not set")
def test_mqtt_adapter_integration_with_real_broker() -> None:
    """Integration smoke test against a real broker from environment."""
    mqtt = __import__("paho.mqtt.client", fromlist=["Client"])

    host = os.getenv("MQTT_IT_BROKER", "127.0.0.1")
    port = int(os.getenv("MQTT_IT_PORT", "1883"))

    out_topic = "nagabridge/ecoflow/powerstream/state"
    received: list[tuple[str, str]] = []

    def on_message(client: object, userdata: object, msg: _MqttMessage) -> None:
        _ = client
        _ = userdata
        received.append((msg.topic, msg.payload.decode("utf-8")))

    subscriber = mqtt.Client()
    subscriber.on_message = on_message
    subscriber.connect(host, port)
    subscriber.subscribe(out_topic)
    subscriber.loop_start()

    async def scenario() -> None:
        bus = EventBus()
        source = MockPowerstreamSourceAdapter()
        adapter = MqttAdapter(MqttAdapterConfig(host=host, port=port))

        await source.start(bus)
        await adapter.start(bus)

        await source.publish_state(power=42, battery=50, pv_input=99)
        await asyncio.sleep(0.5)

        await adapter.stop()
        await source.stop()

    asyncio.run(scenario())

    subscriber.loop_stop()
    subscriber.disconnect()

    _ensure(bool(received), "Subscriber should receive at least one message")
    _ensure(received[0][0] == out_topic, "Received topic should match output topic")
