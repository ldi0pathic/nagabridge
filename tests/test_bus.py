# =============================================================================
# tests/core/test_bus.py - Tests für den Event Bus
# =============================================================================

import asyncio
import pytest
from nagabridge.core.bus import EventBus

# --- Fixtures ----------------------------------------------------------------


@pytest.fixture
def bus():
    return EventBus()


# --- Subscribe / Unsubscribe -------------------------------------------------


@pytest.mark.asyncio
async def test_subscribe_registers_handler(bus):
    calls = []

    async def handler(topic, payload):
        calls.append((topic, payload))

    await bus.subscribe("ecoflow/powerstream/state", handler)
    assert bus.subscriber_count("ecoflow/powerstream/state") == 1


@pytest.mark.asyncio
async def test_subscribe_same_handler_twice_is_idempotent(bus):
    async def handler(topic, payload):
        pass

    await bus.subscribe("ecoflow/powerstream/state", handler)
    await bus.subscribe("ecoflow/powerstream/state", handler)
    assert bus.subscriber_count("ecoflow/powerstream/state") == 1


@pytest.mark.asyncio
async def test_unsubscribe_removes_handler(bus):
    async def handler(topic, payload):
        pass

    await bus.subscribe("ecoflow/powerstream/state", handler)
    await bus.unsubscribe("ecoflow/powerstream/state", handler)
    assert bus.subscriber_count("ecoflow/powerstream/state") == 0


@pytest.mark.asyncio
async def test_unsubscribe_nonexistent_handler_is_safe(bus):
    async def handler(topic, payload):
        pass

    # kein Fehler wenn Handler nicht registriert war
    await bus.unsubscribe("ecoflow/powerstream/state", handler)


# --- Publish -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_calls_subscriber(bus):
    received = []

    async def handler(topic, payload):
        received.append((topic, payload))

    await bus.subscribe("ecoflow/powerstream/state", handler)
    await bus.publish("ecoflow/powerstream/state", {"power": 120})

    # Tasks müssen ausgeführt werden
    await asyncio.sleep(0)

    assert len(received) == 1
    assert received[0] == ("ecoflow/powerstream/state", {"power": 120})


@pytest.mark.asyncio
async def test_publish_calls_multiple_subscribers(bus):
    received_a = []
    received_b = []

    async def handler_a(topic, payload):
        received_a.append(payload)

    async def handler_b(topic, payload):
        received_b.append(payload)

    await bus.subscribe("ecoflow/powerstream/state", handler_a)
    await bus.subscribe("ecoflow/powerstream/state", handler_b)
    await bus.publish("ecoflow/powerstream/state", {"power": 120})

    await asyncio.sleep(0)

    assert len(received_a) == 1
    assert len(received_b) == 1


@pytest.mark.asyncio
async def test_publish_to_topic_without_subscribers_is_safe(bus):
    # kein Fehler wenn niemand subscribed
    await bus.publish("ecoflow/powerstream/state", {"power": 120})
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_publish_does_not_affect_other_topics(bus):
    received = []

    async def handler(topic, payload):
        received.append(payload)

    await bus.subscribe("ecoflow/powerstream/state", handler)
    await bus.publish("ecoflow/delta2max/state", {"battery": 80})

    await asyncio.sleep(0)

    assert len(received) == 0


@pytest.mark.asyncio
async def test_publish_multiple_events_all_delivered(bus):
    received = []

    async def handler(topic, payload):
        received.append(payload)

    await bus.subscribe("ecoflow/powerstream/state", handler)
    await bus.publish("ecoflow/powerstream/state", {"power": 100})
    await bus.publish("ecoflow/powerstream/state", {"power": 200})
    await bus.publish("ecoflow/powerstream/state", {"power": 300})

    await asyncio.sleep(0)

    assert len(received) == 3


# --- Handler-Fehler ----------------------------------------------------------


@pytest.mark.asyncio
async def test_handler_exception_does_not_crash_bus(bus):
    """Ein fehlerhafter Handler darf den Bus nicht zum Absturz bringen."""
    good_received = []

    async def bad_handler(topic, payload):
        raise ValueError("intentional error")

    async def good_handler(topic, payload):
        good_received.append(payload)

    await bus.subscribe("ecoflow/powerstream/state", bad_handler)
    await bus.subscribe("ecoflow/powerstream/state", good_handler)
    await bus.publish("ecoflow/powerstream/state", {"power": 120})

    await asyncio.sleep(0)

    # good_handler muss trotzdem aufgerufen worden sein
    assert len(good_received) == 1


# --- Topics ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_topics_returns_subscribed_topics(bus):
    async def handler(topic, payload):
        pass

    await bus.subscribe("ecoflow/powerstream/state", handler)
    await bus.subscribe("mqtt/connection/state", handler)

    assert "ecoflow/powerstream/state" in bus.topics
    assert "mqtt/connection/state" in bus.topics


@pytest.mark.asyncio
async def test_topics_excludes_empty_topics(bus):
    async def handler(topic, payload):
        pass

    await bus.subscribe("ecoflow/powerstream/state", handler)
    await bus.unsubscribe("ecoflow/powerstream/state", handler)

    assert "ecoflow/powerstream/state" not in bus.topics
