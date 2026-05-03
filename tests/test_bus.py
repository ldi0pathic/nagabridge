"""Unit tests for the in-memory EventBus."""

import asyncio
from collections.abc import Awaitable, Callable

import pytest

from nagabridge.core.bus import EventBus, Payload, Topic

Handler = Callable[[Topic, Payload], Awaitable[None]]
THREE_EVENTS = 3


def _ensure(condition: object, message: str) -> None:
    if not condition:
        raise AssertionError(message)


@pytest.fixture
def bus() -> EventBus:
    """Provide a fresh EventBus for each test."""
    return EventBus()


@pytest.mark.asyncio
async def test_subscribe_registers_handler(bus: EventBus) -> None:
    """Subscribing should register a handler exactly once."""
    calls: list[tuple[Topic, Payload]] = []

    async def handler(topic: Topic, payload: Payload) -> None:
        calls.append((topic, payload))

    await bus.subscribe("ecoflow/powerstream/state", handler)
    _ensure(
        bus.subscriber_count("ecoflow/powerstream/state") == 1,
        "Handler should be registered once",
    )


@pytest.mark.asyncio
async def test_subscribe_same_handler_twice_is_idempotent(bus: EventBus) -> None:
    """Subscribing the same handler twice should be idempotent."""

    async def handler(topic: Topic, payload: Payload) -> None:
        _ = topic
        _ = payload

    await bus.subscribe("ecoflow/powerstream/state", handler)
    await bus.subscribe("ecoflow/powerstream/state", handler)
    _ensure(
        bus.subscriber_count("ecoflow/powerstream/state") == 1,
        "Duplicate subscribe should not duplicate handler",
    )


@pytest.mark.asyncio
async def test_unsubscribe_removes_handler(bus: EventBus) -> None:
    """Unsubscribe should remove an existing handler."""

    async def handler(topic: Topic, payload: Payload) -> None:
        _ = topic
        _ = payload

    await bus.subscribe("ecoflow/powerstream/state", handler)
    await bus.unsubscribe("ecoflow/powerstream/state", handler)
    _ensure(
        bus.subscriber_count("ecoflow/powerstream/state") == 0,
        "Handler should be removed",
    )


@pytest.mark.asyncio
async def test_unsubscribe_nonexistent_handler_is_safe(bus: EventBus) -> None:
    """Unsubscribing a missing handler should not fail."""

    async def handler(topic: Topic, payload: Payload) -> None:
        _ = topic
        _ = payload

    await bus.unsubscribe("ecoflow/powerstream/state", handler)


@pytest.mark.asyncio
async def test_invalid_topic_raises_value_error_on_subscribe(bus: EventBus) -> None:
    """Invalid topic format should be rejected on subscribe."""

    async def handler(topic: Topic, payload: Payload) -> None:
        _ = topic
        _ = payload

    with pytest.raises(ValueError, match="Erwartet"):
        await bus.subscribe("system/shutdown", handler)


@pytest.mark.asyncio
async def test_invalid_topic_raises_value_error_on_publish(bus: EventBus) -> None:
    """Invalid topic format should be rejected on publish."""
    with pytest.raises(ValueError, match="Erwartet"):
        await bus.publish("system/shutdown", {"reason": "manual"})


@pytest.mark.asyncio
async def test_publish_calls_subscriber(bus: EventBus) -> None:
    """Publishing should call all subscribers for that topic."""
    received: list[tuple[Topic, Payload]] = []

    async def handler(topic: Topic, payload: Payload) -> None:
        received.append((topic, payload))

    await bus.subscribe("ecoflow/powerstream/state", handler)
    await bus.publish("ecoflow/powerstream/state", {"power": 120})
    await asyncio.sleep(0)

    _ensure(len(received) == 1, "Expected exactly one received event")
    _ensure(
        received[0] == ("ecoflow/powerstream/state", {"power": 120}),
        "Received event should match published payload",
    )


@pytest.mark.asyncio
async def test_publish_calls_multiple_subscribers(bus: EventBus) -> None:
    """Publishing should fan out to all handlers."""
    received_a: list[Payload] = []
    received_b: list[Payload] = []

    async def handler_a(topic: Topic, payload: Payload) -> None:
        _ = topic
        received_a.append(payload)

    async def handler_b(topic: Topic, payload: Payload) -> None:
        _ = topic
        received_b.append(payload)

    await bus.subscribe("ecoflow/powerstream/state", handler_a)
    await bus.subscribe("ecoflow/powerstream/state", handler_b)
    await bus.publish("ecoflow/powerstream/state", {"power": 120})
    await asyncio.sleep(0)

    _ensure(len(received_a) == 1, "First subscriber should receive one event")
    _ensure(len(received_b) == 1, "Second subscriber should receive one event")


@pytest.mark.asyncio
async def test_publish_to_topic_without_subscribers_is_safe(bus: EventBus) -> None:
    """Publishing without subscribers should be a no-op."""
    await bus.publish("ecoflow/powerstream/state", {"power": 120})
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_publish_does_not_affect_other_topics(bus: EventBus) -> None:
    """Handlers should only receive their own subscribed topics."""
    received: list[Payload] = []

    async def handler(topic: Topic, payload: Payload) -> None:
        _ = topic
        received.append(payload)

    await bus.subscribe("ecoflow/powerstream/state", handler)
    await bus.publish("ecoflow/delta2max/state", {"battery": 80})
    await asyncio.sleep(0)

    _ensure(len(received) == 0, "Cross-topic publish should not hit handler")


@pytest.mark.asyncio
async def test_publish_multiple_events_all_delivered(bus: EventBus) -> None:
    """Multiple publishes should enqueue all events to subscribers."""
    received: list[Payload] = []

    async def handler(topic: Topic, payload: Payload) -> None:
        _ = topic
        received.append(payload)

    await bus.subscribe("ecoflow/powerstream/state", handler)
    await bus.publish("ecoflow/powerstream/state", {"power": 100})
    await bus.publish("ecoflow/powerstream/state", {"power": 200})
    await bus.publish("ecoflow/powerstream/state", {"power": 300})
    await asyncio.sleep(0)

    _ensure(len(received) == THREE_EVENTS, "Expected three received events")


@pytest.mark.asyncio
async def test_handler_exception_does_not_crash_bus(bus: EventBus) -> None:
    """A failing handler must not prevent other handlers from running."""
    good_received: list[Payload] = []

    async def bad_handler(topic: Topic, payload: Payload) -> None:
        _ = topic
        _ = payload
        msg = "intentional error"
        raise ValueError(msg)

    async def good_handler(topic: Topic, payload: Payload) -> None:
        _ = topic
        good_received.append(payload)

    await bus.subscribe("ecoflow/powerstream/state", bad_handler)
    await bus.subscribe("ecoflow/powerstream/state", good_handler)
    await bus.publish("ecoflow/powerstream/state", {"power": 120})
    await asyncio.sleep(0)

    _ensure(len(good_received) == 1, "Healthy handler should still receive event")


@pytest.mark.asyncio
async def test_topics_returns_subscribed_topics(bus: EventBus) -> None:
    """`topics` should include active subscriptions."""

    async def handler(topic: Topic, payload: Payload) -> None:
        _ = topic
        _ = payload

    await bus.subscribe("ecoflow/powerstream/state", handler)
    await bus.subscribe("mqtt/connection/state", handler)

    _ensure("ecoflow/powerstream/state" in bus.topics, "Powerstream topic missing")
    _ensure("mqtt/connection/state" in bus.topics, "MQTT topic missing")


@pytest.mark.asyncio
async def test_topics_excludes_empty_topics(bus: EventBus) -> None:
    """`topics` should exclude topics with no subscribers."""

    async def handler(topic: Topic, payload: Payload) -> None:
        _ = topic
        _ = payload

    await bus.subscribe("ecoflow/powerstream/state", handler)
    await bus.unsubscribe("ecoflow/powerstream/state", handler)

    _ensure(
        "ecoflow/powerstream/state" not in bus.topics,
        "Topic should not be listed after unsubscribe",
    )
