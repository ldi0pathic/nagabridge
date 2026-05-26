"""MQTT adapter that forwards bus events to and from a broker."""

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib import import_module
from typing import Protocol, cast

from nagabridge.core.adapter import Adapter
from nagabridge.core.bus import EventBus, Payload, Topic
from nagabridge.core.health import HealthState, HealthStatus
from nagabridge.core.topics import health_topic

_MODULE = __name__.rsplit(".", 1)[0]


class _SupportsMqttClient(Protocol):
    def username_pw_set(self, user: str, password: str | None = None) -> None: ...
    def connect(self, host: str, port: int) -> None: ...
    def loop_start(self) -> None: ...
    def loop_stop(self) -> None: ...
    def disconnect(self) -> None: ...
    def publish(
        self,
        topic: str,
        payload: str,
        qos: int,
        *,
        retain: bool,
    ) -> None: ...
    def subscribe(self, topic: str) -> object: ...

    on_message: object


@dataclass(slots=True)
class MqttAdapterConfig:
    """Configuration for the MQTT adapter."""

    host: str
    port: int = 1883
    user: str | None = None
    password: str | None = None
    subscribe_topics: list[str] = field(default_factory=list)
    inbound_topics: list[str] = field(default_factory=list)
    publish_prefix: str = "nagabridge"


class MqttAdapter(Adapter):
    """Publish selected bus topics to an MQTT broker."""

    def __init__(
        self,
        config: MqttAdapterConfig,
        client_factory: Callable[[], _SupportsMqttClient] | None = None,
    ) -> None:
        """Build a new adapter with optional injected MQTT client factory."""
        self._config = config
        self._log = logging.getLogger(f"{_MODULE}.mqtt")
        self._client_factory = client_factory
        self._health = HealthStatus(state=HealthState.failed, detail="not started")
        self._bus: EventBus | None = None
        self._client: _SupportsMqttClient | None = None

    @property
    def name(self) -> str:
        """Return the adapter name."""
        return "mqtt"

    @property
    def version(self) -> str:
        """Return the adapter implementation version."""
        return "0.3.0"

    @property
    def health(self) -> HealthStatus:
        """Return current health information."""
        return self._health

    async def start(self, bus: EventBus) -> None:
        """Connect to MQTT and subscribe to configured bus topics."""
        self._bus = bus
        if self._client_factory is None:
            try:
                mqtt_client = import_module("paho.mqtt.client")
            except ModuleNotFoundError as err:
                msg = "paho-mqtt is required for MqttAdapter"
                raise RuntimeError(msg) from err
            self._client = cast("_SupportsMqttClient", mqtt_client.Client())
        else:
            self._client = self._client_factory()

        if self._config.user:
            self._client.username_pw_set(self._config.user, self._config.password)

        self._client.connect(self._config.host, self._config.port)
        self._client.loop_start()

        for topic in self._config.subscribe_topics:
            await bus.subscribe(topic, self._on_bus_event)
        for topic in self._config.inbound_topics:
            self._client.subscribe(topic)
        self._client.on_message = self._on_mqtt_message

        self._health = HealthStatus(
            state=HealthState.ok,
            detail=f"connected to {self._config.host}:{self._config.port}",
        )
        await self._publish_health()

    async def stop(self) -> None:
        """Disconnect from MQTT and unsubscribe from bus topics."""
        if self._bus is not None:
            for topic in self._config.subscribe_topics:
                await self._bus.unsubscribe(topic, self._on_bus_event)

        if self._client is not None:
            self._client.loop_stop()
            self._client.disconnect()

        self._health = HealthStatus(state=HealthState.failed, detail="stopped")
        await self._publish_health()
        self._client = None
        self._bus = None

    async def _publish_health(self) -> None:
        if self._bus is None:
            return
        try:
            await self._bus.publish(health_topic(self.name), self._health.to_payload(self.name))
        except Exception:
            self._log.exception("Failed to publish health for %s", self.name)

    async def _on_bus_event(self, topic: Topic, payload: Payload) -> None:
        """Publish incoming bus events to MQTT."""
        if self._client is None:
            return

        mqtt_topic = self._map_topic(topic)
        self._client.publish(mqtt_topic, json.dumps(payload), qos=0, retain=False)

    def _on_mqtt_message(self, _client: object, _userdata: object, msg: object) -> None:
        """Forward inbound MQTT messages onto the internal event bus."""
        if self._bus is None:
            return
        topic = getattr(msg, "topic", "")
        payload_bytes = getattr(msg, "payload", b"")
        try:
            payload = json.loads(payload_bytes.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("payload must decode to JSON object")
        except Exception:
            self._log.warning("Ignoring invalid inbound MQTT payload on topic %s", topic, exc_info=True)
            return
        bus_topic = self._unmap_topic(topic)
        if bus_topic is None:
            self._log.debug("Ignoring inbound MQTT message outside prefix: %s", topic)
            return
        self._run_publish_from_callback(bus_topic, payload)

    def _run_publish_from_callback(self, topic: Topic, payload: Payload) -> None:
        """Schedule async publish from sync MQTT callback context."""
        loop = asyncio.get_running_loop()
        loop.create_task(self._bus.publish(topic, payload))  # type: ignore[union-attr]

    def _map_topic(self, topic: Topic) -> str:
        """Map an internal bus topic to an MQTT topic path."""
        return f"{self._config.publish_prefix}/{topic}"

    def _unmap_topic(self, topic: Topic) -> Topic | None:
        """Map MQTT topic with configured prefix back to internal bus topic."""
        prefix = f"{self._config.publish_prefix}/"
        if not topic.startswith(prefix):
            return None
        return topic[len(prefix) :]
